"""Hosted chat-model adapters; failures are fixed codes, never URLs, keys or response bodies."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from backend.bintanong_routing.transport import RuntimeFailure

from .settings import AgentSettings

OPENAI_COMPATIBLE_ENDPOINTS = {  # provider -> (base URL, token-limit field)
    'deepseek': ('https://api.deepseek.com', 'max_tokens'),
    'openai': ('https://api.openai.com/v1', 'max_completion_tokens'),
    'gemini': ('https://generativelanguage.googleapis.com/v1beta/openai', 'max_tokens'),
}
ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
ANTHROPIC_VERSION = '2026-10-21'
# deepseek-flash thinks at high effort unless told not to (API docs, 15 Nov 2026).
DEEPSEEK_THINKING_OFF = {'thinking': {'type': 'disabled'}}


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class Usage:
    """Billed tokens of one or more model calls; counts only, never text."""
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0  # part of output_tokens

    def __add__(self, other: 'Usage') -> 'Usage':
        return Usage(self.input_tokens + other.input_tokens, self.cached_input_tokens + other.cached_input_tokens,
                     self.output_tokens + other.output_tokens, self.reasoning_tokens + other.reasoning_tokens)


def _count(data, *path) -> int:
    for key in path:
        data = data.get(key) if isinstance(data, dict) else None
    return data if isinstance(data, int) and not isinstance(data, bool) else 0


def openai_usage(body: dict) -> Usage:
    usage = body.get('usage')
    cached = _count(usage, 'prompt_cache_hit_tokens') or _count(usage, 'prompt_tokens_details', 'cached_tokens')
    return Usage(_count(usage, 'prompt_tokens'), cached, _count(usage, 'completion_tokens'),
                 _count(usage, 'completion_tokens_details', 'reasoning_tokens'))


def anthropic_usage(body: dict) -> Usage:
    usage = body.get('usage')
    cached = _count(usage, 'cache_read_input_tokens')
    return Usage(_count(usage, 'input_tokens') + cached + _count(usage, 'cache_creation_input_tokens'), cached,
                 _count(usage, 'output_tokens'))


@dataclass(frozen=True)
class ModelTurn:
    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: Usage = field(default_factory=Usage)


class ChatModel(Protocol):
    async def complete(self, messages: list[dict], tools: list[dict], *,
                       max_output_tokens: int = 2048) -> ModelTurn: ...


async def post_json(client, url, headers, payload, timeout_seconds) -> dict:
    """POST and return the JSON object body, mapping every failure to a fixed code."""
    owned = client is None
    client = client or httpx.AsyncClient()
    try:
        response = await client.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        if not response.is_success:
            raise RuntimeFailure('model_http_error')
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeFailure('invalid_server_response')
        return body
    except httpx.TimeoutException:
        raise RuntimeFailure('model_timeout') from None
    except httpx.RequestError:
        raise RuntimeFailure('model_connection_error') from None
    except ValueError:  # response body is not JSON
        raise RuntimeFailure('invalid_server_response') from None
    finally:
        if owned:
            await client.aclose()


def parse_arguments(raw) -> dict:
    try:
        arguments = json.loads(raw)
    except (TypeError, ValueError):
        raise RuntimeFailure('invalid_server_response') from None
    if not isinstance(arguments, dict):
        raise RuntimeFailure('invalid_server_response')
    return arguments


def require_text(value) -> str:
    if value is None:
        return ''
    if not isinstance(value, str):
        raise RuntimeFailure('invalid_server_response')
    return value


class OpenAICompatibleModel:
    def __init__(self, base_url, api_key, model, *, timeout_seconds=60, client=None,
                 token_limit_field='max_tokens', extra_payload=None):
        self.base_url = base_url.rstrip('/')
        self.extra_payload = dict(extra_payload or {})
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.token_limit_field = token_limit_field
        self._api_key = api_key
        self._client = client

    def __repr__(self):
        return f'OpenAICompatibleModel(base_url={self.base_url!r}, model={self.model!r})'

    async def complete(self, messages, tools, *, max_output_tokens=2048) -> ModelTurn:
        payload = {**self.extra_payload, 'model': self.model, 'messages': messages,
                   self.token_limit_field: max_output_tokens}
        if tools:
            payload['tools'] = tools
        body = await post_json(self._client, self.base_url + '/chat/completions',
                               {'Authorization': f'Bearer {self._api_key}'}, payload, self.timeout_seconds)
        try:
            message = body['choices'][0]['message']
            calls = tuple(ToolCall(call['id'], call['function']['name'],
                                   parse_arguments(call['function']['arguments']))
                          for call in message.get('tool_calls') or ())
            return ModelTurn(require_text(message['content']), calls, openai_usage(body))
        except (KeyError, TypeError, IndexError, AttributeError):
            raise RuntimeFailure('invalid_server_response') from None


def anthropic_tool(tool) -> dict:
    function = tool['function']
    return {'name': function['name'], 'description': function['description'],
            'input_schema': function['parameters']}


def anthropic_messages(messages) -> tuple[str, list[dict]]:
    """Split OpenAI-shape messages into Anthropic's system string and alternating turns."""
    system, converted = [], []
    for message in messages:
        role = message['role']
        if role == 'system':
            system.append(message['content'])
        elif role == 'tool':
            block = {'type': 'tool_result', 'tool_use_id': message['tool_call_id'], 'content': message['content']}
            if converted and converted[-1]['role'] == 'user' and isinstance(converted[-1]['content'], list):
                converted[-1]['content'].append(block)  # consecutive results share one user message
            else:
                converted.append({'role': 'user', 'content': [block]})
        elif role == 'assistant' and message.get('tool_calls'):
            blocks = [{'type': 'text', 'text': message['content']}] if message.get('content') else []
            blocks += [{'type': 'tool_use', 'id': call['id'], 'name': call['function']['name'],
                        'input': parse_arguments(call['function']['arguments'])}
                       for call in message['tool_calls']]
            converted.append({'role': 'assistant', 'content': blocks})
        else:
            converted.append({'role': role, 'content': message['content']})
    return '\n'.join(system), converted


class AnthropicModel:
    def __init__(self, api_key, model, *, timeout_seconds=60, client=None):
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._client = client

    def __repr__(self):
        return f'AnthropicModel(model={self.model!r})'

    async def complete(self, messages, tools, *, max_output_tokens=2048) -> ModelTurn:
        system, turns = anthropic_messages(messages)
        payload = {'model': self.model, 'max_tokens': max_output_tokens, 'messages': turns}
        if system:
            payload['system'] = system
        if tools:
            payload['tools'] = [anthropic_tool(tool) for tool in tools]
        headers = {'x-api-key': self._api_key, 'anthropic-version': ANTHROPIC_VERSION}
        body = await post_json(self._client, ANTHROPIC_URL, headers, payload, self.timeout_seconds)
        try:
            blocks = body['content']
            text = ''.join(block['text'] for block in blocks if block['type'] == 'text')
            calls = tuple(ToolCall(block['id'], block['name'], block['input']) for block in blocks
                          if block['type'] == 'tool_use')
            if not all(isinstance(call.arguments, dict) for call in calls):
                raise RuntimeFailure('invalid_server_response')
            return ModelTurn(text, calls, anthropic_usage(body))
        except (KeyError, TypeError, AttributeError):
            raise RuntimeFailure('invalid_server_response') from None


def build_model(settings: AgentSettings) -> ChatModel:
    if settings.provider == 'anthropic':
        return AnthropicModel(settings.api_key, settings.model)
    base_url, token_limit_field = OPENAI_COMPATIBLE_ENDPOINTS[settings.provider]
    quiet = settings.provider == 'deepseek' and not settings.thinking
    return OpenAICompatibleModel(base_url, settings.api_key, settings.model, token_limit_field=token_limit_field,
                                 extra_payload=DEEPSEEK_THINKING_OFF if quiet else None)
