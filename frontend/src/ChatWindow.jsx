import React from 'react';
import { Send, Bot, MessageCircle } from 'lucide-react';

export default function ChatWindow({ messages, isStreaming, onSend }) {
  const inputRef = React.useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    const input = inputRef.current;
    const text = input.value.trim();
    if (!text) return;
    onSend(text);
    input.value = '';
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!messages || messages.length === 0) {
    return (
      <div className="chat-content">
        <div className="empty-state">
          <MessageCircle size={26} style={{ marginBottom: 8 }} />
          <p>Start the interview — type a message below to begin.</p>
        </div>
        <form onSubmit={handleSubmit} className="chat-input-area">
          <div className="chat-input-wrapper">
            <input
              ref={inputRef}
              placeholder="Say hello to your interviewer..."
              disabled={isStreaming}
              onKeyDown={handleKeyDown}
            />
            <button type="submit" disabled={isStreaming || !inputRef.current?.value.trim()}>
              <Send size={18} />
            </button>
          </div>
          <div className="hint">
            Tip: write code in the Monaco Editor on the left, then chat — the interviewer can see
            your code and respond to it.
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="chat-content">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`message ${msg.role} ${msg.streaming ? 'streaming' : ''}`}
        >
          {msg.role === 'assistant' && <Bot size={16} style={{ marginRight: 6 }} />}
          {msg.content}
          {msg.streaming && <span className="cursor"></span>}
        </div>
      ))}
      <form onSubmit={handleSubmit} className="chat-input-area">
        <div className="chat-input-wrapper">
          <input
            ref={inputRef}
            placeholder="Type your answer..."
            disabled={isStreaming}
            onKeyDown={handleKeyDown}
          />
          <button type="submit" disabled={isStreaming || !inputRef.current?.value.trim()}>
            <Send size={18} />
          </button>
        </div>
        <div className="hint">
          Tip: write code in the Monaco Editor on the left, then chat — the interviewer can see
          your code and respond to it.
        </div>
      </form>
    </div>
  );
}