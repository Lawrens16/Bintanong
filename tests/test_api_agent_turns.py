"""Hosted agent chat turns: session history in, one committed exchange out, same stream as the original path."""
import asyncio
import importlib
import json

import pytest
from fastapi.testclient import TestClient

import test_agent_tools as fixtures
from backend.bintanong_agent.agent import AgentAnswer
from backend.bintanong_api.app import ApiServices, ApiSettings, create_app
from backend.bintanong_api.chat import ChatRequest, CurriculumOption
from backend.bintanong_api.session import ApiError, Session
from backend.bintanong_api.stream import answer_parts
from backend.bintanong_private_context.sessions import SessionStore
from backend.bintanong_routing.contracts import ScopedFact

ORIGIN = 'https://bintanong.example'
CURRICULA = (CurriculumOption(fixtures.PROGRAM, fixtures.CURRICULUM, 'Program', 'Curriculum'),)
SCOPE = dict(programId=fixtures.PROGRAM, curriculumId=fixtures.CURRICULUM)


def agent_turns():
    return importlib.import_module('backend.bintanong_api.agent_turns')


class FakeAgent:
    """Stands in for `Agent`: records each call and returns queued answers."""

    def __init__(self, *answers, error=None):
        self.answers, self.error, self.calls = list(answers), error, []

    async def answer(self, question, history, state, progress):
        self.calls.append((question, list(history), state))
        progress('searching')
        progress('writing')
        if self.error is not None:
            raise self.error
        return self.answers.pop(0)


def answered(text, *citations, status='answered', language='english'):
    return AgentAnswer(status, text, language, tuple(citations))


def fee_passage():
    return fixtures.make_corpus().get('C002')


def new_session(store):
    issued = store.issue()
    return Session(issued.credential, store.resolve(issued.credential))


def body(text, message_id='msg-1', **extra):
    return dict(id='chat-1', trigger='submit-message',
                messages=[dict(id=message_id, role='user', parts=[dict(type='text', text=text)])], **extra)


def run_turn(turns, session, text, message_id='msg-1', **extra):
    return asyncio.run(turns.answer(session, ChatRequest.model_validate(body(text, message_id, **extra))))


def make_turns(store, agent):
    return agent_turns().AgentTurns(store, agent, CURRICULA)


def test_turn_commits_exchange_and_history_reaches_next_turn():
    store, agent = SessionStore(), FakeAgent(answered('At the cashier.'), answered('You are welcome!'))
    session, turns = new_session(store), None
    turns = make_turns(store, agent)
    reply = run_turn(turns, session, 'Where do I pay the fee?', 'msg-1')
    run_turn(turns, session, 'thanks!', 'msg-2')
    assert reply.status == 'answered' and reply.text == 'At the cashier.'
    assert agent.calls[0][:2] == ('Where do I pay the fee?', [])
    assert agent.calls[1][:2] == ('thanks!', [{'role': 'user', 'content': 'Where do I pay the fee?'},
                                               {'role': 'assistant', 'content': 'At the cashier.'}])
    view = store.resolve(session.credential)
    assert [(e.user_text, e.assistant_text, e.answer_status) for e in view.dialogue.exchanges] == [
        ('Where do I pay the fee?', 'At the cashier.', 'answered'), ('thanks!', 'You are welcome!', 'answered')]


def test_failed_turn_commits_nothing():
    store, agent = SessionStore(), FakeAgent(error=RuntimeError('boom'))
    session = new_session(store)
    with pytest.raises(ApiError) as refused:
        run_turn(make_turns(store, agent), session, 'Where do I pay the fee?')
    assert (refused.value.status, refused.value.code) == (503, 'answer_unavailable')
    assert store.resolve(session.credential).dialogue.revision == 0
    # The same message can be sent again: the failed turn left no turn in flight.
    retry = make_turns(store, FakeAgent(answered('At the cashier.')))
    assert run_turn(retry, session, 'Where do I pay the fee?').text == 'At the cashier.'


def test_unavailable_reply_is_shown_but_not_kept_as_history():
    store = SessionStore()
    agent = FakeAgent(answered('Try again later.', status='temporarily_unavailable'), answered('At the cashier.'))
    session, turns = new_session(store), make_turns(store, agent)
    assert run_turn(turns, session, 'Where do I pay the fee?').status == 'temporarily_unavailable'
    assert store.resolve(session.credential).dialogue.revision == 0
    run_turn(turns, session, 'Where do I pay the fee?')
    assert agent.calls[1][1] == []


def test_turn_state_carries_the_chosen_scope_and_only_its_facts():
    store, agent = SessionStore(), FakeAgent(answered('ok'), answered('ok'))
    session = new_session(store)

    def fact(name, curriculum):
        return ScopedFact.parse(dict(fact_id='fact-' + name, session_id=session.view.session_id,
            program_id=fixtures.PROGRAM, curriculum_id=curriculum, course_id='course-syn-100', state='passed'))
    store.set_facts(session.credential, (fact('mine', fixtures.CURRICULUM), fact('other', 'curriculum-other')))
    turns = make_turns(store, agent)
    run_turn(turns, session, 'Can I take SYN 104?', 'msg-1', **SCOPE)
    run_turn(turns, session, 'Can I take SYN 104?', 'msg-2')
    chosen, unchosen = agent.calls[0][2], agent.calls[1][2]
    assert (chosen.program_id, chosen.curriculum_id) == (fixtures.PROGRAM, fixtures.CURRICULUM)
    assert [f.fact_id for f in chosen.facts] == ['fact-mine']
    assert (unchosen.program_id, unchosen.curriculum_id, unchosen.facts) == (None, None, ())


def test_unlisted_curriculum_is_refused_before_the_agent_runs():
    store, agent = SessionStore(), FakeAgent(answered('ok'))
    with pytest.raises(ApiError) as refused:
        run_turn(make_turns(store, agent), new_session(store), 'hello', programId='program-x',
                 curriculumId='curriculum-x')
    assert refused.value.code == 'unknown_curriculum' and agent.calls == []


def test_reply_fits_the_existing_answer_parts():
    store, agent = SessionStore(), FakeAgent(answered('Pay at the cashier.', fee_passage(), language='taglish'))
    reply = run_turn(make_turns(store, agent), new_session(store), 'Saan po magbabayad?')
    parts = answer_parts(reply, 'msg-a')
    assert parts[1] == {'type': 'text-delta', 'id': 'msg-a-text', 'delta': 'Pay at the cashier.'}
    assert [p for p in parts if p['type'] == 'source-document'] == [
        {'type': 'source-document', 'sourceId': 'C002', 'mediaType': 'text/plain', 'title': 'Synthetic.pdf, p.3'}]
    summary = next(p for p in parts if p['type'] == 'data-answer')['data']
    assert summary == {'status': 'answered', 'conditional': False, 'language': 'taglish', 'missingFields': [],
                       'notice': 'Hindi official university guidance.'}


def test_english_reply_uses_the_frontend_language_code():
    store, agent = SessionStore(), FakeAgent(answered('Hello!'))
    reply = run_turn(make_turns(store, agent), new_session(store), 'hello')
    assert reply.language == 'en'


def app_client(agent):
    store = SessionStore()
    app = create_app(ApiServices(sessions=store, curricula=CURRICULA, turns=make_turns(store, agent)),
                     ApiSettings(allowed_origins=(ORIGIN,)))
    return TestClient(app, base_url='https://testserver', headers={'Origin': ORIGIN})


def parse(raw: bytes):
    events = [e for e in raw.decode('utf-8').split('\n\n') if e]
    assert events[-1] == 'data: [DONE]'
    return [json.loads(e[len('data: '):]) for e in events[:-1]]


def test_stream_emits_status_text_sources_and_answer_parts():
    client = app_client(FakeAgent(answered('Pay at the cashier.', fee_passage())))
    response = client.post('/chat', json=body('Where do I pay the fee?'))
    assert response.status_code == 200 and response.headers['x-vercel-ai-ui-message-stream'] == 'v1'
    parts = parse(response.content)
    kinds = [p['type'] for p in parts]
    assert kinds == ['start', 'data-status', 'data-status', 'text-start', 'text-delta', 'text-end',
                     'source-document', 'data-answer', 'finish']
    assert [p['data']['stage'] for p in parts if p['type'] == 'data-status'] == ['searching', 'writing']
    assert parts[4]['delta'] == 'Pay at the cashier.' and parts[6]['sourceId'] == 'C002'
    assert parts[7]['data']['status'] == 'answered' and parts[7]['data']['language'] == 'en'


def test_sources_endpoint_serves_cited_passage():
    client = app_client(FakeAgent(answered('Pay at the cashier.', fee_passage())))
    assert client.get('/sources/C002').status_code == 404  # nothing is served before an answer cites it
    client.post('/chat', json=body('Where do I pay the fee?'))
    card = client.get('/sources/C002').json()
    assert card['sourceId'] == 'C002' and card['title'] == 'Synthetic.pdf' and card['page'] == 3
    assert 'Pay the enrolment fee at the cashier.' in card['excerpt']
    assert client.get('/sources/C001').status_code == 404
