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
