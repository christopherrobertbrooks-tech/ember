import React, { useState, useEffect } from 'react';
import { 
  Flame, Mic, Search, Clock, Bell, Settings, 
  Grid, X, TerminalSquare, FolderOpen, Activity, 
  Code, Globe, Calendar, Music, AlarmClock, BatteryMedium, Wifi, Bluetooth, Download, Keyboard, MessageSquare, Menu, Monitor, Gamepad2
} from 'lucide-react';
import { useEmberSocket } from './hooks/useEmberSocket';
import { useAudioStream } from './hooks/useAudioStream';
import ChatBox from './components/ChatBox';
import MessageInput from './components/MessageInput';

// Import ported desktop apps
import FileExplorer from './apps/FileExplorer';
import SystemMonitor from './apps/SystemMonitor';
import TerminalApp from './apps/Terminal';
import WebBrowser from './apps/WebBrowser';
import ScreenViewer from './apps/ScreenViewer';
import QuickRemote from './apps/QuickRemote';

import './index.css';

function App() {
  const { messages, sendMessage, isConnected, isBotTyping, isThinking } = useEmberSocket();
  const [activeApp, setActiveApp] = useState(null); // null means Home/Chat Arena
  const [browserUrl, setBrowserUrl] = useState(null);
  const [filesPath, setFilesPath] = useState(null);
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false); // Collapsible sidebar state

  // Audio stream handling
  const { isListening, isCommandMode, startStream, stopStream } = useAudioStream({
    onWakeWord: () => console.log("Wake word detected"),
    onCommandTranscribed: (text) => sendMessage(text),
    onInterrupt: () => console.log("Interrupt detected")
  });

  // Handle PWA prompt
  useEffect(() => {
    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, []);

  const handleInstallClick = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setDeferredPrompt(null);
    }
  };

  const closeApp = () => setActiveApp(null);
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  useEffect(() => {
    const handleUiAction = (e) => {
      const data = e.detail;
      if (data.action === 'open_browser') {
        setBrowserUrl(data.url || null);
        setActiveApp('browser');
      } else if (data.action === 'open_chat') {
        setActiveApp(null);
      } else if (data.action === 'open_terminal') {
        setActiveApp('terminal');
      } else if (data.action === 'open_files') {
        setFilesPath(data.path || data.folder || null);
        setActiveApp('files');
      } else if (data.action === 'open_monitor') {
        setActiveApp('monitor');
      } else if (data.action === 'open_screen') {
        setActiveApp('screen');
      } else if (data.action === 'open_remote') {
        setActiveApp('remote');
      }
    };
    window.addEventListener('ember-ui-action', handleUiAction);
    return () => window.removeEventListener('ember-ui-action', handleUiAction);
  }, []);

  return (
    <div className="mobile-app-container">
      
      {/* Sidebar (Left) */}
      <div className={`sidebar ${isSidebarOpen ? 'open' : 'collapsed'}`}>
        <div className="sidebar-top">
          <div className={`nav-item ${activeApp === null ? 'active' : ''}`} onClick={() => setActiveApp(null)} title="Chat">
            <MessageSquare size={24} />
          </div>
          <div className={`nav-item ${activeApp === 'terminal' ? 'active' : ''}`} onClick={() => setActiveApp('terminal')} title="Terminal">
            <TerminalSquare size={24} />
          </div>
          <div className={`nav-item ${activeApp === 'files' ? 'active' : ''}`} onClick={() => setActiveApp('files')} title="Files">
            <FolderOpen size={24} />
          </div>
          <div className={`nav-item ${activeApp === 'browser' ? 'active' : ''}`} onClick={() => { setBrowserUrl(null); setActiveApp('browser'); }} title="Browser">
            <Globe size={24} />
          </div>
          <div className={`nav-item ${activeApp === 'monitor' ? 'active' : ''}`} onClick={() => setActiveApp('monitor')} title="Monitor">
            <Activity size={24} />
          </div>
          <div className={`nav-item ${activeApp === 'screen' ? 'active' : ''}`} onClick={() => setActiveApp('screen')} title="Screen Viewer">
            <Monitor size={24} />
          </div>
          <div className={`nav-item ${activeApp === 'remote' ? 'active' : ''}`} onClick={() => setActiveApp('remote')} title="Quick Remote">
            <Gamepad2 size={24} />
          </div>
        </div>
        <div className="sidebar-bottom">
          <div className="nav-item" title="Notifications">
            <Bell size={24} />
          </div>
          <div className="nav-item" title="Settings">
            <Settings size={24} />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="chat-arena">
        
        {/* Status Bar Overlay */}
        <div className="status-bar" style={{ justifyContent: 'space-between' }}>
          <Menu size={24} color="var(--text-main)" onClick={() => setIsSidebarOpen(!isSidebarOpen)} style={{ cursor: 'pointer' }} />
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <span>{time}</span>
            {deferredPrompt && (
               <Download size={18} color="var(--accent-red)" onClick={handleInstallClick} style={{ cursor: 'pointer' }} title="Install App" />
            )}
            <Bluetooth size={16} />
            <Wifi size={16} />
            <BatteryMedium size={16} />
          </div>
        </div>

        {/* Chat / Home View */}
        {activeApp === null && (
          <>
            {messages.length === 0 ? (
              <div className="home-empty-state" style={{ justifyContent: 'flex-start', paddingTop: '40px' }}>
                <div className="sub-greeting">What's on your mind?</div>
                <div className="action-chips-container">
                  <div className="action-chip" onClick={() => sendMessage("Check my schedule")}><Calendar size={16} color="var(--accent-red)" /> Check schedule</div>
                  <div className="action-chip" onClick={() => sendMessage("Play some music")}><Music size={16} color="var(--accent-red)" /> Play music</div>
                  <div className="action-chip" onClick={() => sendMessage("Set an alarm")}><AlarmClock size={16} color="var(--accent-red)" /> Set alarm</div>
                </div>
              </div>
            ) : (
              <ChatBox messages={messages} isTyping={isBotTyping} />
            )}
            
            {/* Unified Input Box (always visible at bottom of Chat Arena) */}
            <div className="input-area-wrapper">
              <MessageInput onSendMessage={(text, img) => sendMessage(text, img)} disabled={isThinking} />
            </div>
          </>
        )}

        {/* Full Screen App Overlays (Terminal, Editor, etc.) */}
        {activeApp && (
          <div className="full-app-overlay">
            <div className="drawer-header">
              <X size={24} color="var(--text-muted)" cursor="pointer" onClick={closeApp} style={{marginRight: '16px'}} />
              <div className="drawer-title" style={{textTransform: 'capitalize'}}>{activeApp}</div>
            </div>
            <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
              {activeApp === 'terminal' && <TerminalApp />}
              {activeApp === 'files' && <FileExplorer initialPath={filesPath} onOpenFile={(f) => { console.log("File opened", f); }} />}
              {activeApp === 'browser' && (
                <WebBrowser
                  initialUrl={browserUrl}
                  messages={messages}
                  sendMessage={sendMessage}
                  isBotTyping={isBotTyping}
                />
              )}
              {activeApp === 'monitor' && <SystemMonitor />}
              {activeApp === 'screen' && <ScreenViewer />}
              {activeApp === 'remote' && <QuickRemote />}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;
