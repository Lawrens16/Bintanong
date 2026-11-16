import asyncio
import importlib
import json
from types import SimpleNamespace

from backend.bintanong_agent.corpus import Corpus
from backend.bintanong_agent.search import KeywordSearch
from backend.bintanong_routing.contracts import ScopedFact

CURRICULUM, PROGRAM, SESSION = 'curriculum-synthetic-1', 'program-synthetic', 'sess-agent-loop-test'
RULE_RESULT = {'course': 'SYN 104/L', 'printed_rule': 'SYN 100', 'evaluation': 'unknown', 'unmet': [],
               'unknown_facts': [{'course': 'SYN 100', 'reason': 'completion_unknown'}], 'limits': []}


def tools_module():
    return importlib.import_module('backend.bintanong_agent.tools')


def make_chunk(chunk_id, reading_id, body):
    return {'chunk_id': chunk_id, 'chunk_type': 'policy', 'version_id': 'v1', 'source_label': 'Synthetic.pdf',
            'type_fields': {'reading_id': reading_id, 'source_limits': [], 'required_neighbor_chunk_ids': []},
            'spans': [{'page': 3}],
            'text': json.dumps({'fields': [{'name': 'body', 'source_blank': False, 'value': body}]})}


def make_corpus():
    # Short ids follow chunk-id order: C001 library, C002 and C003 fees.
    return Corpus.from_snapshot({'versions': {}, 'chunks': [
        make_chunk('a', 'LIB1', 'Library books are due in seven days.'),
        make_chunk('b', 'FEES1', 'Pay the enrolment fee at the cashier.'),
        make_chunk('c', 'FEES2', 'Keep the cashier receipt after paying.')]})


class FakeCurriculum:
    """Stands in for CurriculumTools: same attributes and coroutine names, canned results."""

    def __init__(self, rule_result=None):
        self.catalog = tuple(SimpleNamespace(kind='course', curriculum_id=CURRICULUM, course_code=code,
                                             entity_id=course_id, aliases=())
                             for course_id, code in (('course-syn-100', 'SYN 100'), ('course-syn-104', 'SYN 104/L')))
        self.titles = {'course-syn-100': 'Fictional Base', 'course-syn-104': 'Fictional Structures'}
        self.rule_result = RULE_RESULT if rule_result is None else rule_result
        self.calls = []

    async def prerequisite_check(self, curriculum_id, program_id, course_id, facts):
        self.calls.append(('prerequisite_check', curriculum_id, program_id, course_id, tuple(facts)))
        return self.rule_result

    async def course_facts(self, curriculum_id, program_id, course_id):
        self.calls.append(('course_facts', curriculum_id, program_id, course_id))
        return {'course_id': course_id, 'code': 'SYN 104/L', 'title': 'Fictional Structures'}

    async def term_courses(self, curriculum_id, program_id, year, term):
        self.calls.append(('term_courses', curriculum_id, program_id, year, term))
        return {'year': year, 'term': term, 'courses': []}

    async def affected_courses(self, curriculum_id, program_id, course_id):
        self.calls.append(('affected_courses', curriculum_id, program_id, course_id))
        return {'course': 'SYN 100', 'complete': True, 'affected': ['SYN 104/L']}


def passed_fact():
    return ScopedFact.parse(dict(fact_id='fact-syn-100', session_id=SESSION, program_id=PROGRAM,
                                 curriculum_id=CURRICULUM, course_id='course-syn-100', state='passed'))


def make_runner(curriculum=None):
    corpus = make_corpus()
    return tools_module().ToolRunner(KeywordSearch(corpus), corpus, curriculum or FakeCurriculum())


def make_state(chosen=True, facts=()):
    return tools_module().TurnState(PROGRAM if chosen else None, CURRICULUM if chosen else None, tuple(facts))


def call(runner, name, arguments, state):
    return json.loads(asyncio.run(runner.run(name, arguments, state)))


def test_schemas_name_the_seven_tools():
    names = [schema['function']['name'] for schema in make_runner().schemas]
    assert names == ['search_documents', 'open_topic', 'find_course', 'check_prerequisite', 'course_facts',
                     'list_term_courses', 'list_affected_courses']
    assert all(schema['type'] == 'function' and schema['function']['parameters']['type'] == 'object'
               for schema in make_runner().schemas)


def test_search_tool_records_fetched_passages():
    runner, state = make_runner(), make_state()
    result = call(runner, 'search_documents', {'query': 'where do I pay the enrolment fee'}, state)
    first = result['passages'][0]
    assert first['id'] == 'C002' and 'enrolment fee' in first['text']
    assert first['source'] == 'Synthetic.pdf' and first['page'] == 3
    assert set(state.fetched) == {p['id'] for p in result['passages']}
    assert state.fetched['C002'].chunk_id == 'b'


def test_search_with_no_match_returns_an_empty_list():
    runner, state = make_runner(), make_state()
    assert call(runner, 'search_documents', {'query': 'zebra'}, state) == {'passages': []}
    assert state.fetched == {}


def test_open_topic_returns_topic_passages_and_records_them():
    runner, state = make_runner(), make_state()
    result = call(runner, 'open_topic', {'topic_id': 'FEES'}, state)
    assert [p['id'] for p in result['passages']] == ['C002', 'C003']
    assert set(state.fetched) == {'C002', 'C003'}
    assert call(runner, 'open_topic', {'topic_id': 'NOPE'}, state) == {'error': 'unknown_topic'}


def test_open_topic_says_when_a_long_topic_is_cut():
    corpus = Corpus.from_snapshot({'versions': {}, 'chunks': [
        make_chunk(f'k{number:02d}', f'LONG{number}', f'Step {number} of the long procedure.') for number in range(15)]})
    runner, state = tools_module().ToolRunner(KeywordSearch(corpus), corpus, FakeCurriculum()), make_state()
    result = call(runner, 'open_topic', {'topic_id': 'LONG'}, state)
    assert len(result['passages']) == 12 and len(state.fetched) == 12
    assert '12 of 15' in result['note']
    assert 'note' not in call(make_runner(), 'open_topic', {'topic_id': 'FEES'}, make_state())


def test_search_adds_required_neighbour_passages():
    # A service-table step is read together with the passage it requires, even when only one matches.
    step = make_chunk('s1', 'SVC1', 'Submit the clearance form.')
    step['type_fields']['required_neighbor_chunk_ids'] = ['s2']
    corpus = Corpus.from_snapshot({'versions': {}, 'chunks': [step, make_chunk('s2', 'SVC2', 'Processing takes a week.')]})
    runner, state = tools_module().ToolRunner(KeywordSearch(corpus), corpus, FakeCurriculum()), make_state()
    result = call(runner, 'search_documents', {'query': 'clearance form'}, state)
    assert [p['id'] for p in result['passages']] == ['C001', 'C002']
    assert set(state.fetched) == {'C001', 'C002'}


def test_unknown_tool_name_returns_error_json():
    assert call(make_runner(), 'delete_everything', {}, make_state()) == {'error': 'unknown_tool'}


def test_bad_arguments_return_error_json():
    runner, state = make_runner(), make_state()
    bad_calls = [('search_documents', {}), ('search_documents', {'query': 7}), ('search_documents', {'query': ' '}),
                 ('search_documents', {'query': 'fee', 'top_k': 'many'}), ('open_topic', {'topic': 'FEES'}),
                 ('check_prerequisite', {'course_id': None}), ('list_term_courses', {'year': 'two', 'term': 'any'}),
                 ('list_term_courses', {'year': True, 'term': 'any'}), ('search_documents', ['fee'])]
    for name, arguments in bad_calls:
        assert call(runner, name, arguments, state) == {'error': 'invalid_arguments'}, (name, arguments)
    assert state.fetched == {} and runner.curriculum.calls == []


def test_check_prerequisite_without_curriculum_returns_scope_needed():
    runner, state = make_runner(), make_state(chosen=False)
    for name, arguments in [('check_prerequisite', {'course_id': 'course-syn-104'}), ('find_course', {'text': 'syn104'}),
                            ('course_facts', {'course_id': 'course-syn-104'}),
                            ('list_term_courses', {'year': 2, 'term': 'first_semester'}),
                            ('list_affected_courses', {'course_id': 'course-syn-100'})]:
        assert call(runner, name, arguments, state) == {'error': 'scope_needed'}, name
    assert runner.curriculum.calls == [] and state.rule_checks == []


def test_find_course_returns_candidates_for_loose_text():
    result = call(make_runner(), 'find_course', {'text': 'syn-104'}, make_state())
    assert result == {'candidates': [{'course_id': 'course-syn-104', 'printed_code': 'SYN 104/L',
                                      'title': 'Fictional Structures'}]}


def test_check_prerequisite_uses_session_scope_and_records_the_rule_check():
    runner, state = make_runner(), make_state(facts=(passed_fact(),))
    result = call(runner, 'check_prerequisite', {'course_id': 'course-syn-104'}, state)
    assert result == RULE_RESULT
    assert runner.curriculum.calls == [('prerequisite_check', CURRICULUM, PROGRAM, 'course-syn-104', state.facts)]
    assert state.rule_checks == [RULE_RESULT]


def test_check_prerequisite_passes_results_the_student_stated_in_chat():
    runner, state = make_runner(), make_state()
    call(runner, 'check_prerequisite', {'course_id': 'course-syn-104', 'student_results': [
        {'course_id': 'course-syn-100', 'state': 'passed'}]}, state)
    (stated,) = runner.curriculum.calls[0][4]
    assert (stated.course_id, stated.state, stated.source) == ('course-syn-100', 'passed', 'user_statement')
    assert (stated.program_id, stated.curriculum_id) == (PROGRAM, CURRICULUM)
    assert state.facts == ()  # a stated result is used for this check only


def test_stated_results_join_the_confirmed_upload_facts_of_the_same_session():
    runner, state = make_runner(), make_state(facts=(passed_fact(),))
    call(runner, 'check_prerequisite', {'course_id': 'course-syn-104', 'student_results': [
        {'course_id': 'course-syn-100', 'state': 'failed'}, {'course_id': 'course-syn-104', 'state': 'enrolled'}]},
         state)
    facts = runner.curriculum.calls[0][4]
    assert {f.session_id for f in facts} == {SESSION}
    # The confirmed upload is kept beside the disagreeing statement, so the rule check reports the conflict.
    assert sorted((f.course_id, f.state, f.source) for f in facts) == [
        ('course-syn-100', 'failed', 'user_statement'), ('course-syn-100', 'passed', None),
        ('course-syn-104', 'enrolled', 'user_statement')]


def test_bad_stated_results_return_error_json():
    runner, state = make_runner(), make_state()
    for results in ('passed', [{'course_id': 'course-syn-100'}], [{'course_id': 'course-syn-100', 'state': 'aced'}],
                    [{'course_id': 5, 'state': 'passed'}], ['course-syn-100'],
                    [{'course_id': 'Not An Id', 'state': 'passed'}]):
        arguments = {'course_id': 'course-syn-104', 'student_results': results}
        assert call(runner, 'check_prerequisite', arguments, state) == {'error': 'invalid_arguments'}, results
    assert runner.curriculum.calls == []


def test_check_prerequisite_schema_offers_optional_student_results():
    schema = next(s['function'] for s in make_runner().schemas if s['function']['name'] == 'check_prerequisite')
    results = schema['parameters']['properties']['student_results']
    assert results['type'] == 'array' and schema['parameters']['required'] == ['course_id']
    assert results['items']['properties']['state']['enum'] == ['passed', 'failed', 'enrolled', 'not_taken']


def test_failed_rule_check_is_not_recorded():
    runner, state = make_runner(FakeCurriculum({'error': 'course_not_found'})), make_state()
    assert call(runner, 'check_prerequisite', {'course_id': 'course-zzz'}, state) == {'error': 'course_not_found'}
    assert state.rule_checks == []


def test_other_curriculum_tools_pass_the_session_scope():
    runner, state = make_runner(), make_state()
    call(runner, 'course_facts', {'course_id': 'course-syn-104'}, state)
    call(runner, 'list_term_courses', {'year': 2, 'term': 'first_semester'}, state)
    call(runner, 'list_affected_courses', {'course_id': 'course-syn-100'}, state)
    assert runner.curriculum.calls == [('course_facts', CURRICULUM, PROGRAM, 'course-syn-104'),
                                       ('term_courses', CURRICULUM, PROGRAM, 2, 'first_semester'),
                                       ('affected_courses', CURRICULUM, PROGRAM, 'course-syn-100')]


def test_fact_lines_name_printed_codes_without_private_ids():
    lines = make_runner().fact_lines(make_state(facts=(passed_fact(),)))
    assert lines == ('SYN 100: passed',)
