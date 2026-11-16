"""Student-facing HTTP API (master 16.1). Session and origin rules live in `session.py`."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from backend.bintanong_api.admission import AdmittedStream, AnswerAdmission
from backend.bintanong_api.rate_limit import (CLIENT_COOKIE, CLIENT_COOKIE_MAX_AGE, QuestionRateLimit,
                                              admit_together, client_id)
from backend.bintanong_api.auth import authorize
from backend.bintanong_api.chat import ChatRequest, ChatTurns, CurriculumOption
from backend.bintanong_api.main import HealthStatus, dependency_health, health_live, health_ready
from backend.bintanong_api.session import SESSION_COOKIE, ApiError, Session, check_origin, require_session
from backend.bintanong_api.sources import SourceRegistry, source_view
from backend.bintanong_api.stream import STREAM_HEADERS, chat_stream
from backend.bintanong_api.uploads import upload_router
from backend.bintanong_private_context.sessions import SessionStore
from backend.bintanong_private_context.uploads import MAX_UPLOAD_BYTES

__all__ = ['ApiServices', 'ApiSettings', 'create_app', 'require_session']


@dataclass(frozen=True)
class ApiSettings:
    allowed_origins: tuple[str, ...]
    max_upload_bytes: int = MAX_UPLOAD_BYTES
    max_parallel_uploads: int = 2  # each upload starts a parser process
    max_running_answers: int = 1  # Gemma serves one request at a time (`--parallel 1`)
    max_waiting_answers: int = 4
    max_questions_per_window: int = 5  # per person (account, or guest browser); owner 3 Nov 2026
    question_window_seconds: int = 300
    max_questions_per_day: int | None = None  # per person, rolling 24 hours; None = no daily limit
    max_questions_per_day_total: int | None = None  # everyone together; hosted fork (owner, 16 Nov 2026)
    max_request_bytes: int | None = None  # refuse a larger or unsized request body before reading it
    api_docs: bool = True  # False serves no /openapi.json, /docs or /redoc
    require_auth: bool = False  # trusted offline/test compositions preserve their existing contract
    allow_guests: bool = False  # explicit access policy; supplied credentials still require verification


@dataclass(frozen=True)
class ApiServices:
    sessions: SessionStore
    curricula: tuple[CurriculumOption, ...] = ()
    pipeline: object = None  # run(text, context, *, routed_sink, progress) -> CandidateAnswer
    extract_rows: object = None  # (raw bytes, program_id, curriculum_id) -> ExtractionResult; parses; blocking
    course_labels: Mapping[str, str] = field(default_factory=dict)  # course id -> printed code
    sources: SourceRegistry = field(default_factory=SourceRegistry)
    auth: object = None
    close: object = None
    ready: object = None
    supabase_probe: object = None  # hosted storage readiness (co-worker composition)
    evaluation: object = None  # gated benchmark runs; only a trusted launcher sets this
    turns: object = None  # a ChatTurns replacement (the hosted agent); None keeps the pipeline turns
    uploads: bool = True  # False leaves out the grade-upload routes (hosted agent, owner 15 Nov 2026)


def create_app(services: ApiServices, settings: ApiSettings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            if services.close is not None:
                await services.close()
    app = FastAPI(title='Bintanong API', version='0.0.0', lifespan=lifespan,
                  openapi_url='/openapi.json' if settings.api_docs else None,
                  dependencies=[Depends(check_origin), Depends(authorize)])
    app.state.services, app.state.settings = services, settings
    turns = services.turns or ChatTurns(services.sessions, services.pipeline, services.curricula,
                                        course_labels=services.course_labels)
    app.state.admission = admission = AnswerAdmission(running=settings.max_running_answers,
                                                      waiting=settings.max_waiting_answers)
    app.state.question_limit = question_limit = QuestionRateLimit(limit=settings.max_questions_per_window,
                                                                  window_seconds=settings.question_window_seconds)
    day = 24 * 60 * 60
    person_day_limit = (None if settings.max_questions_per_day is None else
                        QuestionRateLimit(limit=settings.max_questions_per_day, window_seconds=day))
    site_day_limit = (None if settings.max_questions_per_day_total is None else
                      QuestionRateLimit(limit=settings.max_questions_per_day_total, window_seconds=day))
    if services.uploads:
        app.include_router(upload_router(services, turns, settings.max_upload_bytes, settings.max_parallel_uploads))
    if services.evaluation is not None:
        app.include_router(services.evaluation.router(admission))
    app.add_api_route('/health/live', health_live, methods=['GET'])
    if services.supabase_probe is not None:
        @app.get('/health/ready')
        async def student_ready(response: Response):
            status = await dependency_health(response, supabase_probe=services.supabase_probe)
            try:
                ok = bool(services.pipeline is not None and (services.ready is None or await services.ready()))
            except Exception:
                ok = False
            status.probes['student_runtime'] = ok
            if not ok:
                status.errors['student_runtime'] = 'research runtime unavailable'
                status.status = 'degraded'
                response.status_code = 503
            return status
    elif services.ready is None:
        app.add_api_route('/health/ready', health_ready, methods=['GET'])
    else:
        @app.get('/health/ready')
        async def research_ready(response: Response):
            try:
                available = bool(await services.ready())
            except Exception:
                available = False
            if not available:
                response.status_code = 503
            return HealthStatus(status='ready' if available else 'degraded',
                probes={'student_runtime': available},
                errors={} if available else {'student_runtime': 'research runtime unavailable'})

    @app.exception_handler(ApiError)
    async def api_error(_request: Request, error: ApiError):
        if error.retry_after is None:
            return JSONResponse({'error': error.code}, status_code=error.status)
        return JSONResponse({'error': error.code, 'retryAfter': error.retry_after}, status_code=error.status,
                            headers={'Retry-After': str(error.retry_after)})

    @app.middleware('http')
    async def attach_session_cookie(request: Request, call_next):
        response = await call_next(request)
        credential = getattr(request.state, 'issued_credential', None)
        if credential is not None:
            response.set_cookie(SESSION_COOKIE, credential, httponly=True, secure=True, samesite='strict',
                                path='/')
        browser = getattr(request.state, 'issued_client', None)
        if browser is not None:
            response.set_cookie(CLIENT_COOKIE, browser, max_age=CLIENT_COOKIE_MAX_AGE, httponly=True, secure=True,
                                samesite='strict', path='/')
        return response

    if settings.max_request_bytes is not None:
        @app.middleware('http')
        async def refuse_large_requests(request: Request, call_next):
            # FastAPI reads the whole body before any dependency runs, so the size is checked here first.
            if request.method in ('POST', 'PUT', 'PATCH'):
                length = request.headers.get('content-length')
                if length is None:
                    return JSONResponse({'error': 'length_required'}, status_code=411)
                if not length.isdigit() or int(length) > settings.max_request_bytes:
                    return JSONResponse({'error': 'request_too_large'}, status_code=413)
            return await call_next(request)

    @app.post('/chat')
    def chat(body: ChatRequest, request: Request, session: Session = Depends(require_session)) -> AdmittedStream:
        turn = turns.prepare(body)
        identity = ('account:' + session.account_id if session.account_id is not None
                    else 'guest:' + session.view.session_id)
        if session.account_id is not None:
            person = 'account:' + session.account_id
        else:
            browser, issued = client_id(request.cookies.get(CLIENT_COOKIE))
            if issued:
                request.state.issued_client = browser
            person = 'browser:' + browser
        reservation = admission.reserve(account_id=identity)
        # Counted only once admitted, so a busy refusal never uses the person's quota.
        limits = [(question_limit, person, 'rate_limited')]
        if person_day_limit is not None:
            limits.append((person_day_limit, person, 'daily_limit_reached'))
        if site_day_limit is not None:
            limits.append((site_day_limit, 'everyone', 'site_limit_reached'))
        refused = admit_together(limits)
        if refused is not None:
            reservation.release()
            raise ApiError(429, refused[0], retry_after=refused[1])
        # Last: no raises after the reservation is handed to the response.
        return AdmittedStream(chat_stream(turns, session, turn, services.sources, reservation,
                                          services.course_labels), reservation,
                              media_type='text/event-stream', headers=STREAM_HEADERS)

    @app.get('/sources/{source_id}')
    def source(source_id: str) -> dict:
        card = services.sources.get(source_id)
        if card is None:
            raise ApiError(404, 'unknown_source')
        return source_view(card)

    @app.get('/curricula')
    def curricula() -> dict:
        return {'curricula': [dict(programId=c.program_id, curriculumId=c.curriculum_id,
                                   programName=c.program_name, curriculumName=c.curriculum_name)
                              for c in services.curricula]}

    @app.delete('/session', status_code=204)
    def delete_session(request: Request) -> Response:
        services.sessions.delete(request.cookies.get(SESSION_COOKIE),
                                 account_id=getattr(request.state, 'account_id', None))
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, httponly=True, secure=True, samesite='strict', path='/')
        return response

    return app
