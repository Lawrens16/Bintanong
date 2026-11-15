import asyncio
import importlib
import json

import httpx
import pytest


def providers():
    return importlib.import_module('backend.bintanong_agent.providers')


def settings_module():
    return importlib.import_module('backend.bintanong_agent.settings')


def failure():
    return importlib.import_module('backend.bintanong_routing.transport').RuntimeFailure


TOOLS = [{'type': 'function', 'function': {'name': 'lookup', 'description': 'Find a rule.',
                                           'parameters': {'type': 'object', 'properties': {}}}}]
USER_HI = [{'role': 'user', 'content': 'hi'}]


def complete_with(model_factory, handler, messages, tools=TOOLS, **kwargs):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await model_factory(client).complete(messages, tools, **kwargs)
    return asyncio.run(run())


def compatible(client, **kwargs):
    return providers().OpenAICompatibleModel('https://example.test/v1/', 'secret-key', 'm1', client=client, **kwargs)


def anthropic(client):
    return providers().AnthropicModel('secret-key', 'claude-x', client=client)


def reply(message):
    return httpx.Response(200, json={'choices': [{'message': message}]})


def test_openai_compatible_sends_tools_and_parses_tool_calls():
    seen = []
    def handler(request):
        seen.append(request)
        return reply({'content': None, 'tool_calls': [{'id': 'c1', 'type': 'function',
            'function': {'name': 'lookup', 'arguments': '{"q": "grades"}'}}]})
    turn = complete_with(compatible, handler, USER_HI, max_output_tokens=99)
    request = seen[0]
    assert str(request.url) == 'https://example.test/v1/chat/completions'
    assert request.headers['authorization'] == 'Bearer secret-key'
    assert json.loads(request.content) == {'model': 'm1', 'messages': USER_HI, 'tools': TOOLS, 'max_tokens': 99}
    assert turn.text == ''
    assert turn.tool_calls == (providers().ToolCall('c1', 'lookup', {'q': 'grades'}),)


def test_openai_compatible_parses_plain_text_and_omits_empty_tools():
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return reply({'content': 'Hello'})
    turn = complete_with(compatible, handler, USER_HI, tools=[])
    assert 'tools' not in seen[0]
    assert (turn.text, turn.tool_calls) == ('Hello', ())


def test_token_limit_field_is_configurable():
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return reply({'content': 'ok'})
    complete_with(lambda c: compatible(c, token_limit_field='max_completion_tokens'), handler, USER_HI)
    assert seen[0]['max_completion_tokens'] == 2048 and 'max_tokens' not in seen[0]


def test_anthropic_converts_tool_results_and_parses_tool_use():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={'content': [
            {'type': 'text', 'text': 'Checking '}, {'type': 'text', 'text': 'now.'},
            {'type': 'tool_use', 'id': 'tu2', 'name': 'lookup', 'input': {'q': 'x'}}]})
    messages = [
        {'role': 'system', 'content': 'Be brief.'},
        {'role': 'user', 'content': 'hi'},
        {'role': 'assistant', 'content': 'Looking.', 'tool_calls': [
            {'id': 'a', 'type': 'function', 'function': {'name': 'lookup', 'arguments': '{"q": 1}'}},
            {'id': 'b', 'type': 'function', 'function': {'name': 'lookup', 'arguments': '{"q": 2}'}}]},
        {'role': 'tool', 'tool_call_id': 'a', 'content': 'r1'},
        {'role': 'tool', 'tool_call_id': 'b', 'content': 'r2'},
    ]
    turn = complete_with(anthropic, handler, messages, max_output_tokens=50)
    request = seen[0]
    body = json.loads(request.content)
    assert str(request.url) == 'https://api.anthropic.com/v1/messages'
    assert request.headers['x-api-key'] == 'secret-key'
    assert request.headers['anthropic-version'] == '2026-10-21'
    assert body['system'] == 'Be brief.' and body['max_tokens'] == 50 and body['model'] == 'claude-x'
    assert body['tools'] == [{'name': 'lookup', 'description': 'Find a rule.',
                              'input_schema': {'type': 'object', 'properties': {}}}]
    assert body['messages'] == [
        {'role': 'user', 'content': 'hi'},
        {'role': 'assistant', 'content': [
            {'type': 'text', 'text': 'Looking.'},
            {'type': 'tool_use', 'id': 'a', 'name': 'lookup', 'input': {'q': 1}},
            {'type': 'tool_use', 'id': 'b', 'name': 'lookup', 'input': {'q': 2}}]},
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'a', 'content': 'r1'},
            {'type': 'tool_result', 'tool_use_id': 'b', 'content': 'r2'}]},
    ]
    assert turn.text == 'Checking now.'
    assert turn.tool_calls == (providers().ToolCall('tu2', 'lookup', {'q': 'x'}),)


MODEL_FACTORIES = [compatible, anthropic]


@pytest.mark.parametrize('factory', MODEL_FACTORIES)
def test_timeout_maps_to_model_timeout(factory):
    def handler(request):
        raise httpx.ReadTimeout('slow https://secret.example', request=request)
    with pytest.raises(failure()) as caught:
        complete_with(factory, handler, USER_HI)
    assert str(caught.value) == 'model_timeout'


@pytest.mark.parametrize('factory', MODEL_FACTORIES)
def test_connection_error_maps_to_model_connection_error(factory):
    def handler(request):
        raise httpx.ConnectError('refused', request=request)
    with pytest.raises(failure()) as caught:
        complete_with(factory, handler, USER_HI)
    assert str(caught.value) == 'model_connection_error'


@pytest.mark.parametrize('factory', MODEL_FACTORIES)
def test_http_429_maps_to_model_http_error(factory):
    with pytest.raises(failure()) as caught:
        complete_with(factory, lambda r: httpx.Response(429, text='secret body'), USER_HI)
    assert str(caught.value) == 'model_http_error'


@pytest.mark.parametrize('arguments', ['{not json', '[1, 2]', '"text"'])
def test_malformed_tool_arguments_become_invalid_server_response(arguments):
    def handler(request):
        return reply({'content': None, 'tool_calls': [{'id': 'c', 'type': 'function',
            'function': {'name': 'lookup', 'arguments': arguments}}]})
    with pytest.raises(failure()) as caught:
        complete_with(compatible, handler, USER_HI)
    assert str(caught.value) == 'invalid_server_response'


@pytest.mark.parametrize('factory', MODEL_FACTORIES)
@pytest.mark.parametrize('response', [
    httpx.Response(200, text='not json'), httpx.Response(200, json={'choices': []}),
    httpx.Response(200, json={'unexpected': 1})])
def test_unexpected_body_becomes_invalid_server_response(factory, response):
    with pytest.raises(failure()) as caught:
        complete_with(factory, lambda r: response, USER_HI)
    assert str(caught.value) == 'invalid_server_response'


@pytest.mark.parametrize('provider, expected_base, token_field', [
    ('deepseek', 'https://api.deepseek.com', 'max_tokens'),
    ('openai', 'https://api.openai.com/v1', 'max_completion_tokens'),
    ('gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'max_tokens'),
])
def test_build_model_uses_provider_base_url(provider, expected_base, token_field):
    model = providers().build_model(settings_module().AgentSettings(provider, 'm', 'k'))
    assert isinstance(model, providers().OpenAICompatibleModel)
    assert model.base_url == expected_base and model.token_limit_field == token_field
    assert model.model == 'm'


def test_build_model_anthropic():
    model = providers().build_model(settings_module().AgentSettings('anthropic', 'claude-x', 'k'))
    assert isinstance(model, providers().AnthropicModel) and model.model == 'claude-x'


def test_api_key_never_in_repr():
    settings = settings_module().AgentSettings('deepseek', 'm', 'secret-key')
    objects = [settings, providers().build_model(settings),
               providers().build_model(settings_module().AgentSettings('anthropic', 'm', 'secret-key'))]
    assert all('secret-key' not in repr(item) for item in objects)


def test_extra_payload_is_sent_with_every_request():
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return reply({'content': 'ok'})
    complete_with(lambda c: compatible(c, extra_payload={'thinking': {'type': 'disabled'}}), handler, USER_HI)
    assert seen[0]['thinking'] == {'type': 'disabled'} and seen[0]['model'] == 'm1'


def test_deepseek_thinking_is_off_unless_chosen():
    # deepseek-flash thinks at high effort by default (API docs, 15 Nov 2026); thinking tokens bill as output.
    quiet = providers().build_model(settings_module().AgentSettings('deepseek', 'm', 'k'))
    thinking = providers().build_model(settings_module().AgentSettings('deepseek', 'm', 'k', thinking=True))
    assert quiet.extra_payload == {'thinking': {'type': 'disabled'}} and thinking.extra_payload == {}
    for provider in ('openai', 'gemini'):
        assert providers().build_model(settings_module().AgentSettings(provider, 'm', 'k')).extra_payload == {}


def test_openai_compatible_reports_token_usage():
    def deepseek(request):
        return httpx.Response(200, json={'choices': [{'message': {'content': 'ok'}}], 'usage': {
            'prompt_tokens': 1000, 'prompt_cache_hit_tokens': 800, 'prompt_cache_miss_tokens': 200,
            'completion_tokens': 70, 'completion_tokens_details': {'reasoning_tokens': 20}}})
    def openai(request):
        return httpx.Response(200, json={'choices': [{'message': {'content': 'ok'}}], 'usage': {
            'prompt_tokens': 500, 'prompt_tokens_details': {'cached_tokens': 300}, 'completion_tokens': 9}})
    Usage = providers().Usage
    assert complete_with(compatible, deepseek, USER_HI).usage == Usage(1000, 800, 70, 20)
    assert complete_with(compatible, openai, USER_HI).usage == Usage(500, 300, 9, 0)
    assert complete_with(compatible, lambda r: reply({'content': 'ok'}), USER_HI).usage == Usage()


def test_anthropic_reports_token_usage():
    def handler(request):
        return httpx.Response(200, json={'content': [{'type': 'text', 'text': 'ok'}], 'usage': {
            'input_tokens': 100, 'cache_read_input_tokens': 900, 'cache_creation_input_tokens': 50,
            'output_tokens': 40}})
    assert complete_with(anthropic, handler, USER_HI).usage == providers().Usage(1050, 900, 40, 0)


def test_usage_adds_up():
    Usage = providers().Usage
    assert Usage(10, 5, 2, 1) + Usage(1, 1, 1, 1) == Usage(11, 6, 3, 2)
