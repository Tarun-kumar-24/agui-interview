import React, { useState, useCallback, useEffect } from 'react';
import {
  AlertCircle,
  Bot,
  CheckCircle,
  Code,
  Maximize2,
  Minimize2,
  Volume2,
  VolumeX,
} from 'lucide-react';
import MonacoEditor from './MonacoEditor';
import ChatWindow from './ChatWindow';
import SplitPane from './SplitPane';
import useAguiChat from './useAguiChat';

const AGUI_URL = import.meta.env.VITE_AGUI_URL || 'http://localhost:8000';

const STATUS_LABELS = {
  NOT_STARTED: 'Ready',
  THEORETICAL: 'Interview in progress',
  CODING_ACTIVE: 'Coding round',
  WAITING_FOR_REVIEW: 'Ready for review',
  REVIEWING: 'Reviewing code',
  ENDED: 'Interview complete',
};

export default function App() {
  const [threadId] = useState(() => 'thread_' + crypto.randomUUID());
  const [editorWidth, setEditorWidth] = useState(55);

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
    voiceEnabled,
    isSpeaking,
    speakingMessageId,
    toggleVoice,
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

  const statusLabel = isSpeaking
    ? 'Speaking response'
    : isStreaming
      ? 'Interviewer is responding'
    : (interviewStatus === 'NOT_STARTED' && messages.length
      ? 'Interview in progress'
      : (STATUS_LABELS[interviewStatus] || 'Connected'));

  return (
    <div className="app">
      <header className="toolbar">
        <div className="toolbar-brand">
          <span className="brand-mark" aria-hidden="true"><Code size={18} /></span>
          <span className="brand-copy">
            <strong>Interview studio</strong>
            <small>Adaptive technical assessment</small>
          </span>
        </div>
        <div className="toolbar-actions">
          <button
            className={`voice-toggle ${voiceEnabled ? 'is-enabled' : ''} ${isSpeaking ? 'is-speaking' : ''}`}
            type="button"
            onClick={toggleVoice}
            aria-pressed={voiceEnabled}
            title={voiceEnabled ? 'Turn interviewer voice off' : 'Turn interviewer voice on'}
          >
            {voiceEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
            <span>{isSpeaking ? 'Speaking' : (voiceEnabled ? 'Voice on' : 'Voice off')}</span>
          </button>
          <div className={`run-status ${isStreaming || isSpeaking ? 'is-active' : ''}`}>
            <i />
            <span>{statusLabel}</span>
          </div>
          {codingMode && (
            <button
              className="toggle-btn"
              onClick={() => setEditorOpen((open) => !open)}
              title={editorOpen ? 'Hide editor and focus on chat' : 'Show active coding editor'}
            >
              {editorOpen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
              <span>{editorOpen ? 'Focus on chat' : 'Show code'}</span>
            </button>
          )}
        </div>
      </header>

      <main
        className={`split-container ${editorOpen ? 'has-editor' : 'chat-only'}`}
        style={{ '--editor-width': `${editorWidth}%` }}
      >
        {editorOpen && (
          <section className="editor-panel" aria-label="Coding workspace">
            <div className="panel-header">
              <div className="panel-title">
                <span className="panel-icon"><Code size={15} /></span>
                <span>
                  <strong>Code workspace</strong>
                  <small>{editorLanguage}</small>
                </span>
              </div>
              {currentQuestion && (
                <div className="question-meta">
                  {currentQuestion.concept && <span>{currentQuestion.concept}</span>}
                  {currentQuestion.difficulty && <span>{currentQuestion.difficulty}</span>}
                </div>
              )}
            </div>

            {(editorTask || currentQuestion) && (
              <section className="problem-panel" aria-labelledby="current-task-title">
                <div className="problem-marker" aria-hidden="true">
                  <AlertCircle size={15} />
                </div>
                <div>
                  <p className="eyebrow" id="current-task-title">Current task</p>
                  <p>{editorTask || currentQuestion?.question_text}</p>
                </div>
              </section>
            )}

            <div className="editor-wrapper">
              <MonacoEditor
                value={editorCode}
                onChange={handleEditorChange}
                language={editorLanguage}
                onLanguageChange={handleLanguageChange}
                question={currentQuestion?.question_text || editorTask}
              />
              <div className="review-bar">
                <p><i /> Latest editor state will be reviewed</p>
                <button
                  className="review-button"
                  onClick={handleReviewClick}
                  disabled={!editorCode.trim() || isStreaming}
                >
                  <CheckCircle size={14} />
                  <span>Submit for review</span>
                </button>
              </div>
            </div>
          </section>
        )}

        {editorOpen && <SplitPane value={editorWidth} onResize={setEditorWidth} />}

        <section className="chat-panel" aria-label="Interview conversation">
          <div className="panel-header">
            <div className="panel-title">
              <span className="panel-icon"><Bot size={15} /></span>
              <span>
                <strong>Interview room</strong>
                <small>{isStreaming ? 'Response streaming' : 'Live adaptive session'}</small>
              </span>
            </div>
            {sessionId && (
              <span className="session-id"><small>Session</small>{sessionId.slice(-8)}</span>
            )}
          </div>
          <ChatWindow
            messages={messages}
            isStreaming={isStreaming}
            speakingMessageId={speakingMessageId}
            onSend={handleSend}
          />
        </section>
      </main>
    </div>
  );
}
