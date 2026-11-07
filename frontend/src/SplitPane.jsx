import React, { useCallback, useEffect, useRef, useState } from 'react';

const MIN_EDITOR_WIDTH = 32;
const MAX_EDITOR_WIDTH = 72;

export default function SplitPane({ value, onResize }) {
  const [dragging, setDragging] = useState(false);
  const cleanupRef = useRef(null);

  const stopDragging = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setDragging(false);
    document.body.classList.remove('is-resizing');
  }, []);

  const startDragging = useCallback((event) => {
    event.preventDefault();
    const container = event.currentTarget.parentElement;
    if (!container) return;

    const move = (pointerEvent) => {
      const rect = container.getBoundingClientRect();
      const rawWidth = ((pointerEvent.clientX - rect.left) / rect.width) * 100;
      onResize(Math.min(Math.max(rawWidth, MIN_EDITOR_WIDTH), MAX_EDITOR_WIDTH));
    };

    const finish = () => stopDragging();
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', finish, { once: true });
    cleanupRef.current = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', finish);
    };
    setDragging(true);
    document.body.classList.add('is-resizing');
  }, [onResize, stopDragging]);

  const handleKeyDown = (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();

    if (event.key === 'Home') onResize(MIN_EDITOR_WIDTH);
    else if (event.key === 'End') onResize(MAX_EDITOR_WIDTH);
    else onResize(Math.min(Math.max(
      value + (event.key === 'ArrowLeft' ? -2 : 2),
      MIN_EDITOR_WIDTH,
    ), MAX_EDITOR_WIDTH));
  };

  useEffect(() => stopDragging, [stopDragging]);

  return (
    <div
      className={`split-handle ${dragging ? 'is-dragging' : ''}`}
      role="separator"
      aria-label="Resize code and interview panels"
      aria-orientation="vertical"
      aria-valuemin={MIN_EDITOR_WIDTH}
      aria-valuemax={MAX_EDITOR_WIDTH}
      aria-valuenow={Math.round(value)}
      tabIndex={0}
      title="Drag or use arrow keys to resize panels"
      onPointerDown={startDragging}
      onKeyDown={handleKeyDown}
    >
      <span aria-hidden="true" />
    </div>
  );
}
