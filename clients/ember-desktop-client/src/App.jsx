import React, { useState, useEffect } from 'react';
import { useEmberSocket } from './hooks/useEmberSocket';
import Sidebar from './components/Sidebar';
import ChatBox from './components/ChatBox';
import MessageInput from './components/MessageInput';
import SettingsPanel from './components/SettingsPanel';
import CodeEditor from './apps/CodeEditor';
import WebBrowser from './apps/WebBrowser';
import SystemMonitor from './apps/SystemMonitor';
import TerminalApp from './apps/Terminal';
import FileExplorer from './apps/FileExplorer';
import VrmRenderer from './components/VrmRenderer';
import './index.css';

function App() {
  const { messages, sendMessage, isConnected, isBotTyping, isThinking, clearMessages, addMessageToChat, stopAudio, gesture } = useEmberSocket();
  const [activeApp, setActiveApp] = useState('chat'); // 'chat', 'editor', 'files', 'terminal', 'monitor', 'settings'
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [editorFile, setEditorFile] = useState(null);
  const [filesPath, setFilesPath] = useState(null);
  const [browserUrl, setBrowserUrl] = useState(null);
  const [showCompanion, setShowCompanion] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [affinity, setAffinity] = useState(50);

  useEffect(() => {
    if (activeApp === 'settings') {
      setIsSettingsOpen(true);
      setActiveApp('chat');
    }
  }, [activeApp]);

  useEffect(() => {
    const fetchAffinity = async () => {
      try {
        const res = await fetch('/api/relationship', {
          headers: { 'X-API-Key': 'ember-secret-key-123' }
        });
        if (!res.ok) return; // Backend not ready or erroring — skip silently
        const data = await res.json();
        if (data.affinity !== undefined) {
          setAffinity(data.affinity);
        }
      } catch (e) {
        // Silently ignore — backend is offline or not yet ready
      }
    };
    fetchAffinity();
    
    // Poll relationship state periodically to catch sentiment shifts
    const interval = setInterval(fetchAffinity, 8000);
    return () => clearInterval(interval);
  }, []); // Only set up once on mount — the interval handles polling

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length === 0) return;

    let idCounter = Date.now() * 1000;
    const nextId = () => idCounter++;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      addMessageToChat({ 
        role: 'system', 
        content: `Ingesting "${file.name}" into Ember's RAG database...`, 
        id: nextId() 
      });

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch('/api/upload_document', {
          method: 'POST',
          headers: { 'X-API-Key': 'ember-secret-key-123' },
          body: formData
        });
        const data = await res.json();
        if (data.status === 'success') {
          addMessageToChat({ 
            role: 'system', 
            content: `"${file.name}" has been successfully memorized.`, 
            id: nextId() 
          });
        } else {
          addMessageToChat({ 
            role: 'system', 
            content: `Failed to memorize "${file.name}": ${data.detail}`, 
            id: nextId() 
          });
        }
      } catch (err) {
        addMessageToChat({ 
          role: 'system', 
          content: `Error uploading "${file.name}": ${err.message}`, 
          id: nextId() 
        });
      }
    }
  };

  useEffect(() => {
    const handleUiAction = (e) => {
      const data = e.detail;
      if (data.action === 'open_browser') {
        setBrowserUrl(data.url);
        setActiveApp('browser');
      } else if (data.action === 'open_editor') {
        setEditorFile(data.file || data.filepath || null);
        setActiveApp('editor');
      } else if (data.action === 'open_chat') {
        setActiveApp('chat');
      } else if (data.action === 'open_terminal') {
        setActiveApp('terminal');
      } else if (data.action === 'open_files') {
        setFilesPath(data.path || data.folder || null);
        setActiveApp('files');
      } else if (data.action === 'open_monitor') {
        setActiveApp('monitor');
      }
      if (window.electron) {
        window.electron.ipcRenderer.send('show-app');
      }
    };
    window.addEventListener('ember-ui-action', handleUiAction);
    
    // Listen for memory telemetry from main process and dispatch to socket layer
    if (window.electron) {
      window.electron.ipcRenderer.on('memory-telemetry', (data) => {
         window.dispatchEvent(new CustomEvent('ember-send-telemetry', { detail: data }));
      });
    }

    return () => {
      window.removeEventListener('ember-ui-action', handleUiAction);
      if (window.electron) {
        window.electron.ipcRenderer.removeAllListeners('memory-telemetry');
      }
    };
  }, []);

  const isCompanionMode = window.location.search.includes('mode=companion');

  const latestBotMessage = messages.filter(m => m.role === 'bot').pop()?.content || '';

  // Forward state updates to companion window
  useEffect(() => {
    if (window.electron && !isCompanionMode) {
      window.electron.ipcRenderer.send('forward-to-companion', {
        channel: 'vrm-state-update',
        data: { isThinking, affinity, isConnected, latestMessage: latestBotMessage }
      });
    }
  }, [isThinking, affinity, isConnected, latestBotMessage, isCompanionMode]);

  // Forward visibility updates to companion window manager
  useEffect(() => {
    if (window.electron && !isCompanionMode) {
      window.electron.ipcRenderer.send('toggle-companion-window', showCompanion);
    }
  }, [showCompanion, isCompanionMode]);

  // Handle IPC calls from companion window
  useEffect(() => {
    if (window.electron && !isCompanionMode) {
      const handleCompanionSendMessage = (text) => {
        sendMessage(text);
      };
      const handleCompanionToggleListening = () => {
        window.dispatchEvent(new CustomEvent('toggle-audio-listening'));
      };

      window.electron.ipcRenderer.on('companion-send-message', handleCompanionSendMessage);
      window.electron.ipcRenderer.on('companion-toggle-listening', handleCompanionToggleListening);

      return () => {
        window.electron.ipcRenderer.removeAllListeners('companion-send-message');
        window.electron.ipcRenderer.removeAllListeners('companion-toggle-listening');
      };
    }
  }, [isCompanionMode, sendMessage]);

  if (isCompanionMode) {
    return (
      <div 
        style={{ 
          width: '100vw', 
          height: '100vh', 
          background: 'transparent', 
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        <VrmRenderer isCompanionMode={true} gesture={gesture} />
      </div>
    );
  }

  const handleSettingsClose = () => {
    setIsSettingsOpen(false);
    setActiveApp('chat');
  };

  const handleGenerateArt = async (prompt) => {
    addMessageToChat({ role: 'system', content: `Generating art for: "${prompt}"...`, id: Date.now() });
    try {
      const res = await fetch('/api/generate_image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': 'ember-secret-key-123' },
        body: JSON.stringify({ prompt })
      });
      const data = await res.json();
      if (data.image_base64) {
        addMessageToChat({ 
          role: 'bot', 
          content: 'Here is your generated image:', 
          image: `data:image/png;base64,${data.image_base64}`,
          id: Date.now() 
        });
      } else {
        addMessageToChat({ role: 'system', content: `Art generation failed.`, id: Date.now() });
      }
    } catch (err) {
      addMessageToChat({ role: 'system', content: `Error generating art: ${err.message}`, id: Date.now() });
    }
  };

  return (
    <div className="app-container" onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
      <Sidebar 
        activeApp={activeApp} 
        setActiveApp={setActiveApp} 
        isConnected={isConnected} 
        isThinking={isThinking} 
        showCompanion={showCompanion}
        setShowCompanion={setShowCompanion}
      />
      {!showCompanion && (
        <div className="vrm-container-wrapper">
          <VrmRenderer 
            isThinking={isThinking} 
            affinity={affinity} 
            isCompanionMode={false} 
            gesture={gesture} 
          />
        </div>
      )}
      
      <div className="workspace-container">
        {/* We can dynamically render the active app here */}
        <div style={{ display: activeApp === 'chat' ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
          <header className="header">
            <div className="header-title">EmberOS <span>Chat</span></div>
          </header>
          <ChatBox messages={messages} isBotTyping={isBotTyping} />
          <MessageInput 
            onSendMessage={sendMessage} 
            onGenerateArt={handleGenerateArt} 
            onInterrupt={stopAudio}
          />
        </div>

        {/* Render Apps */}
        {activeApp === 'editor' && <CodeEditor filePath={editorFile} />}
        {activeApp === 'browser' && (
          <WebBrowser 
            initialUrl={browserUrl} 
            messages={messages} 
            sendMessage={sendMessage} 
            isBotTyping={isBotTyping} 
            stopAudio={stopAudio}
          />
        )}
        {activeApp === 'monitor' && <SystemMonitor />}
        {activeApp === 'terminal' && <TerminalApp />}
        
        {activeApp === 'files' && (
           <FileExplorer initialPath={filesPath} onOpenFile={(path) => { setEditorFile(path); setActiveApp('editor'); }} />
        )}

        <SettingsPanel 
          isOpen={isSettingsOpen} 
          onClose={handleSettingsClose} 
          onMemoryWiped={clearMessages}
        />
      </div>

      {/* Drag & Drop Upload Overlay */}
      {isDragging && (
        <div style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(230, 57, 70, 0.2)',
          backdropFilter: 'blur(8px)',
          border: '4px dashed var(--accent-primary)',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: '1.5rem',
          fontWeight: 'bold',
          pointerEvents: 'none'
        }}>
          Feed document to Ember's Hive Mind...
        </div>
      )}
    </div>
  );
}

export default App;
