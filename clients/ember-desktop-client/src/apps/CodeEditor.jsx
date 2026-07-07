import React, { useState, useEffect, useRef } from 'react';

const CodeEditor = () => {
  const [code, setCode] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const notesPath = 'c:/Project_Ember/ember_notes.txt';

  // Read notes from disk
  const loadFile = () => {
    if (window.electron) {
      window.electron.ipcRenderer.invoke('read-file', notesPath).then((content) => {
        if (content && !content.error) {
          setCode(content);
        }
      });
    }
  };

  // Initial load
  useEffect(() => {
    loadFile();
  }, []);

  // Poll for external changes when user is not actively editing
  useEffect(() => {
    let intervalId;
    if (!isFocused) {
      intervalId = setInterval(loadFile, 2000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isFocused]);

  const handleChange = (e) => {
    const val = e.target.value;
    setCode(val);
    
    // Auto-save immediately to disk
    if (window.electron) {
      window.electron.ipcRenderer.invoke('write-file', notesPath, val);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', backgroundColor: '#09090b' }}>
      <div style={{ padding: '16px', backgroundColor: '#18181b', borderBottom: '1px solid #27272a', color: '#f4f4f5', fontSize: '1.1rem', fontWeight: 'bold' }}>
        Ember Notes
      </div>
      <textarea
        value={code}
        onChange={handleChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        placeholder="Type notes here... Ember can read and write to this scratchpad directly!"
        style={{
          flex: 1,
          width: '100%',
          height: '100%',
          backgroundColor: '#09090b',
          color: '#f4f4f5',
          border: 'none',
          padding: '20px',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          fontSize: '16px',
          lineHeight: '1.6',
          resize: 'none',
          outline: 'none'
        }}
      />
    </div>
  );
};

export default CodeEditor;
