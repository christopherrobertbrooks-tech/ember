import { useState, useEffect, useRef, useCallback } from 'react';

const API_KEY = "ember-secret-key-123";
const WS_URL = (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + window.location.host + '/ws';

export function useEmberSocket() {
  const [messages, setMessages] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isBotTyping, setIsBotTyping] = useState(false);
  const ws = useRef(null);
  const audioQueue = useRef([]);
  const isPlayingAudio = useRef(false);
  const currentAudio = useRef(null);
  const isAudioMuted = useRef(false);

  const connect = useCallback(() => {
    ws.current = new WebSocket(WS_URL);

    ws.current.onopen = () => {
      console.log("WebSocket Connected");
      setIsConnected(true);
      // Send initial handshake
      ws.current.send(JSON.stringify({ api_key: API_KEY }));
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'stream_start':
          setIsBotTyping(true);
          isAudioMuted.current = false;
          break;
        case 'text':
          setMessages(prev => {
            if (prev.length === 0 || prev[prev.length - 1].role !== 'bot' || prev[prev.length - 1].image) {
              return [...prev, { role: 'bot', content: data.chunk, id: Date.now() }];
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
          setMessages(prev => [...prev, { role: 'bot', content: '', image: `data:image/png;base64,${data.data}`, id: Date.now() }]);
          break;
        case 'audio':
          if (isAudioMuted.current) break;
          audioQueue.current.push(data.data);
          playNextAudio();
          break;
        case 'error':
          console.error("Engine error:", data.message);
          setMessages(prev => [...prev, { role: 'system', content: `Error: ${data.message}`, id: Date.now() }]);
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

    ws.current.onclose = () => {
      console.log("WebSocket Disconnected");
      setIsConnected(false);
      setIsBotTyping(false);
      setTimeout(connect, 3000); // Reconnect loop
    };

    ws.current.onerror = (err) => {
      console.error("WebSocket Error:", err);
      ws.current.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [connect]);

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

  const sendMessage = (text, imgB64 = null) => {
    if (text.trim() === '' && !imgB64) return;
    
    setMessages(prev => [...prev, { role: 'user', content: text, image: imgB64, id: Date.now() }]);
    
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        user_text: text,
        attached_image_b64: imgB64
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

  return { messages, sendMessage, isConnected, isBotTyping, clearMessages, addMessageToChat, stopAudio };
}
