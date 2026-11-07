import React, { useCallback, useEffect, useRef } from 'react';
import MonacoEditor from 'react-monaco-editor';
import { Code2 } from 'lucide-react';
import { formatQuestionComment, getQuestionZoneHeight } from './editorQuestion';

const LANGUAGES = [
  { id: 'python', label: 'Python', monaco: 'python' },
  { id: 'java', label: 'Java', monaco: 'java' },
  { id: 'javascript', label: 'JavaScript', monaco: 'javascript' },
  { id: 'typescript', label: 'TypeScript', monaco: 'typescript' },
  { id: 'cpp', label: 'C++', monaco: 'cpp' },
  { id: 'text', label: 'Text', monaco: 'plaintext' },
];

const MONACO_LANG_MAP = Object.fromEntries(
  LANGUAGES.map(({ id, monaco }) => [id, monaco])
);

export default function MonacoEditorComponent({
  value,
  onChange,
  height = '100%',
  language = 'python',
  onLanguageChange,
  question = '',
}) {
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const questionZoneRef = useRef(null);
  const applyingValueRef = useRef(false);

  const renderQuestionZone = useCallback(() => {
    const editor = editorRef.current;
    if (!editor) return;

    editor.changeViewZones((accessor) => {
      if (questionZoneRef.current) {
        accessor.removeZone(questionZoneRef.current);
        questionZoneRef.current = null;
      }

      const comment = formatQuestionComment(question, language);
      if (!comment) return;

      const domNode = document.createElement('div');
      domNode.setAttribute('role', 'note');
      domNode.setAttribute('aria-label', 'Current coding question');
      domNode.textContent = comment;
      Object.assign(domNode.style, {
        boxSizing: 'border-box',
        height: '100%',
        overflow: 'auto',
        padding: '12px 18px',
        borderBottom: '1px solid var(--border-strong)',
        background: 'var(--surface-code-note)',
        color: 'var(--accent-soft)',
        fontFamily: 'var(--font-mono)',
        fontSize: '12px',
        lineHeight: '19px',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      });

      questionZoneRef.current = accessor.addZone({
        afterLineNumber: 0,
        heightInLines: getQuestionZoneHeight(question),
        domNode,
        suppressMouseDown: false,
      });
    });
  }, [language, question]);

  const editorDidMount = useCallback((editorInstance, monacoInstance) => {
    editorRef.current = editorInstance;
    monacoRef.current = monacoInstance;
    renderQuestionZone();
  }, [renderQuestionZone]);

  const handleChange = useCallback((nextValue) => {
    if (!applyingValueRef.current) {
      onChange(nextValue ?? '');
    }
  }, [onChange]);

  const handleLanguageChange = useCallback((nextLanguage) => {
    if (nextLanguage === language) return;
    onLanguageChange(nextLanguage, editorRef.current?.getValue() ?? value ?? '');
  }, [language, onLanguageChange, value]);

  useEffect(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco) return;

    monaco.editor.setModelLanguage(
      editor.getModel(),
      MONACO_LANG_MAP[language] || language
    );
    renderQuestionZone();
  }, [language, renderQuestionZone]);

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor || editor.getValue() === (value ?? '')) return;

    applyingValueRef.current = true;
    editor.setValue(value ?? '');
    applyingValueRef.current = false;
  }, [value]);

  useEffect(() => {
    renderQuestionZone();
  }, [question, renderQuestionZone]);

  useEffect(() => () => {
    const editor = editorRef.current;
    if (editor && questionZoneRef.current) {
      editor.changeViewZones((accessor) => accessor.removeZone(questionZoneRef.current));
    }
  }, []);

  return (
    <div className="monaco-shell" style={{ height }}>
      <div className="language-selector">
        <Code2 size={14} aria-hidden="true" />
        <label htmlFor="editor-language">Language</label>
        <select
          id="editor-language"
          value={language}
          onChange={(event) => handleLanguageChange(event.target.value)}
        >
          {LANGUAGES.map(({ id, label }) => (
            <option key={id} value={id}>{label}</option>
          ))}
        </select>
      </div>
      <div className="monaco-editor-frame">
        <MonacoEditor
          height="100%"
          width="100%"
          language={MONACO_LANG_MAP[language] || language}
          theme="vs"
          value={value ?? ''}
          onChange={handleChange}
          editorDidMount={editorDidMount}
          options={{
            minimap: { enabled: true },
            fontFamily: 'IBM Plex Mono, SFMono-Regular, Consolas, monospace',
            fontSize: 13,
            lineHeight: 21,
            padding: { top: 10, bottom: 10 },
            wordWrap: 'on',
            automaticLayout: true,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            stickyScroll: { enabled: true },
          }}
        />
      </div>
    </div>
  );
}
