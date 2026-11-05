import { useCallback, useEffect, useRef, useState } from 'react';

const STORAGE_KEY = 'agui-interview-voice-enabled';
const DEFAULT_VOICE = 'en-US-AndrewMultilingualNeural';
const MAX_SEGMENT_LENGTH = 280;

function speechPreference() {
  if (typeof window === 'undefined') return true;
  return window.localStorage.getItem(STORAGE_KEY) !== 'false';
}

export function cleanSpeechText(value) {
  return value
    .replace(/```[\s\S]*?```/g, ' code sample ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)]\([^)]+\)/g, '$1')
    .replace(/https?:\/\/\S+/g, 'link')
    .replace(/[*_#>|~]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function splitSpeechSegments(value, flush = false) {
  const text = value.replace(/\r/g, '').replace(/\n+/g, ' ');
  const segments = [];
  const boundary = /[.!?](?:["'”’)]*)?(?=\s|$)/g;
  let consumed = 0;
  let match;

  while ((match = boundary.exec(text)) !== null) {
    const end = match.index + match[0].length;
    const segment = cleanSpeechText(text.slice(consumed, end));
    if (segment) segments.push(segment);
    consumed = end;
  }

  let remainder = text.slice(consumed).trimStart();
  while (remainder.length > MAX_SEGMENT_LENGTH) {
    const splitAt = remainder.lastIndexOf(' ', MAX_SEGMENT_LENGTH);
    const end = splitAt > 80 ? splitAt : MAX_SEGMENT_LENGTH;
    const segment = cleanSpeechText(remainder.slice(0, end));
    if (segment) segments.push(segment);
    remainder = remainder.slice(end).trimStart();
  }

  if (flush) {
    const finalSegment = cleanSpeechText(remainder);
    if (finalSegment) segments.push(finalSegment);
    remainder = '';
  }

  return { segments, remainder };
}

function waitForPlayback(audio) {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
    };
    const handleEnded = () => {
      cleanup();
      resolve();
    };
    const handleError = () => {
      cleanup();
      reject(new Error('The browser could not play the synthesized speech.'));
    };

    audio.addEventListener('ended', handleEnded, { once: true });
    audio.addEventListener('error', handleError, { once: true });
  });
}

function speakWithBrowser(text) {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      reject(new Error('No browser speech fallback is available.'));
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    utterance.voice = voices.find((voice) => /Microsoft.*(Andrew|Ava)/i.test(voice.name))
      || voices.find((voice) => /Google US English|Samantha/i.test(voice.name))
      || voices.find((voice) => voice.lang?.startsWith('en-US'))
      || null;
    utterance.rate = 1.06;
    utterance.pitch = 1;
    utterance.onend = () => resolve();
    utterance.onerror = (event) => reject(new Error(event.error || 'Browser speech failed.'));
    window.speechSynthesis.speak(utterance);
  });
}

export default function useEdgeTts(baseUrl) {
  const [enabled, setEnabled] = useState(speechPreference);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState(null);

  const enabledRef = useRef(enabled);
  const audioRef = useRef(null);
  const buffersRef = useRef(new Map());
  const queueRef = useRef([]);
  const processingRef = useRef(false);
  const generationRef = useRef(0);
  const controllersRef = useRef(new Set());
  const endpoint = `${baseUrl.replace(/\/$/, '')}/tts`;

  const stop = useCallback(() => {
    generationRef.current += 1;
    buffersRef.current.clear();
    queueRef.current = [];
    controllersRef.current.forEach((controller) => controller.abort());
    controllersRef.current.clear();

    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }

    processingRef.current = false;
    setIsSpeaking(false);
    setSpeakingMessageId(null);
  }, []);

  const playQueue = useCallback(async () => {
    if (processingRef.current || !enabledRef.current) return;
    processingRef.current = true;

    while (enabledRef.current && queueRef.current.length) {
      const item = queueRef.current.shift();
      if (!item || item.generation !== generationRef.current) continue;

      let objectUrl = null;
      try {
        const blob = await item.audio;
        if (item.generation !== generationRef.current || !enabledRef.current) continue;
        setSpeakingMessageId(item.messageId);
        setIsSpeaking(true);

        if (blob?.size >= 256) {
          try {
            const audio = audioRef.current || new Audio();
            audioRef.current = audio;
            objectUrl = URL.createObjectURL(blob);
            audio.src = objectUrl;
            audio.preload = 'auto';
            await audio.play();
            await waitForPlayback(audio);
          } catch (edgePlaybackError) {
            console.warn('Edge TTS audio failed; using browser speech:', edgePlaybackError.message);
            await speakWithBrowser(item.text);
          }
        } else {
          await speakWithBrowser(item.text);
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          console.warn('Edge TTS playback skipped:', error.message);
        }
      } finally {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
      }
    }

    processingRef.current = false;
    setIsSpeaking(false);
    setSpeakingMessageId(null);

    if (enabledRef.current && queueRef.current.length) {
      void playQueue();
    }
  }, []);

  const enqueue = useCallback((messageId, text) => {
    if (!enabledRef.current || !messageId || !text) return;

    const controller = new AbortController();
    const generation = generationRef.current;
    controllersRef.current.add(controller);
    const audio = fetch(endpoint, {
      method: 'POST',
      headers: {
        Accept: 'audio/mpeg',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text, voice: DEFAULT_VOICE }),
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`TTS request failed with HTTP ${response.status}.`);
        return response.blob();
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          console.warn('Edge TTS synthesis skipped:', error.message);
        }
        return null;
      })
      .finally(() => controllersRef.current.delete(controller));

    queueRef.current.push({ messageId, text, audio, generation });
    void playQueue();
  }, [endpoint, playQueue]);

  const pushChunk = useCallback((messageId, delta) => {
    if (!enabledRef.current || !messageId || !delta) return;
    const buffered = `${buffersRef.current.get(messageId) || ''}${delta}`;
    const { segments, remainder } = splitSpeechSegments(buffered);
    buffersRef.current.set(messageId, remainder);
    segments.forEach((segment) => enqueue(messageId, segment));
  }, [enqueue]);

  const flushMessage = useCallback((messageId) => {
    if (!messageId) return;
    const buffered = buffersRef.current.get(messageId) || '';
    buffersRef.current.delete(messageId);
    if (!enabledRef.current || !buffered) return;
    const { segments } = splitSpeechSegments(buffered, true);
    segments.forEach((segment) => enqueue(messageId, segment));
  }, [enqueue]);

  const beginTurn = useCallback(() => {
    stop();
    if (!audioRef.current && typeof Audio !== 'undefined') {
      audioRef.current = new Audio();
    }
  }, [stop]);

  const toggle = useCallback(() => {
    setEnabled((current) => {
      const next = !current;
      enabledRef.current = next;
      window.localStorage.setItem(STORAGE_KEY, String(next));
      if (!next) stop();
      return next;
    });
  }, [stop]);

  useEffect(() => {
    enabledRef.current = enabled;
    window.localStorage.setItem(STORAGE_KEY, String(enabled));
  }, [enabled]);

  useEffect(() => () => stop(), [stop]);

  return {
    enabled,
    isSpeaking,
    speakingMessageId,
    beginTurn,
    pushChunk,
    flushMessage,
    toggle,
    stop,
  };
}
