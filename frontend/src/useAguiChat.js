import { HttpAgent } from '@ag-ui/client';
import { useCallback, useEffect, useRef, useState } from 'react';

const INITIAL_CODING_STATE = {
  active: false,
  visible: false,
  status: 'NOT_STARTED',
  language: 'python',
  code: '',
  question: null,
  questionRevision: 0,
};

export default function useAguiChat(baseUrl, threadId) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [codingState, setCodingState] = useState(INITIAL_CODING_STATE);

  const messagesRef = useRef([]);
  const sessionIdRef = useRef(null);
  const codingStateRef = useRef(INITIAL_CODING_STATE);
  const abortRef = useRef(null);
  const backgroundAbortRef = useRef(null);
  const requestInFlightRef = useRef(null);
  const snapshotTimerRef = useRef(null);
  const inactivityTimerRef = useRef(null);
  const lastCodeTimeRef = useRef(Date.now());
  const lastInactivityActivityRef = useRef(null);

  const updateMessages = useCallback((updater) => {
    setMessages((current) => {
      const next = typeof updater === 'function' ? updater(current) : updater;
      messagesRef.current = next;
      return next;
    });
  }, []);

  const updateCodingState = useCallback((updater) => {
    setCodingState((current) => {
      const next = typeof updater === 'function' ? updater(current) : updater;
      codingStateRef.current = next;
      return next;
    });
  }, []);

  const setCurrentSessionId = useCallback((nextSessionId) => {
    if (!nextSessionId) return;
    sessionIdRef.current = nextSessionId;
    setSessionId(nextSessionId);
  }, []);

  const applySessionState = useCallback((eventState) => {
    if (!eventState) return;
    setCurrentSessionId(eventState.sessionId);

    const serverState = eventState.interviewState;
    if (!serverState || typeof serverState !== 'object') return;

    updateCodingState((current) => {
      const active = Boolean(serverState.coding_round_active);
      const incomingRevision = serverState.question_revision ?? current.questionRevision;
      const canApplyQuestion = incomingRevision >= current.questionRevision;

      return {
        ...current,
        active,
        visible: active ? current.visible : false,
        status: serverState.status || current.status,
        language: serverState.selected_language || current.language,
        question: canApplyQuestion
          ? (serverState.current_question || current.question)
          : current.question,
        questionRevision: Math.max(current.questionRevision, incomingRevision),
      };
    });
  }, [setCurrentSessionId, updateCodingState]);

  const applyToolCall = useCallback((name, args) => {
    if (name === 'open_editor') {
      updateCodingState((current) => {
        const questionId = args.question_id || current.question?.question_id || null;
        const incomingRevision = args.question_revision ?? current.questionRevision;
        if (incomingRevision < current.questionRevision) return current;

        const isNewQuestion = Boolean(questionId && questionId !== current.question?.question_id);
        const replaceCode = args.replace_code === true
          || (args.replace_code !== false && (isNewQuestion || !current.question));
        const question = {
          ...(isNewQuestion ? {} : current.question),
          question_id: questionId,
          question_text: args.task || current.question?.question_text || '',
          concept: args.concept || current.question?.concept || '',
          difficulty: args.difficulty || current.question?.difficulty || '',
          starter_code: args.initial_code || '',
          language: args.language || current.language,
        };

        if (replaceCode) {
          lastCodeTimeRef.current = Date.now();
          lastInactivityActivityRef.current = null;
        }

        return {
          ...current,
          active: true,
          visible: true,
          status: 'CODING_ACTIVE',
          language: args.language || current.language,
          code: replaceCode ? (args.initial_code || '') : current.code,
          question,
          questionRevision: Math.max(current.questionRevision, incomingRevision),
        };
      });
    } else if (name === 'close_editor') {
      updateCodingState((current) => ({
        ...current,
        active: args.end_interview ? false : current.active,
        visible: false,
        status: args.end_interview ? 'ENDED' : current.status,
      }));
    }
  }, [updateCodingState]);

  const finishAssistantMessage = useCallback((assistantId) => {
    if (!assistantId) return;
    updateMessages((current) => current
      .map((message) => (
        message.id === assistantId ? { ...message, streaming: false } : message
      ))
      .filter((message) => message.id !== assistantId || message.content.trim())
    );
  }, [updateMessages]);

  const buildAgentState = useCallback((requestType) => {
    const current = codingStateRef.current;
    return {
      requestType,
      editorContent: current.code,
      editorOpen: current.active,
      editorLanguage: current.language,
      sessionId: sessionIdRef.current,
      questionId: current.question?.question_id || null,
      questionRevision: current.questionRevision,
    };
  }, []);

  const sendRequest = useCallback(async ({
    requestType,
    requestMessages,
    assistantId,
    abortController,
  }) => {
    const runId = `run_${crypto.randomUUID()}`;
    let displayMessageId = assistantId;
    let displayMessageCreated = Boolean(assistantId);
    let runError = null;

    const agent = new HttpAgent({
      url: baseUrl,
      threadId,
      initialMessages: requestMessages,
      initialState: buildAgentState(requestType),
    });

    await agent.runAgent(
      {
        runId,
        tools: [],
        context: [],
        forwardedProps: {},
        abortController,
      },
      {
        onTextMessageContentEvent: ({ event }) => {
          if (!displayMessageCreated) {
            displayMessageId = event.messageId || `assistant_${crypto.randomUUID()}`;
            displayMessageCreated = true;
            updateMessages((current) => [
              ...current,
              { id: displayMessageId, role: 'assistant', content: '', streaming: false },
            ]);
          }
          updateMessages((current) => current.map((message) => (
            message.id === displayMessageId
              ? { ...message, content: message.content + event.delta }
              : message
          )));
        },
        onToolCallEndEvent: ({ toolCallName, toolCallArgs }) => {
          applyToolCall(toolCallName, toolCallArgs);
        },
        onStateSnapshotEvent: ({ event }) => {
          applySessionState(event.snapshot);
        },
        onRunErrorEvent: ({ event }) => {
          runError = new Error(event.message || 'Agent run failed');
        },
        onRunFinishedEvent: () => {
          finishAssistantMessage(displayMessageId);
        },
      },
    );

    if (runError) throw runError;
    finishAssistantMessage(displayMessageId);
  }, [applySessionState, applyToolCall, baseUrl, buildAgentState, finishAssistantMessage, threadId, updateMessages]);

  const beginForegroundRequest = useCallback(() => {
    if (requestInFlightRef.current === 'foreground') return false;
    if (requestInFlightRef.current === 'background') {
      const backgroundController = backgroundAbortRef.current;
      backgroundAbortRef.current = null;
      backgroundController?.abort();
    }
    requestInFlightRef.current = 'foreground';
    return true;
  }, []);

  const sendMessage = useCallback(async (userText) => {
    const text = userText?.trim();
    if (!text || !beginForegroundRequest()) return;

    setIsStreaming(true);

    const userMessage = {
      id: `user_${crypto.randomUUID()}`,
      role: 'user',
      content: text,
      streaming: false,
    };
    const assistantId = `assistant_${crypto.randomUUID()}`;
    const requestMessages = [
      ...messagesRef.current
        .filter((message) => message.content?.trim())
        .map(({ id, role, content }) => ({ id, role, content })),
      { id: userMessage.id, role: 'user', content: text },
    ];

    updateMessages((current) => [
      ...current,
      userMessage,
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await sendRequest({
        requestType: 'chat',
        requestMessages,
        assistantId,
        abortController: controller,
      });
    } catch (error) {
      if (error.name !== 'AbortError') {
        updateMessages((current) => current.map((message) => (
          message.id === assistantId
            ? { ...message, content: `${message.content}\n\n[Connection error: ${error.message}]`, streaming: false }
            : message
        )));
      }
    } finally {
      requestInFlightRef.current = null;
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [beginForegroundRequest, sendRequest, updateMessages]);

  const sendBackgroundRequest = useCallback(async (requestType) => {
    const current = codingStateRef.current;
    if (
      requestInFlightRef.current
      || !sessionIdRef.current
      || !current.active
      || !current.question
    ) return false;

    const controller = new AbortController();
    requestInFlightRef.current = 'background';
    backgroundAbortRef.current = controller;
    try {
      await sendRequest({
        requestType,
        requestMessages: messagesRef.current
          .filter((message) => message.content?.trim())
          .map(({ id, role, content }) => ({ id, role, content })),
        abortController: controller,
      });
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error(`${requestType} request failed:`, error);
      }
    } finally {
      if (backgroundAbortRef.current === controller) {
        backgroundAbortRef.current = null;
        if (requestInFlightRef.current === 'background') {
          requestInFlightRef.current = null;
        }
      }
    }
    return true;
  }, [sendRequest]);

  const requestCodeReview = useCallback(async () => {
    const current = codingStateRef.current;
    if (!current.active || !current.question || !current.code.trim() || !beginForegroundRequest()) {
      return;
    }

    setIsStreaming(true);

    const userMessage = {
      id: `user_${crypto.randomUUID()}`,
      role: 'user',
      content: "I've completed my solution. Please review the latest editor code.",
      streaming: false,
    };
    const assistantId = `assistant_${crypto.randomUUID()}`;
    const requestMessages = [
      ...messagesRef.current
        .filter((message) => message.content?.trim())
        .map(({ id, role, content }) => ({ id, role, content })),
      { id: userMessage.id, role: 'user', content: userMessage.content },
    ];

    updateMessages((messages) => [
      ...messages,
      userMessage,
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await sendRequest({
        requestType: 'review',
        requestMessages,
        assistantId,
        abortController: controller,
      });
    } catch (error) {
      updateMessages((messages) => messages.map((message) => (
        message.id === assistantId
          ? { ...message, content: `[Review error: ${error.message}]`, streaming: false }
          : message
      )));
    } finally {
      requestInFlightRef.current = null;
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [beginForegroundRequest, sendRequest, updateMessages]);

  const stopTimers = useCallback(() => {
    if (snapshotTimerRef.current) clearInterval(snapshotTimerRef.current);
    if (inactivityTimerRef.current) clearInterval(inactivityTimerRef.current);
    snapshotTimerRef.current = null;
    inactivityTimerRef.current = null;
  }, []);

  const startTimers = useCallback(() => {
    stopTimers();
    lastCodeTimeRef.current = Date.now();
    lastInactivityActivityRef.current = null;

    snapshotTimerRef.current = setInterval(() => {
      void sendBackgroundRequest('snapshot');
    }, 60000);

    inactivityTimerRef.current = setInterval(() => {
      const activityMarker = lastCodeTimeRef.current;
      if (
        Date.now() - activityMarker >= 120000
        && lastInactivityActivityRef.current !== activityMarker
      ) {
        void sendBackgroundRequest('inactivity').then((started) => {
          if (started && lastCodeTimeRef.current === activityMarker) {
            lastInactivityActivityRef.current = activityMarker;
          }
        });
      }
    }, 30000);
  }, [sendBackgroundRequest, stopTimers]);

  const setEditorCode = useCallback((code) => {
    lastCodeTimeRef.current = Date.now();
    lastInactivityActivityRef.current = null;
    updateCodingState((current) => ({ ...current, code: code ?? '' }));
  }, [updateCodingState]);

  const setEditorLanguage = useCallback((language) => {
    updateCodingState((current) => ({ ...current, language }));
  }, [updateCodingState]);

  const setEditorVisible = useCallback((nextValue) => {
    updateCodingState((current) => ({
      ...current,
      visible: current.active
        ? (typeof nextValue === 'function' ? nextValue(current.visible) : Boolean(nextValue))
        : false,
    }));
  }, [updateCodingState]);

  useEffect(() => () => {
    stopTimers();
    abortRef.current?.abort();
    backgroundAbortRef.current?.abort();
  }, [stopTimers]);

  return {
    messages,
    isStreaming,
    sendMessage,
    sessionId,
    codingMode: codingState.active,
    editorOpen: codingState.active && codingState.visible,
    setEditorOpen: setEditorVisible,
    editorTask: codingState.question?.question_text || '',
    editorCode: codingState.code,
    setEditorCode,
    editorLanguage: codingState.language,
    setEditorLanguage,
    currentQuestion: codingState.question,
    questionRevision: codingState.questionRevision,
    interviewStatus: codingState.status,
    startTimers,
    stopTimers,
    requestCodeReview,
    abort: () => {
      abortRef.current?.abort();
      backgroundAbortRef.current?.abort();
    },
  };
}
