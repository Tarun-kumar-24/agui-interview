import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Maximize2, Minimize2 } from 'lucide-react';

export default function SplitPane({ editorOpen, onToggle }) {
  const [dragging, setDragging] = useState(false);
  const [editorFlex, setEditorFlex] = useState(50);
  const containerRef = useRef(null);

  const minEditor = 25;
  const maxEditor = 80;

  const startDrag = useCallback((e) => {
    setDragging(true);
  }, []);

  useEffect(() => {
    if (!dragging) return;
    const move = (e) => {
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      let pct = (x / rect.width) * 100;
      pct = Math.min(Math.max(pct, minEditor), maxEditor);
      setEditorFlex(pct);
    };
    const up = () => setDragging(false);
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    return () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
  }, [dragging]);

  return (
    <>
      <div
        ref={containerRef}
        className="split-handle"
        onMouseDown={startDrag}
        title="Drag to resize panels"
        style={{
          flex: '0 0 8px',
          background: dragging ? '#3b82f6' : '#1e293b',
          cursor: 'ew-resize',
          userSelect: 'none',
        }}
      />
      <button
        className="toggle-btn"
        onClick={onToggle}
        title={editorOpen ? 'Hide editor (chat only)' : 'Show editor'}
        style={{
          position: 'absolute',
          left: editorOpen ? '50%' : 'calc(100% - 40px)',
          top: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 20,
          background: '#0b1120',
          border: '1px solid #334155',
          color: '#e2e8f0',
          padding: '6px 10px',
          borderRadius: '6px',
          cursor: 'pointer',
          fontSize: '0.8rem',
          opacity: editorOpen ? 0.7 : 1,
          pointerEvents: editorOpen ? 'auto' : 'auto',
        }}
      >
        {editorOpen ? (
          <>
            <Minimize2 size={14} />
            <span style={{ marginLeft: 4, fontSize: '0.75rem' }}>Hide Editor</span>
          </>
        ) : (
          <>
            <Maximize2 size={14} />
            <span style={{ marginLeft: 4, fontSize: '0.75rem' }}>Show Editor</span>
          </>
        )}
      </button>
    </>
  );
}