"""Hosted agent app factory: environment only, public key only, Supabase reads only (synthetic data)."""
import base64
import copy
import importlib
import json

import pytest
from fastapi.testclient import TestClient

import test_agent_loop as loop
from test_api_hosted_snapshot import Database
from test_runtime_hosted_curricula import REF
from test_runtime_multi_curriculum import C1, real_ledger

ORIGIN = 'https://bintanong.example'


def agent_app():
    return importlib.import_module('backend.bintanong_api.agent_app')


def jwt(role):
    payload = base64.urlsafe_b64encode(json.dumps({'role': role}).encode()).decode().rstrip('=')
    return f'header.{payload}.signature'


def environment(**changes):
    env = {'SUPABASE_URL': 'https://synthetic.supabase.co', 'SUPABASE_ANON_KEY': jwt('anon'),
           'DEEPSEEK_API_KEY': 'synthetic-key', 'BINTANONG_ALLOWED_ORIGINS': ORIGIN + ', https://second.example',
           'BINTANONG_ALLOW_GUESTS': '1', 'BINTANONG_RELEASE_ID': 'hosted',
           'BINTANONG_RESEARCH_AUTHORIZATION': REF}
    env.update(changes)
    return {name: value for name, value in env.items() if value is not None}


class SpyClient:
    """One synthetic release (a document chunk and a curriculum ledger). Records every method that is called."""

    def __init__(self):
        database, ledger = Database(), real_ledger(C1, 'course-1', 'course-2')  # fictional courses
        self.ledger = ledger
        self.tables = database.tables
        self.tables['knowledge_releases'][0]['research_authorization_ref'] = REF
        self.tables['chunks'][0]['source_label'] = 'Synthetic Handbook.pdf'
        scope = ledger['scope']
        self.tables['release_curriculum_ledgers'] = [dict(
            release_id='hosted', curriculum_id=scope['curriculum_id'], ledger_sha256=ledger['content_sha256'])]
        self.tables['curriculum_ledgers'] = [dict(ledger_sha256=ledger['content_sha256'], ledger=ledger,
            program_id=scope['program_id'], curriculum_id=scope['curriculum_id'])]
        self.calls = []

    def select(self, table, columns='*', *, filters=None, role):
        self.calls.append(('select', table, role))
        return copy.deepcopy(self.tables[table])

    def close(self):
        self.calls.append(('close', None, None))

    def __getattr__(self, name):  # any other storage method (insert, upsert, rpc, delete ...)
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            raise AssertionError(f'unexpected storage call: {name}')
        return record


def started(model=None, **changes):
    spy = SpyClient()
    app = agent_app().load_agent_app(environment(**changes), client=spy, model=model)
    return spy, TestClient(app, base_url='https://testserver', headers={'Origin': ORIGIN})


def test_app_refuses_service_role_key():
    spy = SpyClient()
    with pytest.raises(ValueError, match='public_runtime_key_required'):
        agent_app().load_agent_app(environment(SUPABASE_ANON_KEY=jwt('service_role')), client=spy)
    assert spy.calls == []


@pytest.mark.parametrize('missing, code', [
    ('SUPABASE_URL', 'agent_credentials_required'), ('SUPABASE_ANON_KEY', 'agent_credentials_required'),
    ('BINTANONG_ALLOWED_ORIGINS', 'allowed_origins_required'), ('BINTANONG_RELEASE_ID', 'release_required'),
    ('BINTANONG_RESEARCH_AUTHORIZATION', 'release_required'), ('DEEPSEEK_API_KEY', 'llm_api_key_required')])
def test_app_requires_its_environment(missing, code):
    with pytest.raises(ValueError, match=code):
        agent_app().load_agent_app(environment(**{missing: None}), client=SpyClient())


def test_app_starts_without_model_url_or_encoder():
    spy, client = started()
    scope = spy.ledger['scope']
    listed = client.get('/curricula').json()['curricula']
    assert [(c['programId'], c['curriculumId']) for c in listed] == [(scope['program_id'], scope['curriculum_id'])]
    assert client.get('/health/live').status_code == 200
    ready = client.get('/health/ready')
    assert ready.status_code == 200 and ready.json()['probes'] == {'student_runtime': True}


def test_allowed_origins_come_from_the_environment():
    _, client = started()
    assert client.app.state.settings.allowed_origins == (ORIGIN, 'https://second.example')
    assert client.app.state.settings.require_auth is True and client.app.state.settings.allow_guests is True
    _, strict = started(BINTANONG_ALLOW_GUESTS=None)
    assert strict.app.state.settings.allow_guests is False


def chat_body(text):
    return dict(id='chat-1', trigger='submit-message',
                messages=[dict(id='msg-1', role='user', parts=[dict(type='text', text=text)])])


def test_chat_answers_from_the_hosted_passages():
    model = loop.FakeModel(loop.tool_turn('search_documents', {'query': 'synthetic visible field'}),
                           loop.final_turn(text='It is a synthetic field.', citations=['C001']))
    spy, client = started(model)
    response = client.post('/chat', json=chat_body('What does the synthetic reading say?'))
    assert response.status_code == 200
    events = response.content.decode('utf-8')
    chunk_id = spy.tables['chunks'][0]['chunk_id']
    assert 'It is a synthetic field.' in events and f'"sourceId":"ev-{chunk_id}"' in events
    assert client.get(f'/sources/ev-{chunk_id}').json()['title'] == 'Synthetic Handbook.pdf'


def test_no_supabase_write_method_is_called():
    model = loop.FakeModel(loop.tool_turn('search_documents', {'query': 'synthetic visible field'}),
                           loop.final_turn(text='It is a synthetic field.', citations=['C001']))
    spy, client = started(model)
    client.get('/health/ready')
    client.post('/chat', json=chat_body('What does the synthetic reading say?'))
    client.get('/sources/ev-' + spy.tables['chunks'][0]['chunk_id'])
    assert {call[0] for call in spy.calls} == {'select'}
    assert {call[2] for call in spy.calls} == {'runtime'}
    assert not {call[1] for call in spy.calls} & {'chunk_embeddings', 'selected_release_reviews'}


def test_source_spans_are_read_in_pages():
    rows = [{'chunk_id': f'c{number:04d}', 'span_order': 0} for number in range(2300)]
    requests = []

    class Capped:
        def select(self, table, columns='*', *, filters=None, role):
            requests.append((table, dict(filters or {})))
            if table != 'source_spans':
                return [{'table': table}]
            offset = int(filters.get('offset', 0))
            return rows[offset:offset + 1000]  # the hosted API returns at most 1000 rows per request

    paged = agent_app().PagedReads(Capped())
    assert paged.select('source_spans', role='runtime') == rows
    assert [f['offset'] for table, f in requests] == ['0', '1000', '2000']
    assert all(f['order'] == 'chunk_id,span_order' and f['limit'] == '1000' for _, f in requests)
    assert paged.select('chunks', filters={'a': 'eq.b'}, role='runtime') == [{'table': 'chunks'}]
    assert requests[-1] == ('chunks', {'a': 'eq.b'})


def test_picker_uses_display_names_and_falls_back_to_the_source_file():
    spy = SpyClient()
    scope = spy.ledger['scope']
    names = {'programs': {scope['program_id']: 'Bachelor of Fiction'}, 'curricula': {scope['curriculum_id']: '2018-2019'}}
    app = agent_app().load_agent_app(environment(), client=spy, model=loop.FakeModel(), names=names)
    client = TestClient(app, base_url='https://testserver', headers={'Origin': ORIGIN})
    (listed,) = client.get('/curricula').json()['curricula']
    assert (listed['programName'], listed['curriculumName']) == ('Bachelor of Fiction', '2018-2019')
    plain = agent_app().load_agent_app(environment(), client=SpyClient(), model=loop.FakeModel(), names={})
    (unnamed,) = TestClient(plain, base_url='https://testserver', headers={'Origin': ORIGIN}).get('/curricula').json()['curricula']
    assert unnamed['programName'] == spy.ledger['sources'][0]['filename']


def test_shipped_display_names_cover_programs_and_curricula():
    names = agent_app().display_names()
    assert set(names) >= {'programs', 'curricula'} and len(names['programs']) == 38 and len(names['curricula']) == 39
    assert names['programs']['palsu-bscs'] == 'Bachelor of Science in Computer Science'
    assert all(isinstance(v, str) and v.strip() for group in ('programs', 'curricula') for v in names[group].values())
