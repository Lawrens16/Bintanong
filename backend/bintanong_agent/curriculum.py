"""Forgiving course lookup and thin read-only tools over the existing curriculum adapter.

The tools return plain dicts built only from what the symbolic result contains; the model words the answer.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import ValidationError

from ..bintanong_contracts.runtime import PredicateRequest
from ..bintanong_routing.contracts import RequestContext
from ..bintanong_symbolic.bundle import BLANK_CELL

MISSING_CURRICULUM = 'curriculum_not_in_release'
KNOWN_ERRORS = (MISSING_CURRICULUM, 'invalid_term_input')  # predictable results of bad model arguments
FALLBACK_SESSION = 'sess-agent-tools'  # only labels a request that carries no session facts
_EVALUATION = {'eligible': 'met', 'ineligible': 'not_met'}  # every other outcome stays unknown
_LOOKUP_ERRORS = {'not_found': 'course_not_found', 'not_reviewed': 'course_not_reviewed',
                  'unsupported': 'operation_unsupported'}


@dataclass(frozen=True)
class CourseMatch:
    course_id: str
    printed_code: str
    title: str | None


def _normalize_code(text: str) -> str:
    text = re.sub(r'\s*/\s*l\s*$', '', text.casefold())
    return re.sub(r'[\s\-.]+', '', text)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r'[a-z0-9]+', text.casefold()) if len(w) > 2}


def find_courses(catalog, curriculum_id: str, text: str, *, limit: int = 5,
                 titles: Mapping[str, str] | None = None) -> tuple[CourseMatch, ...]:
    """Candidates for loosely typed text: exact code, then code prefix, then title-word overlap."""
    titles = titles or {}
    query, query_words = _normalize_code(text), _words(text)
    if not query:
        return ()
    entries = sorted((e for e in catalog if e.kind == 'course' and e.curriculum_id == curriculum_id),
                     key=lambda e: e.course_code)
    exact = [e for e in entries if _normalize_code(e.course_code) == query]
    prefix = [e for e in entries if _normalize_code(e.course_code).startswith(query) and e not in exact]

    def overlap(entry):
        return len(query_words & _words(' '.join((titles.get(entry.entity_id, ''), *entry.aliases))))
    ranked = sorted((e for e in entries if e not in exact and e not in prefix and overlap(e)),
                    key=lambda e: -overlap(e))  # stable sort keeps printed-code order within a score
    return tuple(CourseMatch(e.entity_id, e.course_code, titles.get(e.entity_id))
                 for e in (*exact, *prefix, *ranked)[:limit])


class CurriculumTools:
    def __init__(self, symbolic, catalog, titles: Mapping[str, str] | None = None):
        self.symbolic, self.catalog, self.titles = symbolic, tuple(catalog), dict(titles or {})
        self._codes = {e.entity_id: e.course_code for e in self.catalog if e.kind == 'course'}

    def _code(self, course_id):
        return self._codes.get(course_id, course_id)

    async def _execute(self, predicate, curriculum_id, program_id, facts=(), **inputs):
        """The adapter result, or an {'error': code} dict for a known, recoverable failure."""
        names = {'curriculum_id': curriculum_id, **inputs}
        facts = tuple(facts)
        try:
            request = PredicateRequest.parse({'predicate': predicate, 'inputs': [
                {'name': name, 'value': value, 'fact_ref': None} for name, value in names.items()]})
            context = RequestContext.parse(dict(session_id=facts[0].session_id if facts else FALLBACK_SESSION,
                request_id='req-agent-tool', program_id=program_id, curriculum_id=curriculum_id,
                facts=[f.model_dump(mode='json') for f in facts]))
        except ValidationError:
            return {'error': 'invalid_arguments'}
        try:
            return await self.symbolic.execute(request, context)
        except ValueError as exc:
            if str(exc) not in KNOWN_ERRORS:
                raise
            return {'error': str(exc)}

    def _condition(self, text):
        """'reason:course-id' as {'course': printed code, 'reason': reason}; other text stays as the reason."""
        reason, _, course_id = text.partition(':')
        return {'course': self._code(course_id), 'reason': reason} if course_id else {'course': None, 'reason': text}

    def _printed_rule(self, view) -> str:
        kind = view.kind
        if kind == 'verified_none' or (kind == 'unresolved' and (view.reason or '').startswith(BLANK_CELL)):
            return 'None'  # a blank printed cell means no prerequisite (owner, 4 Nov 2026)
        if kind == 'course':
            return self._code(view.course_id)
        if kind == 'co_requisite':
            return f'{self._code(view.course_id)} (co-requisite)'
        if kind in ('all_of', 'any_of'):
            joiner = ' and ' if kind == 'all_of' else ' or '
            return '(' + joiner.join(self._printed_rule(item) for item in view.items) + ')'
        return view.reason or 'unresolved printed condition'

    async def prerequisite_check(self, curriculum_id, program_id, course_id, facts) -> dict:
        """All facts must belong to one session; the caller owns session scoping."""
        result = await self._execute('check_prerequisite_eligibility', curriculum_id, program_id, facts,
                                     course_id=course_id)
        if isinstance(result, dict):
            return result
        decision = result.decision
        limits = [] if decision.rule_coverage == 'verified' else [f'rule_coverage: {decision.rule_coverage}']
        limits += [f'conflict: {c}' for c in decision.unresolved_conflicts]
        if decision.error_code:
            limits.append(f'error: {decision.error_code}')
        if decision.outcome == 'unsupported':
            limits.append('rule check not supported for this course')
        return {'course': self._code(course_id),
                'printed_rule': None if result.requirement is None else self._printed_rule(result.requirement),
                'evaluation': _EVALUATION.get(decision.outcome, 'unknown'),
                'unmet': [self._condition(c) for c in decision.violated_conditions],
                'unknown_facts': [self._condition(c) for c in (*decision.missing_facts, *decision.unknown_conditions)],
                'limits': limits}

    async def _printed_courses(self, predicate, curriculum_id, program_id, **inputs):
        result = await self._execute(predicate, curriculum_id, program_id, **inputs)
        if isinstance(result, dict):
            return result, ()
        if result.status != 'complete':
            return {'error': _LOOKUP_ERRORS[result.status]}, ()
        return None, [dict(course_id=c.course_id, code=c.code, title=c.title, units=dict(c.units),
                           year=c.year, term=c.term, page=c.page) for c in result.courses]

    async def course_facts(self, curriculum_id, program_id, course_id) -> dict:
        error, courses = await self._printed_courses('course_facts', curriculum_id, program_id,
                                                     course_id=course_id)
        return error or courses[0]

    async def term_courses(self, curriculum_id, program_id, year, term) -> dict:
        error, courses = await self._printed_courses('list_term_courses', curriculum_id, program_id,
                                                     year_level=str(year), semester=term)
        return error or {'year': year, 'term': term, 'courses': courses}

    async def affected_courses(self, curriculum_id, program_id, course_id) -> dict:
        result = await self._execute('list_affected_courses', curriculum_id, program_id, course_id=course_id)
        if isinstance(result, dict):
            return result
        if result.status in ('unsupported', 'error'):
            return {'error': result.error_code or 'dependency_unsupported'}
        return {'course': self._code(course_id), 'complete': result.status == 'complete',
                'affected': [self._code(c) for c in result.course_ids],
                'unknown_conditions': [self._condition(c) for c in result.unknown_conditions],
                'printed_conditions': [[self._code(c), text] for c, text in result.printed_conditions]}
