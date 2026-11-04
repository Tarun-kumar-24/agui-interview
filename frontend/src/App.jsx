import React, { useState, useCallback, useEffect } from 'react';
import { Code, Bot, Minimize2, Maximize2, CheckCircle, AlertCircle } from 'lucide-react';
import MonacoEditor from './MonacoEditor';
import ChatWindow from './ChatWindow';
import SplitPane from './SplitPane';
import useAguiChat from './useAguiChat';

const AGUI_URL = import.meta.env.VITE_AGUI_URL || 'http://localhost:8000';

export default function App() {
  const [threadId] = useState(() => 'thread_' + crypto.randomUUID());

  const {
    messages,
    isStreaming,
    sendMessage,
    codingMode,
    editorOpen,
    setEditorOpen,
    editorTask,
    editorCode,
    setEditorCode,
    editorLanguage,
    setEditorLanguage,
    sessionId,
    currentQuestion,
    interviewStatus,
    startTimers,
    stopTimers,
    requestCodeReview,
  } = useAguiChat(AGUI_URL, threadId);

  useEffect(() => {
    if (codingMode && currentQuestion) {
      startTimers();
    } else {
      stopTimers();
    }
  }, [codingMode, currentQuestion?.question_id, startTimers, stopTimers]);

  const handleLanguageChange = useCallback((language, code) => {
    setEditorLanguage(language);
    setEditorCode(code);
  }, [setEditorCode, setEditorLanguage]);

  const handleEditorChange = useCallback((code) => {
    setEditorCode(code);
  }, [setEditorCode]);

  const handleSend = useCallback((text) => sendMessage(text), [sendMessage]);

  const handleReviewClick = useCallback(() => {
    if (editorCode.trim()) {
      requestCodeReview();
    }
  }, [editorCode, requestCodeReview]);

  return (
    <div className="app">
      <div className="toolbar">
        <div className="toolbar-brand">
          <Code size={20} />
          <span>AG-UI Interview Agent</span>
        </div>
        <div className="toolbar-actions">
          {codingMode && (
            <button
              className="toggle-btn"
              onClick={() => setEditorOpen((open) => !open)}
              title={editorOpen ? 'Hide editor (chat only)' : 'Show active coding editor'}
            >
              {editorOpen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              <span>{editorOpen ? 'Hide Editor' : 'Show Editor'}</span>
            </button>
          )}
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

            {/* Problem Description Panel */}
            {(editorTask || currentQuestion) && (
              <div className="problem-panel" style={{
                padding: '12px 14px',
                background: '#0b1120',
                borderBottom: '1px solid #1e293b',
                flexShrink: 0,
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                  <AlertCircle size={16} style={{ color: '#fbbf24', flexShrink: 0, marginTop: 2 }} />
                  <div style={{ flex: 1, fontSize: 13, lineHeight: 1.6, color: '#e2e8f0' }}>
                    <strong style={{ color: '#fbbf24' }}>Current Task:</strong> {editorTask || currentQuestion?.question_text}
                  </div>
                </div>
              </div>
            )}

            <div className="editor-wrapper" style={{ flex: 1, minHeight: 0, position: 'relative', display: 'flex', flexDirection: 'column' }}>
              <MonacoEditor
                value={editorCode}
                onChange={handleEditorChange}
                language={editorLanguage}
                onLanguageChange={handleLanguageChange}
                question={currentQuestion?.question_text || editorTask}
              />
              {/* Review Button */}
              <div style={{
                padding: '8px 12px',
                background: '#0b1120',
                borderTop: '1px solid #1e293b',
                flexShrink: 0,
                display: 'flex',
                justifyContent: 'flex-end',
              }}>
                <button
                  onClick={handleReviewClick}
                  disabled={!editorCode.trim() || isStreaming}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 16px',
                    background: editorCode.trim() && !isStreaming ? '#1e3a8a' : '#334155',
                    border: '1px solid #334155',
                    borderRadius: 6,
                    color: editorCode.trim() && !isStreaming ? '#93c5fd' : '#64748b',
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: editorCode.trim() && !isStreaming ? 'pointer' : 'not-allowed',
                    transition: 'all 0.2s',
                  }}
                >
                  <CheckCircle size={14} />
                  <span>Submit for Review</span>
                </button>
              </div>
            </div>
          </div>
        )}
        <SplitPane editorOpen={editorOpen} onToggle={() => setEditorOpen((o) => !o)} />
        <div className="chat-panel">
          <div className="panel-header">
            <Bot size={18} style={{ marginRight: 6 }} />
            <span>Interview Chat</span>
            {sessionId && (
              <span style={{ marginLeft: 'auto', fontSize: 11, color: '#64748b', background: '#1e293b', padding: '2px 8px', borderRadius: 4 }}>
                Session: {sessionId.slice(-8)}
              </span>
            )}
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
