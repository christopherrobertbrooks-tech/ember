import { Flame, MessageSquare, Terminal, Settings, FolderOpen, Monitor, Globe, Sparkles, FileText } from 'lucide-react';

const Sidebar = ({ activeApp, setActiveApp, isConnected, isThinking, showCompanion, setShowCompanion }) => {
  const flameColor = isThinking ? "#4dabf7" : (isConnected ? "#e63946" : "#a0a0a0");

  return (
    <div className="sidebar">
      <div className="sidebar-logo" title="EmberOS" style={{ cursor: 'pointer' }} onClick={() => setShowCompanion(!showCompanion)}>
        <Flame color={flameColor} size={42} />
      </div>
      <div className="sidebar-nav">
        <button className={`nav-item ${activeApp === 'chat' ? 'active' : ''}`} onClick={() => setActiveApp('chat')} title="General Chat">
          <MessageSquare size={32} />
        </button>
        <button className={`nav-item ${activeApp === 'editor' ? 'active' : ''}`} onClick={() => setActiveApp('editor')} title="Ember Notes">
          <FileText size={32} />
        </button>
        <button className={`nav-item ${activeApp === 'files' ? 'active' : ''}`} onClick={() => setActiveApp('files')} title="File Explorer">
          <FolderOpen size={32} />
        </button>
        <button className={`nav-item ${activeApp === 'terminal' ? 'active' : ''}`} onClick={() => setActiveApp('terminal')} title="Terminal">
          <Terminal size={32} />
        </button>
        <button className={`nav-item ${activeApp === 'browser' ? 'active' : ''}`} onClick={() => setActiveApp('browser')} title="Web Browser">
          <Globe size={32} />
        </button>
        <button className={`nav-item ${activeApp === 'monitor' ? 'active' : ''}`} onClick={() => setActiveApp('monitor')} title="System Monitor">
          <Monitor size={32} />
        </button>
      </div>
      <div className="sidebar-bottom" style={{ display: 'flex', flexDirection: 'column', gap: '16px', alignItems: 'center' }}>
        <button className={`nav-item ${showCompanion ? 'active' : ''}`} onClick={() => setShowCompanion(!showCompanion)} title="Toggle 3D Companion">
          <Sparkles size={32} />
        </button>
        <button className="nav-item" onClick={() => setActiveApp('settings')} title="Settings">
          <Settings size={32} />
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
