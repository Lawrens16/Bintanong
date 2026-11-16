"""Chat turns for the hosted agent: the session's own exchanges are the history; one exchange per answered turn.

Same `prepare` / `run` surface as `ChatTurns`, and a reply shaped for the existing stream and source endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.bintanong_agent.agent import AgentAnswer
from backend.bintanong_agent.corpus import Passage
from backend.bintanong_agent.tools import TurnState
from backend.bintanong_api.chat import ChatTurns, PreparedTurn
from backend.bintanong_api.session import ApiError, Session
from backend.bintanong_private_context.dialogue import DialogueExchange, bounded_text

LANGUAGE_CODES = {'english': 'en', 'taglish': 'taglish'}  # the frontend's language codes
MAX_QUESTION_CHARS = 1000  # a longer question costs many times a normal one on the hosted model (16 Nov 2026)


@dataclass(frozen=True)
class _Locator:
    section_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Reference:
    filename: str
    page: int | None
    printed_page_label: str | None = None
    locator: _Locator = _Locator()


@dataclass(frozen=True)
class SourceCard:
    """One cited passage, with the fields `stream.answer_parts` and `sources.source_view` read."""
    evidence_id: str
    text: str
    citations: tuple[_Reference, ...]
    kind: str = 'document'


@dataclass(frozen=True)
class AgentReply:
    """An agent answer with the fields the existing stream reads from a candidate answer."""
    status: str
    language: str
    text: str
    citations: tuple[SourceCard, ...] = ()
    claims: tuple = ()
    missing_facts: tuple = ()
    decision: None = None
    reason: None = None
    structured_context: None = None


def _card(passage: Passage) -> SourceCard:
    # The frontend accepts source ids of the form ev-<64 hex>; reviewed chunk ids are 64-hex digests.
    return SourceCard('ev-' + passage.chunk_id, passage.text, (_Reference(passage.source, passage.page),))


def _reply(answer: AgentAnswer) -> AgentReply:
    return AgentReply(answer.status, LANGUAGE_CODES[answer.language], answer.text,
                      tuple(_card(passage) for passage in answer.citations))


def _ignore(_stage: str) -> None:
    pass


class AgentTurns(ChatTurns):
    def __init__(self, sessions, agent, curricula, course_labels=None):
        super().__init__(sessions, agent, curricula, course_labels=course_labels)
        self._agent = agent

    def prepare(self, request) -> PreparedTurn:
        turn = super().prepare(request)
        if len(turn.text) > MAX_QUESTION_CHARS:
            raise ApiError(422, 'message_too_long')
        return turn

    async def run(self, session: Session, turn: PreparedTurn, progress=_ignore) -> AgentReply:
        try:
            self._sessions.begin_turn(session.credential, turn.message_id, regenerate=turn.regenerate,
                                      account_id=session.account_id)
        except ValueError as refused:
            raise ApiError(409, str(refused)) from None
        except KeyError:  # deleted or expired after its cookie was resolved
            raise ApiError(409, 'session_ended') from None
        completed = False
        try:
            view = self._sessions.resolve(session.credential, account_id=session.account_id)
            if view is None:
                raise ApiError(409, 'session_ended')
            history = [message for exchange in view.dialogue.exchanges for message in (
                {'role': 'user', 'content': exchange.user_text},
                {'role': 'assistant', 'content': exchange.assistant_text})]
            facts = tuple(fact for fact in view.facts
                          if (fact.program_id, fact.curriculum_id) == (turn.program_id, turn.curriculum_id))
            state = TurnState(turn.program_id, turn.curriculum_id, facts)
            try:
                answer = await self._agent.answer(turn.text, history, state, progress)
            except Exception:
                raise ApiError(503, 'answer_unavailable') from None
            if answer.status != 'temporarily_unavailable':  # an outage notice is shown, never kept as history
                user_text, user_cut = bounded_text(turn.text)
                assistant_text, assistant_cut = bounded_text(answer.text)
                exchange = DialogueExchange(
                    message_id=turn.message_id, user_text=user_text, program_id=turn.program_id,
                    curriculum_id=turn.curriculum_id, assistant_text=assistant_text, answer_status=answer.status,
                    source_refs=tuple(passage.short_id for passage in answer.citations)[:32],
                    text_truncated=user_cut or assistant_cut)
                try:
                    self._sessions.commit_turn_result(
                        session.credential, turn.message_id, expected_revision=view.dialogue.revision,
                        exchange=exchange, conversation=view.conversation, account_id=session.account_id)
                except (ValueError, KeyError):
                    raise ApiError(409, 'conversation_changed') from None
                completed = True
        finally:
            if not completed:  # a failed, cancelled or unavailable turn commits nothing
                self._sessions.end_turn(session.credential, turn.message_id, completed=False,
                                        account_id=session.account_id)
        return _reply(answer)
