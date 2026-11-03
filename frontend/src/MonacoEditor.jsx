import React, { useEffect, useRef, useState } from 'react';
import MonacoEditor from 'react-monaco-editor';

export default function MonacoEditorComponent({ value, onChange, height = '100%', language = 'javascript' }) {
  const editorRef = useRef(null);
  const [editor, setEditor] = useState(null);
  const [monaco, setMonaco] = useState(null);

  const editorDidMount = (editorInstance, monacoInstance) => {
    setEditor(editorInstance);
    setMonaco(monacoInstance);
    editorRef.current = editorInstance;
    try {
      editorInstance.focus();
    } catch (e) {
      // ignore focus issues
    }
  };

  const editorWillMount = (monacoInstance) => {
    // no-op; environment configured in main.jsx
  };

  return (
    <div className="editor-wrapper" style={{ flex: 1, position: 'relative', minHeight: 0 }}>
      <MonacoEditor
        height={height}
        width="100%"
        language={language}
        theme="vs-dark"
        value={value != null ? value : ''}
        onChange={(newValue) => onChange(newValue)}
        editorDidMount={editorDidMount}
        editorWillMount={editorWillMount}
        options={{
          minimap: { enabled: true },
          fontSize: 14,
          wordWrap: 'on',
          automaticLayout: true,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
        }}
      />
      <div className="editor-hint">
        Write code here. It is sent to the interviewer with each message.
      </div>
    </div>
  );
}