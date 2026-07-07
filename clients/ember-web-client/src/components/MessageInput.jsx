import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic, Image as ImageIcon, Palette, Ear } from 'lucide-react';
import { useAudioStream } from '../hooks/useAudioStream';

export default function MessageInput({ onSendMessage, onGenerateArt, onInterrupt, disabled }) {
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
      if (transcribedText.trim() && !disabled) {
        onSendMessage(transcribedText, attachedImage);
        setAttachedImage(null);
      }
    },
    onInterrupt: () => {
      if (onInterrupt) onInterrupt();
      playChime();
    }
  });

  const handleSend = () => {
    if ((text.trim() || attachedImage) && !disabled) {
      onSendMessage(text, attachedImage);
      setText('');
      setAttachedImage(null);
    }
  };

  const handleGenerateArt = () => {
    if (disabled) return;
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

  return (
    <div className="input-area-wrapper">
      
      {/* Top utility row for actions (now above the pill) */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
        <button 
          className={`icon-btn ${isListening ? 'active-wake' : ''}`}
          onClick={toggleListening}
          title={isListening ? "Disable Wake Word" : "Enable Wake Word"}
          style={{ color: isListening ? 'var(--accent-primary)' : 'var(--text-secondary)', backgroundColor: isListening ? 'var(--accent-subtle)' : 'transparent', borderRadius: '8px', padding: '4px 8px', fontSize: '0.8rem' }}
        >
          <Ear size={14} style={{ marginRight: '4px' }} />
          Wake: {isListening ? "ON" : "OFF"}
        </button>
      </div>

      {/* Main Input Row (Pill shape) */}
      <div className="input-container">
        
        {/* Attach Button */}
        <button 
          className="icon-btn"
          onClick={() => fileInputRef.current?.click()}
          title="Attach Image"
          style={{ padding: '8px' }}
        >
          <ImageIcon size={20} />
        </button>
        <input 
          type="file" 
          accept="image/*" 
          ref={fileInputRef} 
          style={{ display: 'none' }} 
          onChange={handleFileChange}
        />

        {/* Generate Art Button */}
        <button 
          className="icon-btn"
          onClick={handleGenerateArt}
          title="Generate Art from text"
          style={{ padding: '8px' }}
        >
          <Palette size={20} />
        </button>

        {/* Text Input Area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '0 8px' }}>
          {/* Image Preview Container (Inside the pill, above text if present) */}
          {attachedImage && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '8px', width: 'fit-content', marginBottom: '4px' }}>
              <img src={attachedImage} alt="Attached Preview" style={{ width: '32px', height: '32px', objectFit: 'cover', borderRadius: '4px' }} />
              <button className="icon-btn" style={{ padding: '2px' }} onClick={() => setAttachedImage(null)}>X</button>
            </div>
          )}
          <textarea
            className="text-input"
            placeholder={isCommandMode ? "Listening..." : "Ask Ember..."}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={disabled}
            style={{ opacity: disabled ? 0.7 : 1 }}
          />
        </div>

        {/* Mic Button */}
        <button 
          className={`mic-btn ${isCommandMode ? 'recording' : ''}`} 
          onClick={forceCommandMode}
          title={isCommandMode ? "Listening to command..." : "Click to start recording command"}
          disabled={!isListening}
          style={{ opacity: isListening ? 1 : 0.5, cursor: isListening ? 'pointer' : 'not-allowed' }}
        >
          <Mic size={20} />
        </button>

        {/* Send Button */}
        <button 
          className="send-btn" 
          onClick={handleSend}
          disabled={disabled || (!text.trim() && !attachedImage)}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
