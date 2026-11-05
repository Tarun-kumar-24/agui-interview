import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, MessageCircle, Send } from 'lucide-react';

const STARTER_PROMPTS = [
  'Start my technical interview',
  'Can we start the coding round?',
];

export default function ChatWindow({ messages, isStreaming, onSend }) {
  const [draft, setDraft] = useState('');
  const inputRef = useRef(null);
  const messageListRef = useRef(null);
  const hasMessages = Boolean(messages?.length);

  const focusComposer = useCallback(() => {
    inputRef.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    if (isStreaming) return undefined;
    const frame = requestAnimationFrame(focusComposer);
    return () => cancelAnimationFrame(frame);
  }, [focusComposer, hasMessages, isStreaming, messages?.length]);

  useEffect(() => {
    const list = messageListRef.current;
    if (!list) return;
    list.scrollTo({
      top: list.scrollHeight,
      behavior: isStreaming ? 'auto' : 'smooth',
    });
  }, [isStreaming, messages]);

  const submitMessage = useCallback((value) => {
    const text = value.trim();
    if (!text || isStreaming) return;
    setDraft('');
    if (inputRef.current) inputRef.current.style.height = 'auto';
    onSend(text);
  }, [isStreaming, onSend]);

  const handleSubmit = (event) => {
    event.preventDefault();
    submitMessage(draft);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submitMessage(draft);
    }
  };

  const handleDraftChange = (event) => {
    setDraft(event.target.value);
    event.target.style.height = 'auto';
    event.target.style.height = `${Math.min(event.target.scrollHeight, 112)}px`;
  };

  return (
    <div className="chat-content" aria-busy={isStreaming}>
      <div className="message-list" ref={messageListRef} aria-live="polite">
        {!hasMessages ? (
          <section className="empty-state">
            <div className="empty-state-icon" aria-hidden="true">
              <MessageCircle size={22} />
            </div>
            <p className="eyebrow">Adaptive interview</p>
            <h1>Ready when you are.</h1>
            <p className="empty-state-copy">
              Begin with an introduction or jump directly into a focused coding round.
            </p>
            <div className="starter-prompts" aria-label="Suggested messages">
              {STARTER_PROMPTS.map((prompt) => (
                <button key={prompt} type="button" onClick={() => submitMessage(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>
          </section>
        ) : (
          messages.map((message) => {
            const isAssistant = message.role === 'assistant';
            const isError = message.content?.includes('[Connection error:')
              || message.content?.includes('[Review error:');

            return (
              <article
                key={message.id}
                className={`message-row ${message.role} ${message.streaming ? 'streaming' : ''}`}
              >
                {isAssistant && (
                  <div className="message-avatar" aria-hidden="true">
                    <Bot size={15} />
                  </div>
                )}
                <div className="message-stack">
                  <span className="message-author">{isAssistant ? 'Interviewer' : 'You'}</span>
                  <div className={`message ${message.role} ${isError ? 'error' : ''}`}>
                    {message.content ? (
                      <span className="message-copy">{message.content}</span>
                    ) : message.streaming ? (
                      <span className="typing-indicator" aria-label="Interviewer is responding">
                        <i />
                        <i />
                        <i />
                      </span>
                    ) : null}
                    {message.streaming && message.content && <span className="cursor" />}
                  </div>
                </div>
              </article>
            );
          })
        )}
      </div>

      <form onSubmit={handleSubmit} className="chat-input-area">
        <div className={`chat-input-wrapper ${isStreaming ? 'is-streaming' : ''}`}>
          <textarea
            ref={inputRef}
            autoFocus
            rows={1}
            value={draft}
            placeholder={hasMessages ? 'Type your answer…' : 'Introduce yourself…'}
            readOnly={isStreaming}
            aria-label="Message the interviewer"
            aria-disabled={isStreaming}
            onChange={handleDraftChange}
            onKeyDown={handleKeyDown}
          />
          <button
            type="submit"
            disabled={isStreaming || !draft.trim()}
            aria-label="Send message"
            title="Send message"
          >
            <Send size={17} />
          </button>
        </div>
        <div className="composer-meta">
          <span>{isStreaming ? 'Interviewer is responding…' : 'Enter to send · Shift + Enter for a new line'}</span>
          <span className="composer-status"><i /> AG-UI connected</span>
        </div>
      </form>
    </div>
  );
}
