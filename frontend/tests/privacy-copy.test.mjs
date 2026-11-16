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

// Owner, 16 Nov 2026: chatting needs a school Google sign-in. Google gives the name, school email and photo link;
// the record is deleted 7 days after the last sign-in; requests go to the project email.
test('the notice, the FAQ and the sign-in page say what sign-in keeps, for how long and whom to ask', () => {
  assert.equal(DATA_CONTACT, 'bintanongbinturong@gmail.com');
  for (const copy of [privacyNoticeBody, informationAnswer, signInNotice]) {
    assert.match(copy, /name, school email address and Google profile photo/);
    assert.match(copy, /7 days after you last sign in/);
    assert.match(copy, /bintanongbinturong@gmail\.com/);
    assert.doesNotMatch(copy, /No account is needed|stores your account email/);
  }
  for (const copy of [privacyNoticeBody, informationAnswer]) {
    assert.match(copy, /@psu\.palawan\.edu\.ph Google account/);
    assert.match(copy, /not shared with the AI service/);
  }
  assert.match(informationAnswer, /limited number of questions each day/);
});
