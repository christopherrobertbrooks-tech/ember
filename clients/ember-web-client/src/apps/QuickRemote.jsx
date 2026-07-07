import React from 'react';
import { Play, SkipBack, SkipForward, Volume2, Volume1, VolumeX, Lock, Moon } from 'lucide-react';

const QuickRemote = () => {
  const handleAction = async (action) => {
    try {
      await fetch('/api/remote_action', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-API-Key': 'ember-secret-key-123'
        },
        body: JSON.stringify({ action })
      });
    } catch (e) {
      console.error("Remote action failed", e);
    }
  };

  const btnStyle = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    backgroundColor: '#1a1a1a',
    border: '1px solid #333',
    borderRadius: '16px',
    color: '#fff',
    cursor: 'pointer',
    gap: '12px',
    transition: 'background 0.2s',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', backgroundColor: '#0d0d0d', padding: '24px', overflowY: 'auto' }}>
      <h1 style={{ color: '#e63946', fontSize: '2rem', marginBottom: '32px' }}>Quick Remote</h1>
      
      <h2 style={{ color: '#a0a0a0', marginBottom: '16px' }}>Media Controls</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '40px' }}>
        <button style={btnStyle} onClick={() => handleAction('prev_track')}><SkipBack size={32} /> Prev</button>
        <button style={btnStyle} onClick={() => handleAction('play_pause')}><Play size={32} /> Play/Pause</button>
        <button style={btnStyle} onClick={() => handleAction('next_track')}><SkipForward size={32} /> Next</button>
        <button style={btnStyle} onClick={() => handleAction('vol_down')}><Volume1 size={32} /> Vol -</button>
        <button style={btnStyle} onClick={() => handleAction('mute')}><VolumeX size={32} /> Mute</button>
        <button style={btnStyle} onClick={() => handleAction('vol_up')}><Volume2 size={32} /> Vol +</button>
      </div>

      <h2 style={{ color: '#a0a0a0', marginBottom: '16px' }}>System Power</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
        <button style={{ ...btnStyle, borderColor: '#e63946' }} onClick={() => handleAction('lock')}><Lock size={32} color="#e63946" /> Lock PC</button>
        <button style={{ ...btnStyle, borderColor: '#4a90e2' }} onClick={() => handleAction('sleep')}><Moon size={32} color="#4a90e2" /> Sleep PC</button>
      </div>
    </div>
  );
};

export default QuickRemote;
