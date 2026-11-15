import dataclasses
import importlib

import pytest

import test_agent_tools as fixtures


def guards():
    return importlib.import_module('backend.bintanong_agent.guards')


def state_with(*fetched_ids, rule_checks=()):
    state = fixtures.make_state()
    corpus = fixtures.make_corpus()
    state.fetched.update({short_id: corpus.get(short_id) for short_id in fetched_ids})
    state.rule_checks.extend(rule_checks)
    return state


def final(kind='answer', citations=(), eligibility=False):
    return {'kind': kind, 'language': 'english', 'text': 'reply', 'citations': list(citations),
            'eligibility': eligibility}


@pytest.mark.parametrize('question', [
    'How do I enroll in the College of Law?', 'requirements for the JURIS DOCTOR program',
    'Paano mag-apply sa graduate school?', 'Can I take a master’s degree here?',
    'Is there a laboratory school enrolment schedule?', 'doctor of medicine admission po'])
def test_excluded_audience_matches_named_excluded_programs(question):
    assert guards().excluded_audience(question) is True


@pytest.mark.parametrize('question', [
    'How do I request my transcript?', 'Is it lawful to overload units?', 'pwede ba ko mag cc5?',
    'Where is the nursing laboratory?', 'I graduate next year, what are the requirements?'])
def test_excluded_audience_leaves_undergraduate_questions(question):
    assert guards().excluded_audience(question) is False


@pytest.mark.parametrize('question, language', [
    ('How do I request my transcript?', 'english'), ('pwede ba ko mag cc5?', 'taglish'),
    ('Paano po kumuha ng good moral?', 'taglish'), ('Hello!', 'english')])
def test_reply_language_follows_the_question(question, language):
    assert guards().reply_language(question) == language


def test_policy_answer_with_fetched_citation_has_no_errors():
    assert guards().citation_errors(final(citations=['C002']), state_with('C002')) == []


def test_policy_answer_without_citation_is_uncited():
    assert guards().citation_errors(final(), state_with('C002')) == ['uncited_policy_answer']


def test_citation_that_was_not_fetched_this_turn_is_unknown():
    assert guards().citation_errors(final(citations=['C002', 'C003']), state_with('C002')) == ['unknown_citation']
    assert guards().citation_errors(final(citations=['C999']), state_with()) == ['unknown_citation']


@pytest.mark.parametrize('kind', ['chat', 'clarify', 'out_of_scope'])
def test_non_answer_kinds_need_no_citation(kind):
    assert guards().citation_errors(final(kind=kind), state_with()) == []


def test_eligibility_answer_needs_no_citation():
    assert guards().citation_errors(final(eligibility=True), state_with()) == []


def test_eligibility_without_a_rule_check_is_an_error():
    assert guards().eligibility_errors(final(eligibility=True), state_with()) == ['rules_not_consulted']


def test_eligibility_after_a_rule_check_passes():
    state = state_with(rule_checks=[fixtures.RULE_RESULT])
    assert guards().eligibility_errors(final(eligibility=True), state) == []
    assert guards().eligibility_errors(final(), state_with()) == []


def test_private_leak_false_for_fetched_corpus_passages():
    state = state_with('C002')
    assert guards().private_leak((state.fetched['C002'],), state) is False


def test_private_leak_when_citation_is_not_a_fetched_passage():
    state = state_with('C002')
    assert guards().private_leak((fixtures.make_corpus().get('C001'),), state) is True


def test_private_grade_not_in_citations():
    # A source card carrying a session or fact id is private data, whatever passage it claims to be.
    state = state_with('C002')
    for private_id in (fixtures.SESSION, 'fact-syn-100'):
        tainted = dataclasses.replace(state.fetched['C002'], text=f'Grade record {private_id}: 1.25')
        state.fetched['C002'] = tainted
        assert guards().private_leak((tainted,), state) is True


def test_fixed_replies_exist_in_both_languages():
    module = guards()
    for replies in (module.SCOPE_NOTICE, module.FALLBACK_REPLY, module.UNAVAILABLE_REPLY):
        assert set(replies) == {'english', 'taglish'} and all(replies.values())
    assert 'undergraduate academic affairs' in module.SCOPE_NOTICE['english']
