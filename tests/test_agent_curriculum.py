import asyncio
import importlib
import json
from unittest import mock

import pytest

import test_planning_check as planning
from backend.bintanong_orchestration.adapters import SymbolicAdapter
from backend.bintanong_routing.contracts import ScopedFact
from backend.bintanong_runtime.research import research_catalog
from backend.bintanong_symbolic.runtime import CurriculumRuntime

SYNTHETIC, UNFAMILIAR = 'curriculum-synthetic-1', 'curriculum-unfamiliar-9'
SESSION = 'sess-agent-test'


def curriculum_module():
    return importlib.import_module('backend.bintanong_agent.curriculum')


def synthetic_ledger(curriculum_id):
    with mock.patch.object(planning, 'CurriculumRuntime', lambda ledger: ledger):
        return planning.build(curriculum_id)


def titles_of(ledger):
    return {c['course_id']: c['facts']['course_title']['value'] for c in ledger['courses']}


@pytest.fixture(scope='module')
def unfamiliar_catalog():
    return research_catalog(synthetic_ledger(UNFAMILIAR))


@pytest.fixture(scope='module')
def tools():
    ledger = synthetic_ledger(SYNTHETIC)
    adapter = SymbolicAdapter(CurriculumRuntime(ledger))
    return curriculum_module().CurriculumTools(adapter, research_catalog(ledger), titles_of(ledger))


def course_id(name):
    return planning.cid(planning.CURRICULA[SYNTHETIC][name])


def fact(name, state):
    return ScopedFact.parse(dict(fact_id='fact-' + name.lower().replace('_', '-'), session_id=SESSION,
        program_id='program-synthetic', curriculum_id=SYNTHETIC, course_id=course_id(name), state=state))


def run(awaitable):
    return asyncio.run(awaitable)


@pytest.mark.parametrize('text', ['qzva0', 'QZV-A0', 'qzv a0/l', 'QZV A0/L', 'qzv.a0'])
def test_find_courses_ignores_spacing_dash_and_lab_suffix(unfamiliar_catalog, text):
    found = curriculum_module().find_courses(unfamiliar_catalog, UNFAMILIAR, text)
    assert found[0].printed_code == 'QZV-A0/L'
    assert found[0].course_id == planning.cid('QZV-A0/L')


def test_find_courses_matches_title_words(unfamiliar_catalog):
    ledger = synthetic_ledger(UNFAMILIAR)
    found = curriculum_module().find_courses(unfamiliar_catalog, UNFAMILIAR, 'the fictional base course',
                                             titles=titles_of(ledger))
    assert found[0].title == 'Fictional BASE'
    assert found[0].printed_code == planning.CURRICULA[UNFAMILIAR]['BASE']


def test_find_courses_returns_several_candidates_when_ambiguous(unfamiliar_catalog):
    # QZV-A0/L, QZV-B1/L ... share the "qzv" prefix; stable order by printed code, bounded by the limit.
    found = curriculum_module().find_courses(unfamiliar_catalog, UNFAMILIAR, 'qzv', limit=4)
    assert len(found) == 4
    assert [m.printed_code for m in found] == sorted(m.printed_code for m in found)


def test_find_courses_empty_for_nonsense_and_for_another_curriculum(unfamiliar_catalog):
    module = curriculum_module()
    assert module.find_courses(unfamiliar_catalog, UNFAMILIAR, 'xyzzy plugh') == ()
    assert module.find_courses(unfamiliar_catalog, UNFAMILIAR, '   ') == ()
    assert module.find_courses(unfamiliar_catalog, SYNTHETIC, 'qzva0') == ()


def test_prerequisite_check_reports_met_not_met_and_unknown_separately(tools):
    # X needs BASE.
    met = run(tools.prerequisite_check(SYNTHETIC, 'program-synthetic', course_id('X'), (fact('BASE', 'passed'),)))
    not_met = run(tools.prerequisite_check(SYNTHETIC, 'program-synthetic', course_id('X'), (fact('BASE', 'failed'),)))
    unknown = run(tools.prerequisite_check(SYNTHETIC, 'program-synthetic', course_id('X'), ()))
    assert set(met) == {'course', 'printed_rule', 'evaluation', 'unmet', 'unknown_facts', 'limits'}
    assert (met['evaluation'], not_met['evaluation'], unknown['evaluation']) == ('met', 'not_met', 'unknown')
    assert met['course'] == 'SYN 104' and met['printed_rule'] == 'SYN 100'
    assert met['unmet'] == [] and met['unknown_facts'] == []
    assert not_met['unmet'] == [{'course': 'SYN 100', 'reason': 'not_completed'}] and not_met['unknown_facts'] == []
    assert unknown['unmet'] == [] and unknown['unknown_facts'] == [
        {'course': 'SYN 100', 'reason': 'completion_unknown'}]
    json.dumps([met, not_met, unknown])


def test_prerequisite_check_uses_only_session_facts(tools):
    seen = []

    class SpyAdapter:
        async def execute(self, request, context):
            seen.append(context)
            return await tools.symbolic.execute(request, context)

    spied = curriculum_module().CurriculumTools(SpyAdapter(), tools.catalog)
    facts = (fact('BASE', 'passed'),)
    run(spied.prerequisite_check(SYNTHETIC, 'program-synthetic', course_id('X'), facts))
    run(spied.prerequisite_check(SYNTHETIC, 'program-synthetic', course_id('X'), ()))
    assert seen[0].facts == facts and seen[1].facts == ()
    assert seen[0].curriculum_id == SYNTHETIC and seen[0].program_id == 'program-synthetic'


def test_blank_prerequisite_reported_as_none(tools):
    # LINK has a blank printed cell (owner, 4 Nov 2026: no prerequisite); T0 names LINK.
    blank = run(tools.prerequisite_check(SYNTHETIC, 'program-synthetic', course_id('LINK'), ()))
    assert blank['printed_rule'] == 'None' and blank['evaluation'] == 'met'
    dependent = run(tools.prerequisite_check(SYNTHETIC, 'program-synthetic', course_id('T0'), ()))
    assert dependent['printed_rule'] == 'SYN 109'


def test_course_facts_term_courses_and_affected_courses_return_printed_data(tools):
    facts = run(tools.course_facts(SYNTHETIC, 'program-synthetic', course_id('X')))
    assert facts['code'] == 'SYN 104' and facts['title'] == 'Fictional X'
    assert (facts['year'], facts['term']) == (2, 'first_semester')
    term = run(tools.term_courses(SYNTHETIC, 'program-synthetic', 2, 'first_semester'))
    assert [c['code'] for c in term['courses']] == ['SYN 104', 'SYN 105']
    affected = run(tools.affected_courses(SYNTHETIC, 'program-synthetic', course_id('BASE')))
    assert 'SYN 104' in affected['affected']
    json.dumps([facts, term, affected])


def test_unreviewed_or_missing_course_and_foreign_curriculum_return_error_codes(tools):
    missing = run(tools.course_facts(SYNTHETIC, 'program-synthetic', 'course-nonexistent'))
    assert missing == {'error': 'course_not_found'}

    class NotInRelease:
        async def execute(self, request, context):
            raise ValueError('curriculum_not_in_release')

    foreign = curriculum_module().CurriculumTools(NotInRelease(), ())
    assert run(foreign.course_facts('curriculum-other', 'program-x', 'course-a')) == {
        'error': 'curriculum_not_in_release'}

    class Broken:
        async def execute(self, request, context):
            raise ValueError('something_else')

    with pytest.raises(ValueError, match='something_else'):
        run(curriculum_module().CurriculumTools(Broken(), ()).course_facts('c', 'p', 'x'))


def test_unknown_facts_name_every_missing_course_by_printed_code(tools):
    # Y needs X and AUX; with BASE passed and nothing else stated, both are unknown.
    result = run(tools.prerequisite_check(SYNTHETIC, 'program-synthetic', course_id('Y'), (fact('BASE', 'passed'),)))
    assert result['unknown_facts'] == [{'course': 'SYN 101', 'reason': 'completion_unknown'},
                                       {'course': 'SYN 104', 'reason': 'completion_unknown'}]


def test_course_without_printed_code_keeps_its_raw_id(tools):
    bare = curriculum_module().CurriculumTools(tools.symbolic, ())
    result = run(bare.prerequisite_check(SYNTHETIC, 'program-synthetic', course_id('X'), ()))
    assert result['unknown_facts'] == [{'course': course_id('BASE'), 'reason': 'completion_unknown'}]


def test_bad_model_arguments_return_error_codes(tools):
    assert run(tools.term_courses(SYNTHETIC, 'program-synthetic', 9, 'first_semester')) == {
        'error': 'invalid_term_input'}
    assert run(tools.term_courses(SYNTHETIC, 'program-synthetic', 2, 'nonsense')) == {'error': 'invalid_term_input'}
    assert run(tools.course_facts(SYNTHETIC, 'program-synthetic', '')) == {'error': 'invalid_arguments'}
    assert run(tools.course_facts(SYNTHETIC, 'program-synthetic', 'x' * 500)) == {'error': 'invalid_arguments'}


def test_affected_courses_unknown_conditions_use_printed_codes(tools):
    real = run(tools.symbolic.execute(
        curriculum_module().PredicateRequest.parse({'predicate': 'list_affected_courses', 'inputs': [
            {'name': 'curriculum_id', 'value': SYNTHETIC, 'fact_ref': None},
            {'name': 'course_id', 'value': course_id('BASE'), 'fact_ref': None}]}),
        curriculum_module().RequestContext.parse(dict(session_id=SESSION, request_id='req-t',
            program_id='program-synthetic', curriculum_id=SYNTHETIC))))

    class Unresolved:
        async def execute(self, request, context):
            return real.model_copy(update=dict(unknown_conditions=('rule_unresolved:' + course_id('X'),)))

    shown = run(curriculum_module().CurriculumTools(Unresolved(), tools.catalog).affected_courses(
        SYNTHETIC, 'program-synthetic', course_id('BASE')))
    assert shown['unknown_conditions'] == [{'course': 'SYN 104', 'reason': 'rule_unresolved'}]
