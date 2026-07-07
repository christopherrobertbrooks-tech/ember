import React, { useState, useEffect, useRef } from 'react';
import { Maximize2, Minimize2, ArrowLeft, ArrowRight } from 'lucide-react';
import ChatBox from '../components/ChatBox';
import MessageInput from '../components/MessageInput';

const WebBrowser = ({ initialUrl, messages, sendMessage, isBotTyping, stopAudio }) => {
  const [url, setUrl] = useState(initialUrl || 'https://google.com');
  const [inputUrl, setInputUrl] = useState(initialUrl || 'https://google.com');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const webviewRef = useRef(null);
  const isElectron = Boolean(window.electron);

  useEffect(() => {
    if (initialUrl) {
      setUrl(initialUrl);
      setInputUrl(initialUrl);
    }
  }, [initialUrl]);

  const handleNavigate = (e) => {
    e.preventDefault();
    let finalUrl = inputUrl;
    if (!finalUrl.startsWith('http://') && !finalUrl.startsWith('https://')) {
      finalUrl = 'https://' + finalUrl;
    }
    setUrl(finalUrl);
  };

  const handleBack = () => {
    if (webviewRef.current && webviewRef.current.canGoBack()) {
      webviewRef.current.goBack();
    }
  };

  const handleForward = () => {
    if (webviewRef.current && webviewRef.current.canGoForward()) {
      webviewRef.current.goForward();
    }
  };

  const containerStyle = isFullscreen 
    ? { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999, display: 'flex', flexDirection: 'column', backgroundColor: '#000' }
    : { display: 'flex', flexDirection: 'column', height: '100%', width: '100%', position: 'relative' };

  return (
    <div style={containerStyle}>
      <form onSubmit={handleNavigate} style={{ padding: '16px', backgroundColor: '#1a1a1a', borderBottom: '1px solid #333', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button type="button" onClick={handleBack} style={{ padding: '8px', background: 'transparent', border: 'none', color: '#a0a0a0', cursor: 'pointer' }}>
          <ArrowLeft size={20} />
        </button>
        <button type="button" onClick={handleForward} style={{ padding: '8px', background: 'transparent', border: 'none', color: '#a0a0a0', cursor: 'pointer' }}>
          <ArrowRight size={20} />
        </button>
        <input 
          type="text" 
          value={inputUrl} 
          onChange={(e) => setInputUrl(e.target.value)}
          style={{ flex: 1, padding: '12px', borderRadius: '8px', border: '1px solid #333', backgroundColor: '#0d0d0d', color: '#fff', fontSize: '1.1rem' }}
          placeholder="Enter URL or search..."
        />
        <button type="submit" style={{ padding: '12px 24px', backgroundColor: '#e63946', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '1.1rem' }}>
          Go
        </button>
        <button type="button" onClick={() => setIsChatOpen(!isChatOpen)} style={{ padding: '12px', background: 'transparent', border: '1px solid #333', borderRadius: '8px', color: '#a0a0a0', cursor: 'pointer' }}>
          {isChatOpen ? "Hide Chat" : "Show Chat"}
        </button>
        <button type="button" onClick={() => setIsFullscreen(!isFullscreen)} style={{ padding: '12px', background: 'transparent', border: '1px solid #333', borderRadius: '8px', color: '#a0a0a0', cursor: 'pointer' }}>
          {isFullscreen ? <Minimize2 size={20} /> : <Maximize2 size={20} />}
        </button>
      </form>
      
      <div style={{ flex: 1, backgroundColor: '#fff', position: 'relative' }}>
        {isElectron ? (
          <webview 
            ref={webviewRef}
            src={url} 
            style={{ width: '100%', height: '100%', border: 'none' }}
            allowpopups="true"
          />
        ) : (
          <iframe
            title="Ember Browser"
            src={url}
            style={{ width: '100%', height: '100%', border: 'none' }}
          />
        )}
        
        {/* Floating Chat Overlay */}
        {isChatOpen && (
          <div style={{ 
            position: 'absolute', 
            bottom: '20px', 
            right: '20px', 
            width: '400px', 
            height: '600px', 
            backgroundColor: '#111', 
            border: '1px solid #333', 
            borderRadius: '12px', 
            display: 'flex', 
            flexDirection: 'column', 
            boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
            zIndex: 1000
          }}>
            <div style={{ padding: '10px', borderBottom: '1px solid #333', fontWeight: 'bold', color: '#fff', textAlign: 'center' }}>Ember (Overlay)</div>
            <ChatBox messages={messages} isBotTyping={isBotTyping} />
            <MessageInput onSendMessage={sendMessage} onInterrupt={stopAudio} />
          </div>
        )}
      </div>
    </div>
  );
};

export default WebBrowser;
