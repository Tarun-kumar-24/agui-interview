import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanSpeechText, splitSpeechSegments } from './useEdgeTts.js';

test('splits complete sentences while preserving a streaming remainder', () => {
  const result = splitSpeechSegments(
    'Welcome to the interview. What is a closure? This answer is still streaming',
  );

  assert.deepEqual(result.segments, [
    'Welcome to the interview.',
    'What is a closure?',
  ]);
  assert.equal(result.remainder, 'This answer is still streaming');
});

test('flushes and cleans the final speech segment', () => {
  const result = splitSpeechSegments(
    'Review the `result` value and **explain** your choice',
    true,
  );

  assert.deepEqual(result.segments, [
    'Review the result value and explain your choice',
  ]);
  assert.equal(result.remainder, '');
});

test('removes markdown and URLs before synthesis', () => {
  assert.equal(
    cleanSpeechText('See [the docs](https://example.com) or https://example.com now.'),
    'See the docs or link now.',
  );
});
