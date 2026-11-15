import asyncio
import importlib
import json

import test_agent_tools as fixtures
from backend.bintanong_agent.providers import ModelTurn, ToolCall
from backend.bintanong_routing.transport import RuntimeFailure


def agent_module():
    return importlib.import_module('backend.bintanong_agent.agent')


def guards():
    return importlib.import_module('backend.bintanong_agent.guards')


class FakeModel:
    """Returns queued turns (or raises queued failures) and records every message list it was sent."""

    def __init__(self, *turns):
        self.turns, self.requests, self.tool_lists = list(turns), [], []

    async def complete(self, messages, tools, *, max_output_tokens=2048):
        self.requests.append([dict(message) for message in messages])
        self.tool_lists.append(tools)
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn


def tool_turn(name, arguments, call_id='call-1'):
    return ModelTurn('', (ToolCall(call_id, name, arguments),))


def final_turn(kind='answer', text='Pay at the cashier.', citations=(), eligibility=False, language='english'):
    return ModelTurn(json.dumps({'kind': kind, 'language': language, 'text': text, 'citations': list(citations),
                                 'eligibility': eligibility}), ())


SEARCH = tool_turn('search_documents', {'query': 'enrolment fee cashier'})
RULE_CHECK = tool_turn('check_prerequisite', {'course_id': 'course-syn-104'})


def ask(model, question='Where do I pay the enrolment fee?', history=(), state=None, max_rounds=6, stages=None):
    agent = agent_module().Agent(model, fixtures.make_runner(), max_rounds=max_rounds)
    state = state or fixtures.make_state()
    progress = (lambda stage: None) if stages is None else stages.append
    return asyncio.run(agent.answer(question, list(history), state, progress)), state


def test_answer_with_fetched_citation_passes():
    model, stages = FakeModel(SEARCH, final_turn(citations=['C002'])), []
    answer, _ = ask(model, stages=stages)
    assert (answer.status, answer.text, answer.language) == ('answered', 'Pay at the cashier.', 'english')
    assert [p.chunk_id for p in answer.citations] == ['b'] and answer.used_rules is False
    assert stages == ['searching', 'writing']
    tool_message = model.requests[1][-1]
    assert tool_message['role'] == 'tool' and tool_message['tool_call_id'] == 'call-1'
    assert json.loads(tool_message['content'])['passages'][0]['id'] == 'C002'
    assistant_message = model.requests[1][-2]
    assert assistant_message['tool_calls'][0]['function'] == {
        'name': 'search_documents', 'arguments': json.dumps({'query': 'enrolment fee cashier'})}


def test_model_is_given_the_tool_schemas():
    model = FakeModel(final_turn(kind='chat', text='Hello!'))
    ask(model, question='Hello!')
    assert [schema['function']['name'] for schema in model.tool_lists[0]][:2] == ['search_documents', 'open_topic']


def test_final_json_inside_a_code_fence_is_accepted():
    fenced = ModelTurn('```json\n' + final_turn(citations=['C002']).text + '\n```', ())
    answer, _ = ask(FakeModel(SEARCH, fenced))
    assert answer.status == 'answered' and [p.short_id for p in answer.citations] == ['C002']


def test_unknown_citation_is_repaired_once_then_falls_back():
    repaired = FakeModel(SEARCH, final_turn(citations=['C777']), final_turn(citations=['C002']))
    answer, _ = ask(repaired)
    assert answer.status == 'answered' and [p.short_id for p in answer.citations] == ['C002']
    assert 'unknown_citation' in repaired.requests[2][-1]['content'] and repaired.requests[2][-1]['role'] == 'user'

    stubborn = FakeModel(SEARCH, final_turn(citations=['C777']), final_turn(citations=['C778']))
    answer, _ = ask(stubborn)
    assert answer.status == 'insufficient_evidence' and answer.citations == ()
    assert answer.text == guards().FALLBACK_REPLY['english']
    assert len(stubborn.requests) == 3


def test_uncited_policy_answer_falls_back():
    model = FakeModel(final_turn(), final_turn())
    answer, _ = ask(model, question='Saan po magbabayad ng enrolment fee?')
    assert answer.status == 'insufficient_evidence'
    assert (answer.text, answer.language) == (guards().FALLBACK_REPLY['taglish'], 'taglish')
    assert 'uncited_policy_answer' in model.requests[1][-1]['content']


def test_final_turn_that_is_not_the_json_object_is_repaired():
    model = FakeModel(SEARCH, ModelTurn('Pay at the cashier.', ()), final_turn(citations=['C002']))
    answer, _ = ask(model)
    assert answer.status == 'answered'
    assert 'invalid_final' in model.requests[2][-1]['content']


def test_chat_kind_needs_no_citation():
    answer, _ = ask(FakeModel(final_turn(kind='chat', text='Hello! How can I help?')), question='hello')
    assert (answer.status, answer.text, answer.citations) == ('answered', 'Hello! How can I help?', ())


def test_clarify_and_out_of_scope_kinds_map_to_their_status():
    clarify, _ = ask(FakeModel(final_turn(kind='clarify', text='Which program are you in?')))
    declined, _ = ask(FakeModel(final_turn(kind='out_of_scope', text='That is for staff only.')))
    assert (clarify.status, clarify.text) == ('clarification_needed', 'Which program are you in?')
    assert (declined.status, declined.text) == ('out_of_scope', 'That is for staff only.')


def test_eligibility_without_rule_tool_is_repaired():
    model = FakeModel(final_turn(text='Yes you can.', eligibility=True), RULE_CHECK,
                      final_turn(text='It depends on SYN 100.', eligibility=True))
    stages = []
    answer, state = ask(model, question='Can I take SYN 104?', stages=stages)
    assert 'rules_not_consulted' in model.requests[1][-1]['content']
    assert (answer.status, answer.text, answer.used_rules) == ('answered', 'It depends on SYN 100.', True)
    assert state.rule_checks == [fixtures.RULE_RESULT] and stages == ['writing', 'checking', 'writing']


def test_eligibility_wording_is_left_to_the_model():
    wording = 'Hmm, mukhang kailangan mo muna ng SYN 100 bago yan, pero di ko pa alam kung tapos mo na.'
    model = FakeModel(RULE_CHECK, final_turn(text=wording, eligibility=True, language='taglish'))
    answer, _ = ask(model, question='pwede ba ko mag syn104?')
    assert (answer.status, answer.text, answer.language) == ('answered', wording, 'taglish')
    assert answer.used_rules is True and answer.citations == ()


def test_excluded_audience_question_never_reaches_the_model():
    model = FakeModel()
    answer, _ = ask(model, question='How do I enroll in the College of Law?')
    assert model.requests == []
    assert (answer.status, answer.text) == ('out_of_scope', guards().SCOPE_NOTICE['english'])
    answer, _ = ask(model, question='Paano po mag-enroll sa graduate school?')
    assert (answer.text, answer.language) == (guards().SCOPE_NOTICE['taglish'], 'taglish')


def test_private_ids_never_reach_the_model_or_the_citations():
    state = fixtures.make_state(facts=(fixtures.passed_fact(),))
    model = FakeModel(SEARCH, final_turn(citations=['fact-syn-100']), final_turn(citations=['C002']))
    answer, _ = ask(model, state=state)
    assert [p.chunk_id for p in answer.citations] == ['b']
    sent = json.dumps(model.requests)
    assert fixtures.SESSION not in sent and 'fact-syn-100' not in sent.split('"role": "assistant"')[0]
    assert 'SYN 100: passed' in model.requests[0][0]['content']


def test_citations_come_only_from_this_turn():
    state = fixtures.make_state()
    state.fetched['C001'] = fixtures.make_corpus().get('C001')  # left over from an earlier turn
    state.rule_checks.append(fixtures.RULE_RESULT)
    answer, state = ask(FakeModel(final_turn(citations=['C001']), final_turn(citations=['C001'])), state=state)
    assert answer.status == 'insufficient_evidence' and answer.used_rules is False
    assert state.fetched == {} and state.rule_checks == []


def test_loop_stops_at_max_rounds():
    model = FakeModel(*[SEARCH] * 10)
    answer, _ = ask(model, max_rounds=3)
    assert len(model.requests) == 3
    assert (answer.status, answer.text) == ('insufficient_evidence', guards().FALLBACK_REPLY['english'])


def test_model_failure_returns_temporarily_unavailable():
    model = FakeModel(RuntimeFailure('model_timeout'))
    answer, _ = ask(model)
    assert (answer.status, answer.text) == ('temporarily_unavailable', guards().UNAVAILABLE_REPLY['english'])
    assert len(model.requests) == 1 and answer.citations == ()
    assert 'model_timeout' not in answer.text


def test_malformed_provider_response_is_retried_once():
    recovered = FakeModel(RuntimeFailure('invalid_server_response'), final_turn(kind='chat', text='Hi!'))
    answer, _ = ask(recovered, question='hi')
    assert answer.status == 'answered' and recovered.requests[0] == recovered.requests[1]

    broken = FakeModel(RuntimeFailure('invalid_server_response'), RuntimeFailure('invalid_server_response'))
    answer, _ = ask(broken, question='hi')
    assert answer.status == 'temporarily_unavailable' and len(broken.requests) == 2


def test_unknown_tool_error_is_fed_back_to_the_model():
    model = FakeModel(tool_turn('delete_everything', {}), final_turn(kind='chat', text='Sorry, I cannot do that.'))
    answer, _ = ask(model)
    assert json.loads(model.requests[1][-1]['content']) == {'error': 'unknown_tool'}
    assert answer.status == 'answered'


def test_history_is_sent_before_the_question():
    history = [{'role': 'user', 'content': 'Where do I pay the fee?'},
               {'role': 'assistant', 'content': 'At the cashier.'}]
    model = FakeModel(final_turn(kind='chat', text='You are welcome!'))
    ask(model, question='thanks!', history=history)
    sent = model.requests[0]
    assert sent[0]['role'] == 'system' and 'FEES' in sent[0]['content']
    assert fixtures.CURRICULUM in sent[0]['content']
    assert sent[1:] == history + [{'role': 'user', 'content': 'thanks!'}]


def test_system_prompt_says_when_no_curriculum_is_chosen():
    model = FakeModel(final_turn(kind='clarify', text='Which program?'))
    ask(model, question='Can I take SYN 104?', state=fixtures.make_state(chosen=False))
    assert 'not chosen' in model.requests[0][0]['content']
