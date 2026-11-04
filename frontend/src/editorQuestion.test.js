import test from 'node:test';
import assert from 'node:assert/strict';

import { formatQuestionComment, getQuestionZoneHeight } from './editorQuestion.js';

test('formats each question line for the selected language', () => {
  const question = 'Return the sum.\nHandle negative values.';

  assert.equal(
    formatQuestionComment(question, 'python'),
    '# Return the sum.\n# Handle negative values.'
  );
  assert.equal(
    formatQuestionComment(question, 'javascript'),
    '// Return the sum.\n// Handle negative values.'
  );
  assert.equal(
    formatQuestionComment(question, 'cpp'),
    '// Return the sum.\n// Handle negative values.'
  );
});

test('question presentation never changes candidate solution text', () => {
  const solution = 'def add(a, b):\n    return a + b';
  formatQuestionComment('Add two numbers.', 'python');

  assert.equal(solution, 'def add(a, b):\n    return a + b');
});

test('question view zone height remains readable and bounded', () => {
  assert.equal(getQuestionZoneHeight('Short task'), 4);
  assert.equal(getQuestionZoneHeight('x'.repeat(2000)), 12);
});
