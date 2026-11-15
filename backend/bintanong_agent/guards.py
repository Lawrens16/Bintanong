"""The four code guards and the fixed replies the agent gives without the model."""
from __future__ import annotations

import dataclasses
import re

from ..bintanong_contracts.base import foreign_ids
from ..bintanong_routing.router import EXCLUDED_PROGRAM_CUES

# Fixed wording, as the original build's replies (bintanong_generation/render.py).
SCOPE_NOTICE = {
    'english': 'Bintanong covers undergraduate academic affairs; this request is outside that scope.',
    'taglish': 'Undergraduate academic affairs ang scope ng Bintanong; outside scope ang request.'}
FALLBACK_REPLY = {
    'english': "I couldn't verify a complete answer from the reviewed sources. "
               'Please confirm with the relevant university office.',
    'taglish': 'Hindi ko pa ma-verify ang kumpletong sagot gamit ang reviewed sources. '
               'Paki-confirm sa tamang university office.'}
UNAVAILABLE_REPLY = {
    'english': 'Bintanong is temporarily unavailable. Please try again later.',
    'taglish': 'Temporarily unavailable ang Bintanong. Paki-try ulit later.'}

# Owner, 15 Nov 2026: no grades or identity reach the hosted model; obvious identifiers are removed first.
_PERSONAL_DETAILS = re.compile(
    r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+'                          # email address
    r'|(?<!\w)(?:\+63|0)\s?9\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)'   # Philippine mobile number
    r'|(?<![\w-])(?:\d{2}|(?:19|20)\d{2})-\d{5,6}(?![\w-])')     # student number, e.g. 2021-12345; not 2018-2019


def redact_personal_details(text: str) -> str:
    return _PERSONAL_DETAILS.sub('[removed]', text)


_FILIPINO_WORDS = re.compile(
    r'\b(po|ba|ang|ng|mga|paano|pano|pwede|puwede|ako|ko|sa|na|ano|saan|kailan|yung|lang|naman|hindi)\b', re.I)


def reply_language(question: str) -> str:
    """Language for a fixed reply: any Filipino function word means Taglish, otherwise English."""
    return 'taglish' if _FILIPINO_WORDS.search(question) else 'english'


def excluded_audience(question: str) -> bool:
    """Guard 4: the question names a program outside undergraduate academic affairs."""
    question = question.replace('’', "'")  # a typed curly apostrophe matches master's
    return any(re.search(r'(?<![\w-])' + re.escape(cue) + r'(?![\w-])', question, re.IGNORECASE)
               for cue in EXCLUDED_PROGRAM_CUES)


def citation_errors(final: dict, state) -> list[str]:
    """Guard 3: a policy answer cites at least one passage, and only passages fetched this turn."""
    if any(short_id not in state.fetched for short_id in final['citations']):
        return ['unknown_citation']
    if final['kind'] == 'answer' and not final['eligibility'] and not final['citations']:
        return ['uncited_policy_answer']
    return []


def eligibility_errors(final: dict, state) -> list[str]:
    """Guard 1: an eligibility answer needs a rule check this turn; its wording is the model's."""
    return ['rules_not_consulted'] if final['eligibility'] and not state.rule_checks else []


def private_leak(citations, state) -> bool:
    """Guard 2: source cards hold only passages fetched this turn and no session or fact ids."""
    return any(state.fetched.get(passage.short_id) is not passage
               or foreign_ids(dataclasses.asdict(passage), 'institutional') for passage in citations)
