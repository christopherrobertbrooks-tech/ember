import { useState, useEffect, useRef, useCallback } from 'react';

const API_KEY = "ember-secret-key-123";
const WS_URL = (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + window.location.host + '/ws';

export function useEmberSocket() {
  const [messages, setMessages] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isBotTyping, setIsBotTyping] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [gesture, setGesture] = useState(null);
  const ws = useRef(null);
  const audioQueue = useRef([]);
  const isPlayingAudio = useRef(false);
  const currentAudio = useRef(null);
  const isAudioMuted = useRef(false);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);

  const connect = useCallback(() => {
    const socket = new WebSocket(WS_URL);
    ws.current = socket;
    let isMounted = true;

    socket.onopen = () => {
      console.log("WebSocket Connected");
      setIsConnected(true);
      // Send initial handshake
      socket.send(JSON.stringify({ api_key: API_KEY }));
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'stream_start':
          setIsBotTyping(true);
          isAudioMuted.current = false;
          break;
        case 'thinking':
          setIsThinking(data.status);
          break;
        case 'gesture':
          setGesture({ type: data.gesture, time: Date.now() });
          break;
        case 'text':
          setMessages(prev => {
            if (prev.length === 0 || prev[prev.length - 1].role !== 'bot' || prev[prev.length - 1].image) {
              return [...prev, { role: 'bot', content: data.chunk, id: Date.now() + Math.random() }];
            } else {
              const newMessages = [...prev];
              const lastIdx = newMessages.length - 1;
              newMessages[lastIdx] = { 
                ...newMessages[lastIdx], 
                content: newMessages[lastIdx].content + data.chunk 
              };
              return newMessages;
            }
          });
          break;
        case 'stream_done':
          setIsBotTyping(false);
          break;
        case 'image':
          setMessages(prev => [...prev, { role: 'bot', content: '', image: `data:image/png;base64,${data.data}`, id: Date.now() + Math.random() }]);
          break;
        case 'audio':
          if (isAudioMuted.current) break;
          audioQueue.current.push(data.data);
          playNextAudio();
          break;
        case 'error':
          console.error("Engine error:", data.message);
          setMessages(prev => [...prev, { role: 'system', content: `Error: ${data.message}`, id: Date.now() + Math.random() }]);
          setIsBotTyping(false);
          break;
        case 'ui_action':
          try {
            const actionData = typeof data.data === 'string' ? JSON.parse(data.data) : data.data;
            const event = new CustomEvent('ember-ui-action', { detail: actionData });
            window.dispatchEvent(event);
          } catch(e) {
            console.error("Failed to parse ui_action:", e);
          }
          break;
        default:
          break;
      }
    };

    socket.onclose = () => {
      setIsConnected(false);
      setIsBotTyping(false);
      if (isMounted) {
        setTimeout(connect, 3000); // Reconnect only if hook is still alive
      }
    };

    socket.onerror = (err) => {
      socket.close();
    };

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const cleanup = connect();
    return () => {
      if (cleanup) cleanup();
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [connect]);

  useEffect(() => {
    const handleTelemetry = (e) => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({
          type: 'memory_telemetry',
          ...e.detail
        }));
      }
    };
    window.addEventListener('ember-send-telemetry', handleTelemetry);
    return () => window.removeEventListener('ember-send-telemetry', handleTelemetry);
  }, []);

  const playNextAudio = async () => {
    if (isPlayingAudio.current || audioQueue.current.length === 0) return;
    
    isPlayingAudio.current = true;
    const base64Audio = audioQueue.current.shift();
    
    try {
      const byteCharacters = atob(base64Audio);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'audio/wav' });
      const url = URL.createObjectURL(blob);
      
      const audio = new Audio(url);
      currentAudio.current = audio;
      
      // Dispatch custom event for 3D VRM mouth sync
      window.dispatchEvent(new CustomEvent('ember-audio-start', { detail: { audio } }));
      
      // Connect to audio analyser in main window and forward amplitude via IPC
      if (window.electron) {
        try {
          if (!audioContextRef.current) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            audioContextRef.current = new AudioContextClass();
            analyserRef.current = audioContextRef.current.createAnalyser();
            analyserRef.current.fftSize = 256;
          }
          
          if (audioContextRef.current.state === 'suspended') {
            await audioContextRef.current.resume();
          }

          const source = audioContextRef.current.createMediaElementSource(audio);
          source.connect(analyserRef.current);
          analyserRef.current.connect(audioContextRef.current.destination);

          const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
          let animationTimerId;

          const sendAmplitude = () => {
            if (audio.paused || audio.ended) {
              clearTimeout(animationTimerId);
              window.electron.ipcRenderer.send('forward-to-companion', {
                channel: 'vrm-audio-amplitude',
                data: 0
              });
              return;
            }

            if (analyserRef.current) {
              analyserRef.current.getByteFrequencyData(dataArray);
              let sum = 0;
              for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i];
              }
              const average = sum / dataArray.length; // 0 to 255
              window.electron.ipcRenderer.send('forward-to-companion', {
                channel: 'vrm-audio-amplitude',
                data: average
              });
            }

            animationTimerId = setTimeout(sendAmplitude, 1000 / 30); // ~30fps
          };

          audio.addEventListener('play', () => {
            sendAmplitude();
          });
        } catch (err) {
          console.warn("Failed to set up audio analyser for companion window:", err);
        }
      }

      audio.onended = () => {
        isPlayingAudio.current = false;
        URL.revokeObjectURL(url);
        playNextAudio();
      };
      
      await audio.play();
    } catch (err) {
      console.error("Audio playback error", err);
      isPlayingAudio.current = false;
      playNextAudio();
    }
  };

  const sendMessage = (text, imgB64 = null, shareScreen = false) => {
    if (text.trim() === '' && !imgB64) return;
    
    setMessages(prev => [...prev, { role: 'user', content: text, image: imgB64, id: Date.now() + Math.random() }]);
    
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        user_text: text,
        attached_image_b64: imgB64,
        share_screen: shareScreen
      }));
    } else {
      setMessages(prev => [...prev, { role: 'system', content: 'Not connected to server', id: Date.now() }]);
    }
  };

  const clearMessages = () => setMessages([]);

  const addMessageToChat = (msg) => {
    setMessages(prev => [...prev, msg]);
  };

  const stopAudio = () => {
    isAudioMuted.current = true;
    audioQueue.current = [];
    if (currentAudio.current) {
      currentAudio.current.pause();
      currentAudio.current.currentTime = 0;
    }
    isPlayingAudio.current = false;
  };

  return { messages, sendMessage, isConnected, isBotTyping, isThinking, clearMessages, addMessageToChat,
    stopAudio,
    gesture
  };
}
