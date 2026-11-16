import test from 'node:test';
import assert from 'node:assert/strict';
import { GUESTS_ALLOWED, SIGN_IN_ENABLED, pageRedirect } from '../lib/auth-policy.ts';

test('the landing page stays public for visitors and signed-in students', () => {
  assert.equal(pageRedirect('/', false), null);
  assert.equal(pageRedirect('/', true), null);
});

// Owner, 16 Nov 2026 (hosted fork): chatting needs a school Google sign-in; no guest chat.
test('chat sends a visitor who is not signed in to the sign-in page', () => {
  assert.equal(SIGN_IN_ENABLED, true);
  assert.equal(GUESTS_ALLOWED, false);
  assert.equal(pageRedirect('/chat', false), '/login');
  assert.equal(pageRedirect('/chat', true), null);
});

test('when guest mode is on, chat accepts guests', () => {
  assert.equal(pageRedirect('/chat', false, true, true), null);
  assert.equal(pageRedirect('/chat', false, false, true), null);
});

test('the sign-in page shows for visitors and sends signed-in students to chat', () => {
  assert.equal(pageRedirect('/login', false), null);
  assert.equal(pageRedirect('/login', true), '/chat');
});

test('with sign-in switched off, the sign-in page sends everyone to the landing page', () => {
  assert.equal(pageRedirect('/login', false, false), '/');
  assert.equal(pageRedirect('/login', true, false), '/');
});
