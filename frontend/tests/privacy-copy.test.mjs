import test from 'node:test';
import assert from 'node:assert/strict';
import { UPLOADS_ENABLED, privacyNoticeBody, informationAnswer, signInNotice, DATA_CONTACT } from '../lib/privacy-copy.ts';

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

// Owner, 16 Nov 2026 (later): the site stays public for now; the school sign-in is kept, switched off.
test('while the site is public, the notice and FAQ make no sign-in claims and explain the daily limit', () => {
  for (const copy of [privacyNoticeBody, informationAnswer]) {
    assert.doesNotMatch(copy, /sign in|sign-in|school email|profile photo/i);
  }
  assert.match(informationAnswer, /No account is needed/);
  assert.match(informationAnswer, /limited number of questions each day/);
  assert.match(informationAnswer, /anonymous browser cookie/);
});

// Kept for when sign-in is switched on: Google gives the name, school email and photo link; the record is deleted
// 7 days after the last sign-in; requests go to the project email.
test('the parked sign-in notice says what sign-in keeps, for how long and whom to ask', () => {
  assert.equal(DATA_CONTACT, 'bintanongbinturong@gmail.com');
  assert.match(signInNotice, /name, school email address and Google profile photo/);
  assert.match(signInNotice, /7 days after you last sign in/);
  assert.match(signInNotice, /bintanongbinturong@gmail\.com/);
  assert.match(signInNotice, /not shared with the AI service/);
});
