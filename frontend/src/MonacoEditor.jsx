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
        padding: '10px 16px',
        borderBottom: '1px solid #334155',
        background: '#111827',
        color: language === 'python' ? '#7dd3a7' : '#79c0ff',
        fontFamily: 'Consolas, "Courier New", monospace',
        fontSize: '13px',
        lineHeight: '20px',
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
    editorInstance.focus();
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
    <div style={{ display: 'flex', flexDirection: 'column', height, width: '100%' }}>
      <div className="language-selector" style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 12px',
        background: '#0b1120',
        borderBottom: '1px solid #1e293b',
        flexShrink: 0,
      }}>
        <Code2 size={14} style={{ color: '#64748b' }} />
        <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 500 }}>Language</span>
        <select
          value={language}
          onChange={(event) => handleLanguageChange(event.target.value)}
          style={{
            flex: 1,
            maxWidth: 180,
            padding: '6px 32px 6px 10px',
            background: '#020617',
            border: '1px solid #334155',
            borderRadius: 4,
            color: '#f8fafc',
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          {LANGUAGES.map(({ id, label }) => (
            <option key={id} value={id}>{label}</option>
          ))}
        </select>
      </div>
      <MonacoEditor
        height="100%"
        width="100%"
        language={MONACO_LANG_MAP[language] || language}
        theme="vs-dark"
        value={value ?? ''}
        onChange={handleChange}
        editorDidMount={editorDidMount}
        options={{
          minimap: { enabled: true },
          fontSize: 14,
          wordWrap: 'on',
          automaticLayout: true,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          stickyScroll: { enabled: true },
        }}
      />
    </div>
  );
}
