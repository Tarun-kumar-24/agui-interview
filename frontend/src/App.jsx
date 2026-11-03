import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Code, Bot, Minimize2, Maximize2 } from 'lucide-react';
import MonacoEditor from './MonacoEditor';
import ChatWindow from './ChatWindow';
import SplitPane from './SplitPane';
import useAguiChat from './useAguiChat';

const AGUI_URL = import.meta.env.VITE_AGUI_URL || 'http://localhost:8000';

export default function App() {
  const [editorContent, setEditorContent] = useState('// Write your code here...\n// The interviewer can see what you write.\n');
  const [threadId] = useState(() => 'thread_' + crypto.randomUUID());
  const historyRef = useRef([]);

  const { messages, setMessages, isStreaming, sendMessage, editorOpen, setEditorOpen, editorTask, editorInitialCode, editorLanguage } = useAguiChat(
    AGUI_URL,
    threadId
  );

  // Load initial code when coding round starts
  useEffect(() => {
    if (editorOpen && editorInitialCode) {
      setEditorContent(editorInitialCode);
    }
  }, [editorOpen, editorInitialCode]);

  const handleSend = useCallback(
    (text) => {
      historyRef.current = [
        ...historyRef.current,
        { role: 'user', content: text },
      ];
      sendMessage(text, editorContent, historyRef.current);
    },
    [editorContent, sendMessage]
  );

  return (
    <div className="app">
      <div className="toolbar">
        <div className="toolbar-brand">
          <Code size={20} />
          <span>AG-UI Interview Agent</span>
        </div>
        <div className="toolbar-actions">
          <button
            className="toggle-btn"
            onClick={() => setEditorOpen((o) => !o)}
            title={editorOpen ? 'Hide editor (chat only)' : 'Show editor'}
          >
            {editorOpen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            <span>{editorOpen ? 'Hide Editor' : 'Show Editor'}</span>
          </button>
        </div>
      </div>

      <div className="split-container">
        {editorOpen && (
          <div className="editor-panel">
            <div className="panel-header">
              <Code size={16} style={{ marginRight: 6 }} />
              <span>Monaco Editor (Code)</span>
              {editorTask && (
                <div className="editor-task" style={{ marginLeft: 'auto', fontSize: 12, color: '#888', maxWidth: '400px', textAlign: 'right' }}>
                  {editorTask.slice(0, 100)}...
                </div>
              )}
            </div>
            <div className="editor-wrapper" style={{ flex: 1, minHeight: 0, position: 'relative' }}>
              <MonacoEditor value={editorContent} onChange={setEditorContent} language={editorLanguage} />
            </div>
          </div>
        )}
        <SplitPane editorOpen={editorOpen} onToggle={() => setEditorOpen((o) => !o)} />
        <div className="chat-panel">
          <div className="panel-header">
            <Bot size={18} style={{ marginRight: 6 }} />
            <span>Interview Chat</span>
          </div>
          <ChatWindow
            messages={messages}
            isStreaming={isStreaming}
            onSend={handleSend}
          />
        </div>
      </div>
    </div>
  );
}