import React, { useEffect, useRef } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

const TerminalApp = () => {
  const terminalRef = useRef(null);
  const xtermRef = useRef(null);
  const fitAddonRef = useRef(null);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm
    const term = new XTerm({
      cursorBlink: true,
      fontSize: 16, // Larger font for 10-foot UI
      fontFamily: 'Consolas, "Courier New", monospace',
      theme: {
        background: '#1a1a1a',
        foreground: '#e0e0e0',
        cursor: '#e63946',
      }
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    
    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    // Handle Window Resize
    const handleResize = () => {
      fitAddon.fit();
      if (window.electron) {
        window.electron.ipcRenderer.send('terminal-resize', {
          cols: term.cols,
          rows: term.rows
        });
      }
    };
    window.addEventListener('resize', handleResize);
    
    // Initial size report to backend
    if (window.electron) {
      window.electron.ipcRenderer.send('terminal-resize', {
        cols: term.cols,
        rows: term.rows
      });
    }

    // Input from Xterm to Backend PTY
    term.onData((data) => {
      if (window.electron) {
        window.electron.ipcRenderer.send('terminal-intoTerm', data);
      }
    });

    // Output from Backend PTY to Xterm
    const handleIncData = (data) => {
      term.write(data);
    };

    if (window.electron) {
      window.electron.ipcRenderer.on('terminal-incData', handleIncData);
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      if (window.electron) {
        window.electron.ipcRenderer.removeAllListeners('terminal-incData');
      }
      term.dispose();
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
      <div style={{ padding: '16px', backgroundColor: '#1a1a1a', borderBottom: '1px solid #333', color: '#a0a0a0', fontSize: '1.1rem' }}>
        Terminal - powershell
      </div>
      <div style={{ flex: 1, backgroundColor: '#1a1a1a', padding: '16px', overflow: 'hidden' }} ref={terminalRef}></div>
    </div>
  );
};

export default TerminalApp;
