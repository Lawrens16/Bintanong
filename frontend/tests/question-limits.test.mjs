import test from 'node:test';
import assert from 'node:assert/strict';
import { MAX_QUESTION_CHARS, limitNotice } from '../lib/question-limits.ts';

// Owner, 16 Nov 2026: daily question limits per person and for the whole site; long questions are refused.
test('the question length limit matches the server', () => {
  assert.equal(MAX_QUESTION_CHARS, 1000);
});

test('a person over the daily limit is told when they can ask again', () => {
  assert.equal(limitNotice('daily_limit_reached', 3 * 3600 + 5), "You've reached your daily question limit. You can ask again in about 4 hours.");
  assert.equal(limitNotice('daily_limit_reached', 3600), "You've reached your daily question limit. You can ask again in about 1 hour.");
  assert.equal(limitNotice('daily_limit_reached', 20 * 60), "You've reached your daily question limit. You can ask again in about 20 minutes.");
  assert.equal(limitNotice('daily_limit_reached', 30), "You've reached your daily question limit. You can ask again in about 1 minute.");
  assert.equal(limitNotice('daily_limit_reached', null), "You've reached your daily question limit. Please try again later.");
});

test('the whole-site limit and a too-long question have their own messages', () => {
  assert.equal(limitNotice('site_limit_reached', 7200), 'Bintanong has reached its question limit for today. You can ask again in about 2 hours.');
  assert.equal(limitNotice('message_too_long', null), 'Your question is too long. Please keep it under 1,000 characters.');
});

test('other refusals have no limit message', () => {
  assert.equal(limitNotice('rate_limited', 60), null);
  assert.equal(limitNotice('answers_busy', null), null);
});
