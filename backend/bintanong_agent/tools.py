"""The tools the model may call. Results are JSON text; bad model input comes back as {"error": code}."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .corpus import Corpus, Passage
from .curriculum import CurriculumTools, find_courses
from .search import MAX_TOP_K, SearchBackend

TOPIC_PASSAGE_LIMIT = 12
TERMS = ['first_semester', 'second_semester', 'summer', 'any']

# name -> (description, required arguments, optional arguments); an argument is name -> (JSON type, description)
_COURSE_ID = {'course_id': ('string', 'A course_id returned by find_course.')}
TOOL_SPECS = {
    'search_documents': (
        'Keyword search over the reviewed university documents. Returns passages with ids to cite.',
        {'query': ('string', 'Search words. English source terms work best.')},
        {'top_k': ('integer', f'How many passages to return, 1 to {MAX_TOP_K}.')}),
    'open_topic': (
        'Read the passages of one topic from the topic directory.',
        {'topic_id': ('string', 'A topic id exactly as listed in the topic directory.')}, {}),
    'find_course': (
        "Find courses in the student's curriculum from loosely typed text (a code such as cc5 or a title).",
        {'text': ('string', 'The course as the student typed it.')}, {}),
    'check_prerequisite': (
        "The printed prerequisite rule of a course and its evaluation against the student's known course facts.",
        _COURSE_ID, {}),
    'course_facts': ('Printed facts of one course: code, title, units, year and term.', _COURSE_ID, {}),
    'list_term_courses': (
        'Courses printed for one year level and term of the curriculum.',
        {'year': ('integer', 'Year level, for example 2.'), 'term': ('string', 'One of: ' + ', '.join(TERMS) + '.')},
        {}),
    'list_affected_courses': ('Courses whose printed prerequisites depend on the given course.', _COURSE_ID, {}),
}
DOCUMENT_TOOLS = ('search_documents', 'open_topic')
_PYTHON_TYPES = {'string': str, 'integer': int}


def _schema(name: str) -> dict:
    description, required, optional = TOOL_SPECS[name]
    properties = {argument: {'type': kind, 'description': text}
                  for argument, (kind, text) in {**required, **optional}.items()}
    return {'type': 'function', 'function': {'name': name, 'description': description, 'parameters': {
        'type': 'object', 'properties': properties, 'required': list(required)}}}


def _valid(value, kind: str) -> bool:
    if type(value) is not _PYTHON_TYPES[kind]:  # bool is not an integer here
        return False
    return bool(value.strip()) if kind == 'string' else True


def _checked_arguments(name: str, arguments) -> dict | None:
    _, required, optional = TOOL_SPECS[name]
    if not isinstance(arguments, dict) or not required.keys() <= arguments.keys():
        return None
    known = {**required, **optional}
    chosen = {argument: value for argument, value in arguments.items() if argument in known}
    return chosen if all(_valid(value, known[argument][0]) for argument, value in chosen.items()) else None


@dataclass
class TurnState:
    """One session's scope plus what the tools fetched and checked during the current turn."""
    program_id: str | None = None
    curriculum_id: str | None = None
    facts: tuple = ()
    fetched: dict[str, Passage] = field(default_factory=dict)
    rule_checks: list[dict] = field(default_factory=list)


def _passage_view(passage: Passage) -> dict:
    return {'id': passage.short_id, 'title': passage.title, 'source': passage.source, 'page': passage.page,
            'text': passage.text, 'limits': list(passage.limits)}


class ToolRunner:
    def __init__(self, search: SearchBackend, corpus: Corpus, curriculum: CurriculumTools):
        self.search, self.corpus, self.curriculum = search, corpus, curriculum
        self.schemas = [_schema(name) for name in TOOL_SPECS]
        self._topics = {topic.topic_id: topic for topic in corpus.topics}
        self._codes = {entry.entity_id: entry.course_code for entry in curriculum.catalog if entry.kind == 'course'}

    def fact_lines(self, state: TurnState) -> tuple[str, ...]:
        """The student's known course facts by printed code; no session or fact ids."""
        return tuple(f'{self._codes.get(fact.course_id, fact.course_id)}: {fact.state}' for fact in state.facts)

    async def run(self, name: str, arguments: dict, state: TurnState) -> str:
        if name not in TOOL_SPECS:
            return json.dumps({'error': 'unknown_tool'})
        checked = _checked_arguments(name, arguments)
        if checked is None:
            result = {'error': 'invalid_arguments'}
        elif name not in DOCUMENT_TOOLS and not (state.curriculum_id and state.program_id):
            result = {'error': 'scope_needed'}
        else:
            result = await getattr(self, '_' + name)(state, **checked)
        return json.dumps(result, ensure_ascii=False)

    def _fetch(self, state: TurnState, passages) -> list[dict]:
        state.fetched.update({passage.short_id: passage for passage in passages})
        return [_passage_view(passage) for passage in passages]

    async def _search_documents(self, state, query, top_k=MAX_TOP_K):
        found = await self.search.search(query, top_k=top_k)
        return {'passages': self._fetch(state, self.corpus.with_neighbours(p.short_id for p in found))}

    async def _open_topic(self, state, topic_id):
        topic = self._topics.get(topic_id)
        if topic is None:
            return {'error': 'unknown_topic'}
        passage_ids = topic.passage_ids[:TOPIC_PASSAGE_LIMIT]
        result = {'passages': self._fetch(state, [self.corpus.get(short_id) for short_id in passage_ids])}
        if len(topic.passage_ids) > TOPIC_PASSAGE_LIMIT:
            result['note'] = f'Only the first {TOPIC_PASSAGE_LIMIT} of {len(topic.passage_ids)} passages are shown.'
        return result

    async def _find_course(self, state, text):
        matches = find_courses(self.curriculum.catalog, state.curriculum_id, text, titles=self.curriculum.titles)
        return {'candidates': [{'course_id': match.course_id, 'printed_code': match.printed_code,
                                'title': match.title} for match in matches]}

    async def _check_prerequisite(self, state, course_id):
        result = await self.curriculum.prerequisite_check(state.curriculum_id, state.program_id, course_id,
                                                          state.facts)
        if 'error' not in result:
            state.rule_checks.append(result)
        return result

    async def _course_facts(self, state, course_id):
        return await self.curriculum.course_facts(state.curriculum_id, state.program_id, course_id)

    async def _list_term_courses(self, state, year, term):
        return await self.curriculum.term_courses(state.curriculum_id, state.program_id, year, term)

    async def _list_affected_courses(self, state, course_id):
        return await self.curriculum.affected_courses(state.curriculum_id, state.program_id, course_id)
