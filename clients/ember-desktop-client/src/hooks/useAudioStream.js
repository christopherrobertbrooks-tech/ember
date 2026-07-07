import { useState, useEffect, useRef, useCallback } from 'react';

const workletCode = `
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input.length > 0) {
      const channelData = input[0];
      // Convert Float32 [-1, 1] to Int16 [-32768, 32767]
      const int16Data = new Int16Array(channelData.length);
      for (let i = 0; i < channelData.length; i++) {
        let s = Math.max(-1, Math.min(1, channelData[i]));
        int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      this.port.postMessage(int16Data.buffer, [int16Data.buffer]);
    }
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);
`;

export function useAudioStream({ onWakeWord, onCommandTranscribed, onInterrupt }) {
  const [isListening, setIsListening] = useState(false);
  const [isCommandMode, setIsCommandMode] = useState(false);
  
  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const streamRef = useRef(null);
  const workletNodeRef = useRef(null);

  const startStream = useCallback(async () => {
    try {
      // Connect WebSocket via the Vite dev server proxy
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/audio`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "wake_word_detected") {
            setIsCommandMode(true);
            if (onWakeWord) onWakeWord();
          } else if (data.type === "interrupt_detected") {
            setIsCommandMode(true);
            if (onInterrupt) onInterrupt();
          } else if (data.type === "command_transcribed") {
            if (onCommandTranscribed) onCommandTranscribed(data.text);
          } else if (data.type === "command_empty") {
            setIsCommandMode(false);
            // Optionally play a failure chime here
          }
        } catch (e) { console.error(e); }
      };

      await new Promise((resolve) => {
        ws.onopen = resolve;
      });

      // Start Audio Context at 16kHz
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000,
      });
      audioCtxRef.current = audioCtx;
      await audioCtx.resume();

      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true
        } 
      });
      streamRef.current = stream;

      const source = audioCtx.createMediaStreamSource(stream);

      // Load Worklet
      const blob = new Blob([workletCode], { type: 'application/javascript' });
      const url = URL.createObjectURL(blob);
      await audioCtx.audioWorklet.addModule(url);

      const workletNode = new AudioWorkletNode(audioCtx, 'pcm-processor');
      workletNodeRef.current = workletNode;

      workletNode.port.onmessage = (e) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(e.data);
        }
      };

      source.connect(workletNode);
      // Optional: connect to destination with gain=0 if required to pull data
      const gainNode = audioCtx.createGain();
      gainNode.gain.value = 0;
      workletNode.connect(gainNode);
      gainNode.connect(audioCtx.destination);

      setIsListening(true);
    } catch (err) {
      console.error("Audio streaming error:", err);
      stopStream();
    }
  }, [onWakeWord, onCommandTranscribed, onInterrupt]);

  const stopStream = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
    setIsListening(false);
    setIsCommandMode(false);
  }, []);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopStream();
    } else {
      startStream();
    }
  }, [isListening, startStream, stopStream]);

  const forceCommandMode = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "force_command" }));
      setIsCommandMode(true);
    }
  }, []);

  return {
    isListening,
    isCommandMode,
    toggleListening,
    startStream,
    stopStream,
    forceCommandMode
  };
}
