import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic, Image as ImageIcon, Palette, Ear, Camera, Monitor } from 'lucide-react';
import { useAudioStream } from '../hooks/useAudioStream';

export default function MessageInput({ onSendMessage, onGenerateArt, onInterrupt }) {
  const [text, setText] = useState('');
  const [attachedImage, setAttachedImage] = useState(null); // base64 string
  const fileInputRef = useRef(null);

  const playChime = () => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(600, audioCtx.currentTime);
      oscillator.frequency.exponentialRampToValueAtTime(1200, audioCtx.currentTime + 0.1);
      
      gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
      gainNode.gain.linearRampToValueAtTime(0.1, audioCtx.currentTime + 0.05);
      gainNode.gain.linearRampToValueAtTime(0, audioCtx.currentTime + 0.3);
      
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      
      oscillator.start();
      oscillator.stop(audioCtx.currentTime + 0.3);
    } catch (e) { console.error(e); }
  };

  const { isListening, isCommandMode, toggleListening, startStream, stopStream, forceCommandMode } = useAudioStream({
    onWakeWord: () => {
      playChime();
    },
    onCommandTranscribed: (transcribedText) => {
      if (transcribedText.trim()) {
        onSendMessage(transcribedText, attachedImage);
        setAttachedImage(null);
      }
    },
    onInterrupt: () => {
      if (onInterrupt) onInterrupt();
      playChime();
    }
  });

  // Listen to toggle event from companion window
  useEffect(() => {
    const handleToggle = () => {
      toggleListening();
    };
    window.addEventListener('toggle-audio-listening', handleToggle);
    return () => {
      window.removeEventListener('toggle-audio-listening', handleToggle);
    };
  }, [toggleListening]);

  const [shareScreen, setShareScreen] = useState(false);

  // Sync listening state to companion window
  useEffect(() => {
    if (window.electron) {
      window.electron.ipcRenderer.send('forward-to-companion', {
        channel: 'listening-state-changed',
        data: isListening
      });
    }
  }, [isListening]);

  const handleSend = () => {
    if (text.trim() || attachedImage) {
      onSendMessage(text, attachedImage, shareScreen);
      setText('');
      setAttachedImage(null);
    }
  };

  const handleGenerateArt = () => {
    if (text.trim()) {
      onGenerateArt(text);
      setText('');
    } else {
      alert("Please type a prompt before generating art.");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onloadend = () => {
      setAttachedImage(reader.result);
    };
    reader.readAsDataURL(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleCaptureWebcam = async () => {
    try {
      const res = await fetch('/api/capture_webcam', {
        method: 'POST',
        headers: { 'X-API-Key': 'ember-secret-key-123' }
      });
      const data = await res.json();
      if (data.image_base64) {
        setAttachedImage(`data:image/jpeg;base64,${data.image_base64}`);
      } else {
        alert("Webcam capture failed: " + (data.detail || "Webcam might be busy or missing. Make sure cv2 is installed."));
      }
    } catch (err) {
      alert("Error capturing webcam: " + err.message);
    }
  };

  return (
    <div className="input-area-wrapper" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      
      {/* Top utility row for actions */}
      <div style={{ display: 'flex', gap: '8px' }}>
        <button 
          className={`icon-btn ${isListening ? 'active-wake' : ''}`}
          onClick={toggleListening}
          title={isListening ? "Disable Wake Word" : "Enable Wake Word"}
          style={{ color: isListening ? 'var(--accent-primary)' : 'var(--text-secondary)', backgroundColor: isListening ? 'var(--accent-subtle)' : 'transparent', borderRadius: '8px', padding: '6px 12px', fontSize: '0.85rem' }}
        >
          <Ear size={16} style={{ marginRight: '6px' }} />
          Wake Word: {isListening ? "ON" : "OFF"}
        </button>

        <button 
          className={`icon-btn ${shareScreen ? 'active-wake' : ''}`}
          onClick={() => setShareScreen(!shareScreen)}
          title={shareScreen ? "Disable Screen Context" : "Enable Screen Context"}
          style={{ color: shareScreen ? 'var(--accent-primary)' : 'var(--text-secondary)', backgroundColor: shareScreen ? 'var(--accent-subtle)' : 'transparent', borderRadius: '8px', padding: '6px 12px', fontSize: '0.85rem' }}
        >
          <Monitor size={16} style={{ marginRight: '6px' }} />
          Screen Context: {shareScreen ? "ON" : "OFF"}
        </button>

        <button 
          className="icon-btn"
          onClick={() => fileInputRef.current?.click()}
          title="Attach Image"
          style={{ borderRadius: '8px', padding: '6px 12px', fontSize: '0.85rem' }}
        >
          <ImageIcon size={16} style={{ marginRight: '6px' }} />
          Attach
        </button>
        <input 
          type="file" 
          accept="image/*" 
          ref={fileInputRef} 
          style={{ display: 'none' }} 
          onChange={handleFileChange}
        />

        <button 
          className="icon-btn"
          onClick={handleCaptureWebcam}
          title="Capture Webcam Image"
          style={{ borderRadius: '8px', padding: '6px 12px', fontSize: '0.85rem' }}
        >
          <Camera size={16} style={{ marginRight: '6px' }} />
          Webcam
        </button>

        <button 
          className="icon-btn"
          onClick={handleGenerateArt}
          title="Generate Art from text"
          style={{ borderRadius: '8px', padding: '6px 12px', fontSize: '0.85rem' }}
        >
          <Palette size={16} style={{ marginRight: '6px' }} />
          Gen Art
        </button>
      </div>

      {/* Image Preview Container */}
      {attachedImage && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 8px', backgroundColor: 'var(--bg-panel)', borderRadius: '8px', width: 'fit-content' }}>
          <img src={attachedImage} alt="Attached Preview" style={{ width: '40px', height: '40px', objectFit: 'cover', borderRadius: '4px' }} />
          <button className="icon-btn" style={{ padding: '4px' }} onClick={() => setAttachedImage(null)}>X</button>
        </div>
      )}

      {/* Main Input Row */}
      <div className="input-container">
        <button 
          className={`mic-btn ${isCommandMode ? 'recording' : ''}`} 
          onClick={forceCommandMode}
          title={isCommandMode ? "Listening to command..." : "Click to start recording command"}
          disabled={!isListening}
          style={{ opacity: isListening ? 1 : 0.5, cursor: isListening ? 'pointer' : 'not-allowed' }}
        >
          <Mic size={20} />
        </button>
        <textarea
          className="text-input"
          placeholder={isCommandMode ? "Listening..." : "Type a message..."}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <button 
          className="send-btn" 
          onClick={handleSend}
          disabled={!text.trim() && !attachedImage}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
