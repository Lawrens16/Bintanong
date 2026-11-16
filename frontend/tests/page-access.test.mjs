import test from 'node:test';
import assert from 'node:assert/strict';
import { GUESTS_ALLOWED, SIGN_IN_ENABLED, pageRedirect } from '../lib/auth-policy.ts';

test('the landing page stays public for visitors and signed-in students', () => {
  assert.equal(pageRedirect('/', false), null);
  assert.equal(pageRedirect('/', true), null);
});

// Owner, 16 Nov 2026 (later): the site stays public for now; the school sign-in is kept, switched off.
test('while the site is public, chat accepts guests and nobody reaches the sign-in page', () => {
  assert.equal(SIGN_IN_ENABLED, false);
  assert.equal(GUESTS_ALLOWED, true);
  assert.equal(pageRedirect('/chat', false), null);
  assert.equal(pageRedirect('/login', false), '/');
  assert.equal(pageRedirect('/login', true), '/');
});

// The parked sign-in-only mode, for when the owner switches it on.
test('in sign-in-only mode, chat sends a visitor who is not signed in to the sign-in page', () => {
  assert.equal(pageRedirect('/chat', false, true, false), '/login');
  assert.equal(pageRedirect('/chat', true, true, false), null);
  assert.equal(pageRedirect('/login', false, true, false), null);
  assert.equal(pageRedirect('/login', true, true, false), '/chat');
});
