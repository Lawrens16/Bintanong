"""One chat turn: model, tools, final reply, guards. Nothing here logs questions, facts or replies."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from ..bintanong_routing.transport import RuntimeFailure
from . import guards
from .corpus import Passage
from .prompt import Scope, build_messages, repair_message
from .providers import ChatModel, ModelTurn, Usage
from .tools import DOCUMENT_TOOLS, ToolRunner, TurnState

STATUS_OF_KIND = {'answer': 'answered', 'chat': 'answered', 'clarify': 'clarification_needed',
                  'out_of_scope': 'out_of_scope'}
LANGUAGES = ('english', 'taglish')
REPAIRABLE_FAILURE = 'invalid_server_response'  # e.g. tool arguments that are not valid JSON


@dataclass(frozen=True)
class AgentAnswer:
    status: Literal['answered', 'clarification_needed', 'out_of_scope', 'insufficient_evidence',
                    'temporarily_unavailable']
    text: str
    language: Literal['english', 'taglish']
    citations: tuple[Passage, ...] = ()
    used_rules: bool = False
    usage: Usage = field(default_factory=Usage)  # every model call of this answer


def parse_final(text: str) -> dict | None:
    """The model's final JSON object with defaults filled in, or None when it has another shape."""
    try:
        final = json.loads(text[text.find('{'):text.rfind('}') + 1])
    except ValueError:
        return None
    if not isinstance(final, dict):
        return None
    final = {'citations': [], 'eligibility': False, **final}
    valid = (final.get('kind') in STATUS_OF_KIND and isinstance(final.get('text'), str) and final['text'].strip()
             and isinstance(final['citations'], list) and all(isinstance(c, str) for c in final['citations'])
             and isinstance(final['eligibility'], bool))
    return final if valid else None


def _assistant_message(turn: ModelTurn) -> dict:
    return {'role': 'assistant', 'content': turn.text, 'tool_calls': [
        {'id': call.id, 'type': 'function',
         'function': {'name': call.name, 'arguments': json.dumps(call.arguments, ensure_ascii=False)}}
        for call in turn.tool_calls]}


class Agent:
    def __init__(self, model: ChatModel, tools: ToolRunner, *, max_rounds: int = 6):
        self.model, self.tools, self.max_rounds = model, tools, max_rounds

    async def answer(self, question: str, history: list[dict], state: TurnState,
                     progress=lambda stage: None) -> AgentAnswer:
        language = guards.reply_language(question)
        if guards.excluded_audience(question):
            return AgentAnswer('out_of_scope', guards.SCOPE_NOTICE[language], language)
        state.fetched, state.rule_checks = {}, []  # citations and rule checks count for this turn only
        scope = Scope(self.tools.corpus.directory(), state.program_id, state.curriculum_id,
                      self.tools.fact_lines(state))
        messages = build_messages(history, question, scope)
        stages = []

        def report(stage):
            if stages[-1:] != [stage]:
                stages.append(stage)
                progress(stage)

        repaired = retried = False
        usage = Usage()
        for _ in range(self.max_rounds):
            try:
                turn = await self.model.complete(messages, self.tools.schemas)
            except RuntimeFailure as failure:
                if str(failure) == REPAIRABLE_FAILURE and not retried:
                    retried = True
                    continue
                return AgentAnswer('temporarily_unavailable', guards.UNAVAILABLE_REPLY[language], language,
                                   usage=usage)
            usage += turn.usage
            if turn.tool_calls:
                messages.append(_assistant_message(turn))
                for call in turn.tool_calls:
                    report('searching' if call.name in DOCUMENT_TOOLS else 'checking')
                    result = await self.tools.run(call.name, call.arguments, state)
                    messages.append({'role': 'tool', 'tool_call_id': call.id, 'content': result})
                report('writing')
                continue
            final, errors = self._checked(turn.text, state)
            if not errors:
                return AgentAnswer(
                    STATUS_OF_KIND[final['kind']], final['text'],
                    final['language'] if final.get('language') in LANGUAGES else language,
                    tuple(state.fetched[short_id] for short_id in dict.fromkeys(final['citations'])),
                    bool(state.rule_checks), usage)
            if repaired:
                break
            repaired = True
            messages += [{'role': 'assistant', 'content': turn.text},
                         {'role': 'user', 'content': repair_message(errors)}]
            report('writing')
        return AgentAnswer('insufficient_evidence', guards.FALLBACK_REPLY[language], language, usage=usage)

    @staticmethod
    def _checked(text: str, state: TurnState) -> tuple[dict | None, list[str]]:
        final = parse_final(text)
        if final is None:
            return None, ['invalid_final']
        errors = guards.citation_errors(final, state) + guards.eligibility_errors(final, state)
        if not errors and guards.private_leak([state.fetched[c] for c in final['citations']], state):
            errors = ['private_leak']
        return final, errors
