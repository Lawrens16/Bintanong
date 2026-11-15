"""Hosted agent composition: environment variables only, the public Supabase key only, reads only.

No GPU, local model, encoder or sealed package. The release it reads is the one the original system keeps active.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from backend.bintanong_agent.agent import Agent
from backend.bintanong_agent.corpus import Corpus
from backend.bintanong_agent.curriculum import CurriculumTools
from backend.bintanong_agent.providers import build_model
from backend.bintanong_agent.search import KeywordSearch
from backend.bintanong_agent.settings import AgentSettings
from backend.bintanong_agent.tools import ToolRunner
from backend.bintanong_orchestration.adapters import MultiCurriculumSymbolicAdapter, SymbolicAdapter
from backend.bintanong_private_context.sessions import SessionStore
from backend.bintanong_private_context.worker import extract_isolated
from backend.bintanong_runtime.hosted_curricula import load_release_curricula
from backend.bintanong_runtime.research import OPERATIONS, course_labels, research_catalog
from backend.bintanong_storage.client import SupabaseStorageClient
from backend.bintanong_storage.config import StorageConfig
from backend.bintanong_symbolic.bundle import prepare_runtime_bundle
from backend.bintanong_symbolic.runtime import CurriculumRuntime
from .agent_turns import AgentTurns
from .app import ApiServices, ApiSettings, create_app
from .auth import SupabaseAuth
from .chat import CurriculumOption
from .hosted_snapshot import load_document_snapshot
from .probes import probe_janus
from .research_app import _public_key

PAGE_ROWS = 1000  # the hosted API returns at most this many rows per request
PAGED_TABLES = {'source_spans': 'chunk_id,span_order'}  # table -> a stable order to page by
MAX_RUNNING_ANSWERS = 4  # hosted model calls are awaited, so a few answers can run at once
DISPLAY_NAMES = Path(__file__).resolve().parents[2] / 'knowledge' / 'manifests' / 'program-display-names.json'


def display_names() -> dict:
    """Program and curriculum titles for the picker; public titles, not institutional source content."""
    return json.loads(DISPLAY_NAMES.read_text(encoding='utf-8'))


class PagedReads:
    """Read-only view of the storage client that reads large tables in pages."""

    def __init__(self, client):
        self._client = client

    def select(self, table, columns='*', *, filters=None, role):
        if table not in PAGED_TABLES:
            return self._client.select(table, columns, filters=filters, role=role)
        rows = []
        while True:
            page = self._client.select(table, columns, role=role, filters={
                **(filters or {}), 'order': PAGED_TABLES[table], 'limit': str(PAGE_ROWS), 'offset': str(len(rows))})
            rows.extend(page)
            if len(page) < PAGE_ROWS:
                return rows


def _curriculum_tools(ledgers, authorization_ref):
    adapters, catalog, titles, labels = {}, [], {}, []
    for curriculum_id, ledger in sorted(ledgers.items()):
        bundle = prepare_runtime_bundle(ledger)
        runtime = CurriculumRuntime.for_offline_research(bundle, authorization=dict(
            purpose='offline_curriculum_acceptance', authorization_ref=authorization_ref,
            bundle_sha256=bundle['content_sha256'], operations=list(OPERATIONS)))
        adapters[curriculum_id] = SymbolicAdapter(runtime, research=True)
        catalog.extend(research_catalog(ledger))
        labels.extend(course_labels(ledger))
        titles.update({course['course_id']: course['facts']['course_title']['value']
                       for course in ledger['courses'] if 'course_title' in course.get('facts', {})})
    symbolic = MultiCurriculumSymbolicAdapter(adapters, release_id='hosted-agent', rule_bundle_version='hosted-agent')
    return CurriculumTools(symbolic, tuple(catalog), titles), dict(labels)


def _required(env, names, code):
    values = [env.get(name) for name in names]
    if not all(values):
        raise ValueError(code)
    return values


def load_agent_app(env=None, *, client=None, model=None, names=None):
    """Uvicorn factory. `client`, `model` and `names` are for tests; a deployment passes none of them."""
    env = os.environ if env is None else env
    names = display_names() if names is None else names
    program_names, curriculum_names = names.get('programs', {}), names.get('curricula', {})
    url, key = _required(env, ('SUPABASE_URL', 'SUPABASE_ANON_KEY'), 'agent_credentials_required')
    key = _public_key(key)  # a service-role key is refused before anything is read
    origins = tuple(origin.strip() for origin in env.get('BINTANONG_ALLOWED_ORIGINS', '').split(',') if origin.strip())
    if not origins:
        raise ValueError('allowed_origins_required')
    release_id, authorization_ref = _required(
        env, ('BINTANONG_RELEASE_ID', 'BINTANONG_RESEARCH_AUTHORIZATION'), 'release_required')
    model = model or build_model(AgentSettings.from_env(env))
    auth = SupabaseAuth(url, key)
    client = client or SupabaseStorageClient(StorageConfig(api_url=url, anon_key=key, service_role_key='', db_url=''))
    try:
        snapshot = load_document_snapshot(PagedReads(client), release_id=release_id,
                                          authorization_ref=authorization_ref)
        ledgers = load_release_curricula(client, release_id=release_id, authorization_ref=authorization_ref)
        if not ledgers:
            raise ValueError('reviewed_curricula_required')
        corpus = Corpus.from_snapshot(snapshot)
        curriculum, labels = _curriculum_tools(ledgers, authorization_ref)
        agent = Agent(model, ToolRunner(KeywordSearch(corpus), corpus, curriculum))
        curricula = tuple(CurriculumOption(
            ledger['scope']['program_id'], curriculum_id,
            program_names.get(ledger['scope']['program_id'], ledger['sources'][0]['filename']),
            curriculum_names.get(curriculum_id, ledger['sources'][0]['filename']))
            for curriculum_id, ledger in sorted(ledgers.items()))
        sessions = SessionStore()

        async def close():
            await asyncio.to_thread(client.close)

        async def ready():
            releases = await asyncio.to_thread(lambda: client.select(
                'knowledge_releases', filters={'release_id': 'eq.' + release_id}, role='runtime'))
            return bool(releases) and probe_janus()[0]

        services = ApiServices(
            sessions=sessions, curricula=curricula, turns=AgentTurns(sessions, agent, curricula, labels),
            course_labels=labels, auth=auth, close=close, ready=ready,
            extract_rows=lambda raw, program, curriculum_id: extract_isolated(
                raw, curriculum.catalog, program_id=program, curriculum_id=curriculum_id))
        return create_app(services, ApiSettings(
            allowed_origins=origins, require_auth=True, allow_guests=env.get('BINTANONG_ALLOW_GUESTS') == '1',
            max_running_answers=MAX_RUNNING_ANSWERS))
    except BaseException:
        client.close()
        raise
