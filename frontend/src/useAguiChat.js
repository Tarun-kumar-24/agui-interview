import { useState, useCallback, useRef } from 'react';

export default function useAguiChat(baseUrl, threadId) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorTask, setEditorTask] = useState('');
  const [editorInitialCode, setEditorInitialCode] = useState('');
  const [editorLanguage, setEditorLanguage] = useState('python');
  const abortRef = useRef(null);
  const toolCallBufferRef = useRef({});
  const interviewStateRef = useRef({
    questions_asked: 0,
    coding_confirmation_pending: false,
    coding_round_active: false,
  });

  const sendMessage = useCallback(
    async (userText, editorContent, history) => {
      if (!userText || !userText.trim()) return;
      setIsStreaming(true);

      const runId = 'run_' + crypto.randomUUID();
      const assistantId = 'assistant_' + runId;
      const userId = 'user_' + crypto.randomUUID();

      const interviewState = interviewStateRef.current;

      const input = {
        threadId: threadId,
        runId: runId,
        state: { 
          editorContent: editorContent || '', 
          editorOpen: editorOpen,
          interviewState: interviewState
        },
        messages: [
          ...(history || []),
          { id: userId, role: 'user', content: userText },
        ],
        tools: [],
        context: [],
        forwardedProps: {},
      };

      setMessages((prev) => [
        ...prev,
        { id: userId, role: 'user', content: userText, streaming: false },
        { id: assistantId, role: 'assistant', content: '', streaming: true },
      ]);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(baseUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
          },
          body: JSON.stringify(input),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error('HTTP ' + response.status);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          if (controller.signal.aborted) break;
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';

          for (const part of parts) {
            const dataLine = part.split('\n').find((line) => line.startsWith('data: '));
            if (!dataLine) continue;
            try {
              const event = JSON.parse(dataLine.slice(6));

              if (event.type === 'TEXT_MESSAGE_CHUNK' && event.delta) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: m.content + event.delta } : m
                  )
                );
              } else if (event.type === 'TOOL_CALL_CHUNK') {
                const tcid = event.toolCallId;
                if (tcid) {
                  if (!toolCallBufferRef.current[tcid]) {
                    toolCallBufferRef.current[tcid] = { name: '', args: '' };
                  }
                  if (event.toolCallName) {
                    toolCallBufferRef.current[tcid].name = event.toolCallName;
                  }
                  if (event.delta) {
                    toolCallBufferRef.current[tcid].args += event.delta;
                  }
                  const tc = toolCallBufferRef.current[tcid];
                  if (tc.name && tc.args) {
                    try {
                      const args = JSON.parse(tc.args);
                      if (tc.name === 'open_editor') {
                        setEditorOpen(true);
                        setEditorTask(args.task || '');
                        setEditorInitialCode(args.initial_code || '');
                        setEditorLanguage(args.language || 'python');
                      } else if (tc.name === 'close_editor') {
                        setEditorOpen(false);
                        setEditorTask('');
                        setEditorInitialCode('');
                      }
                    } catch (e) {
                    }
                  }
                }
              } else if (event.type === 'RUN_FINISHED') {
                setMessages((prev) =>
                  prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
                );
                setIsStreaming(false);
                toolCallBufferRef.current = {};
                
                // Update interview state from response
                if (event.state && event.state.interviewState) {
                  interviewStateRef.current = {
                    ...interviewStateRef.current,
                    ...event.state.interviewState,
                  };
                }
              } else if (event.type === 'RUN_ERROR') {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? {
                          ...m,
                          content: m.content + '\n\n[Agent error: ' + event.message + ']',
                          streaming: false,
                        }
                      : m
                  )
                );
                setIsStreaming(false);
                toolCallBufferRef.current = {};
              }
            } catch (e) {
            }
          }
        }
      } catch (err) {
        if (err.name === 'AbortError') return;
        setIsStreaming(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: m.content + '\n\n[Connection error: ' + err.message + ']',
                  streaming: false,
                }
              : m
          )
        );
      }
    },
    [baseUrl, threadId, editorOpen]
  );

  return {
    messages,
    setMessages,
    isStreaming,
    sendMessage,
    editorOpen,
    setEditorOpen,
    editorTask,
    editorInitialCode,
    editorLanguage,
    interviewState: interviewStateRef.current,
    abort: () => {
      if (abortRef.current) abortRef.current.abort();
    },
  };
}
