import React, { useState } from 'react';
import Editor from '@monaco-editor/react';

export default function CommandCenter({ messages, onSendMessage }) {
  const [activeFile, setActiveFile] = useState('implementation_plan.md');
  const [code, setCode] = useState('# Welcome to Architect Mode\n\nGenerate plans and view code diffs here.');

  const handleEditorChange = (value) => {
    setCode(value);
  };

  return (
    <div className="command-center" style={{ display: 'flex', height: 'calc(100vh - 60px)', color: '#fff', backgroundColor: '#1e1e1e' }}>
      <div className="sidebar" style={{ width: '250px', borderRight: '1px solid #333', padding: '10px' }}>
        <h3 style={{ marginTop: 0, borderBottom: '1px solid #444', paddingBottom: '10px' }}>Sub-Agents</h3>
        <ul style={{ listStyle: 'none', padding: 0, fontSize: '14px', color: '#aaa' }}>
          <li>Agent Orchestrator [Idle]</li>
          <li>Browser Agent [Idle]</li>
        </ul>
        <h3 style={{ borderBottom: '1px solid #444', paddingBottom: '10px', marginTop: '20px' }}>Artifacts</h3>
        <ul style={{ listStyle: 'none', padding: 0, fontSize: '14px' }}>
          <li 
            style={{ cursor: 'pointer', padding: '5px', backgroundColor: '#333', borderRadius: '4px', marginBottom: '5px' }}
            onClick={() => setCode('# Implementation Plan')}
          >
            implementation_plan.md
          </li>
          <li 
            style={{ cursor: 'pointer', padding: '5px' }}
            onClick={() => setCode('- [ ] Task 1')}
          >
            task.md
          </li>
        </ul>
      </div>
      
      <div className="main-content" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div className="editor-header" style={{ padding: '10px', backgroundColor: '#2d2d2d', borderBottom: '1px solid #333' }}>
          <span>{activeFile}</span>
        </div>
        <div style={{ flex: 1 }}>
          <Editor
            height="100%"
            theme="vs-dark"
            defaultLanguage="markdown"
            value={code}
            onChange={handleEditorChange}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              wordWrap: 'on'
            }}
          />
        </div>
        
        {/* Chat Logs Panel */}
        <div style={{ height: '150px', overflowY: 'auto', backgroundColor: '#1e1e1e', padding: '10px', borderTop: '1px solid #333', fontSize: '14px', fontFamily: 'monospace' }}>
          {(messages || []).filter(m => m.role !== 'system').slice(-10).map((msg, idx) => (
            <div key={idx} style={{ marginBottom: '5px', color: msg.role === 'user' ? '#4dabf7' : '#20C20E' }}>
              <strong>{msg.role === 'user' ? 'You' : 'Architect'}:</strong> {msg.content}
            </div>
          ))}
        </div>

        <div className="terminal-input" style={{ padding: '10px', backgroundColor: '#252526', borderTop: '1px solid #333' }}>
          <input 
            type="text" 
            placeholder="Assign a high-level goal to the Architect..." 
            style={{ width: '100%', padding: '10px', backgroundColor: '#3c3c3c', border: '1px solid #555', color: '#fff', borderRadius: '4px' }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.target.value.trim()) {
                if (onSendMessage) onSendMessage(e.target.value.trim());
                e.target.value = '';
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}
