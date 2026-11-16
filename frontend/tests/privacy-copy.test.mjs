import test from 'node:test';
import assert from 'node:assert/strict';
import { UPLOADS_ENABLED, privacyNoticeBody, informationAnswer } from '../lib/privacy-copy.ts';

// Owner, 15 Nov 2026: no grades or identity are accepted; answers use a third-party AI service.
test('grade uploads are switched off', () => {
  assert.equal(UPLOADS_ENABLED, false);
});

test('the privacy notice names the third-party AI service and asks for no personal details', () => {
  assert.match(privacyNoticeBody, /Data Privacy Act of 2012/);
  assert.match(privacyNoticeBody, /third-party AI service/);
  assert.match(privacyNoticeBody, /name, student number, grades/);
  assert.match(privacyNoticeBody, /passed, failed/);
  assert.doesNotMatch(privacyNoticeBody, /upload|not stored permanently|used only to answer/i);
});

test('the FAQ answer matches the notice', () => {
  assert.match(informationAnswer, /third-party AI service/);
  assert.match(informationAnswer, /name, student number, grades/);
  assert.doesNotMatch(informationAnswer, /upload/i);
});

// Owner, 16 Nov 2026: chatting needs a school Google sign-in, which stores the school email address.
test('the notice and the FAQ say sign-in keeps the school email and nothing else personal', () => {
  for (const copy of [privacyNoticeBody, informationAnswer]) {
    assert.match(copy, /@psu\.palawan\.edu\.ph Google account/);
    assert.match(copy, /school email address/);
    assert.match(copy, /not shared with the AI service/);
    assert.doesNotMatch(copy, /No account is needed/);
  }
  assert.match(informationAnswer, /limited number of questions each day/);
});
