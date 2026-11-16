import test from 'node:test';
import assert from 'node:assert/strict';
import { programListText, progressLabel, progressStages, WAKING_UP, WAKING_UP_AFTER_MS } from '../lib/student-progress.ts';
import { sendStudentMessage } from '../lib/student-transport.ts';

const request = { id: 'msg-test', text: 'A synthetic question', programId: 'program-a', curriculumId: 'curriculum-a' };
const sse = parts => parts.map(part => 'data: ' + JSON.stringify(part) + '\n\n').join('') + 'data: [DONE]\n\n';
const status = stage => ({ type: 'data-status', data: { stage }, transient: true });
const answer = [
  { type: 'text-start', id: 'text-answer' },
  { type: 'text-delta', id: 'text-answer', delta: 'Synthetic response.' },
  { type: 'text-end', id: 'text-answer' },
  { type: 'data-answer', data: { status: 'answered', conditional: false, language: 'en', missingFields: [] } },
  { type: 'finish', finishReason: 'stop' },
];
const response = raw => new Response(raw, { headers: { 'Content-Type': 'text/event-stream', 'x-vercel-ai-ui-message-stream': 'v1' } });
const send = (parts, progress) => sendStudentMessage(request, { signal: new AbortController().signal, onText() {},
  onProgress: stage => progress.push(stage), fetch: async () => response(sse(parts)) });

test('agent progress stages pass through the chat stream', async () => {
  const progress = [];
  const result = await send([{ type: 'start', messageId: 'msg-answer' }, status('searching'), status('checking'),
    status('writing'), ...answer], progress);
  assert.deepEqual(progress, ['searching', 'checking', 'writing']);
  assert.equal(result.text, 'Synthetic response.');
});

test('an unknown progress stage is still rejected', async () => {
  await assert.rejects(send([{ type: 'start', messageId: 'msg-answer' }, status('thinking'), ...answer], []));
});

test('every progress stage has its own student-facing line', () => {
  assert.deepEqual([...progressStages], ['waiting', 'understanding', 'searching', 'checking', 'writing']);
  const labels = progressStages.map(progressLabel);
  assert.equal(new Set(labels).size, labels.length);
  assert.ok(labels.every(label => label.length > 10));
  assert.match(progressLabel('searching'), /documents/i);
  assert.match(progressLabel('checking'), /curriculum/i);
});

test('a slow first response is explained after ten seconds', () => {
  assert.equal(WAKING_UP_AFTER_MS, 10_000);
  assert.match(WAKING_UP, /waking up/i);
});

// Owner, 16 Nov 2026: the program list waited 90 s on a sleeping free server with only "Loading programs…" shown.
test('the program list explains a long wait as the server waking up', () => {
  assert.equal(programListText(0), 'Loading programs…');
  assert.equal(programListText(WAKING_UP_AFTER_MS - 1), 'Loading programs…');
  assert.match(programListText(WAKING_UP_AFTER_MS), /waking up the server/i);
  assert.match(programListText(WAKING_UP_AFTER_MS), /up to 2 minutes/);
});

test('the reply wait message matches the measured wake-up time', () => {
  assert.match(WAKING_UP, /up to 2 minutes/);
});
