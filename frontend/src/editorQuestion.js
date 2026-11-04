const COMMENT_PREFIX = {
  python: '# ',
  java: '// ',
  javascript: '// ',
  typescript: '// ',
  cpp: '// ',
  text: '# ',
};

export function formatQuestionComment(question, language) {
  if (!question?.trim()) return '';

  const prefix = COMMENT_PREFIX[language] || '// ';
  return question
    .trim()
    .split(/\r?\n/)
    .map((line) => `${prefix}${line}`.trimEnd())
    .join('\n');
}

export function getQuestionZoneHeight(question) {
  if (!question?.trim()) return 0;

  const wrappedLines = question
    .trim()
    .split(/\r?\n/)
    .reduce((count, line) => count + Math.max(1, Math.ceil(line.length / 84)), 0);

  return Math.min(Math.max(wrappedLines + 2, 4), 12);
}
