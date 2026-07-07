import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

export default function SettingsPanel({ isOpen, onClose, onMemoryWiped }) {
  const [settings, setSettings] = useState({ ollama_model: '', voice: '', system_prompt: '', game_mode: false, complete_computer_control: false });
  const [models, setModels] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
      fetchModels();
    }
  }, [isOpen]);

  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings', {
        headers: { 'X-API-Key': 'ember-secret-key-123' }
      });
      const data = await res.json();
      setSettings({
        ollama_model: data.ollama_model || '',
        voice: data.voice || '',
        system_prompt: data.system_prompt || '',
        game_mode: data.game_mode || false,
        complete_computer_control: data.complete_computer_control || false
      });
    } catch (err) {
      console.error(err);
    }
  };

  const fetchModels = async () => {
    try {
      const res = await fetch('/api/models', {
        headers: { 'X-API-Key': 'ember-secret-key-123' }
      });
      const data = await res.json();
      setModels(data.models || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSave = async () => {
    setIsLoading(true);
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': 'ember-secret-key-123'
        },
        body: JSON.stringify(settings)
      });
      onClose();
    } catch (err) {
      console.error(err);
    }
    setIsLoading(false);
  };

  const handleWipeMemory = async () => {
    if (!window.confirm("Are you sure you want to wipe Ember's memory?")) return;
    try {
      await fetch('/api/wipe_memory', {
        method: 'POST',
        headers: { 'X-API-Key': 'ember-secret-key-123' }
      });
      onMemoryWiped();
      onClose();
    } catch (err) {
      console.error(err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="icon-btn" onClick={onClose}><X size={20} /></button>
        </div>
        
        {/* Model selection has been removed per user request */}

        <div className="setting-group">
          <label>Voice (TTS Model)</label>
          <input 
            className="setting-input" 
            type="text" 
            value={settings.voice || ''}
            onChange={e => setSettings({...settings, voice: e.target.value})}
          />
        </div>

        <div className="setting-group">
          <label>System Prompt</label>
          <textarea 
            className="setting-input" 
            rows={4}
            value={settings.system_prompt || ''}
            onChange={e => setSettings({...settings, system_prompt: e.target.value})}
          />
        </div>

        <div className="setting-group" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px' }}>
          <input 
            type="checkbox" 
            id="gameMode"
            checked={settings.game_mode || false}
            onChange={e => setSettings({...settings, game_mode: e.target.checked})}
            style={{ width: '18px', height: '18px', cursor: 'pointer' }}
          />
          <label htmlFor="gameMode" style={{ marginBottom: 0, cursor: 'pointer' }}>Enable Game Mode (Continuous Vision Loop)</label>
        </div>

        <div className="setting-group" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px' }}>
          <input
            type="checkbox"
            id="completeComputerControl"
            checked={settings.complete_computer_control || false}
            onChange={e => setSettings({...settings, complete_computer_control: e.target.checked})}
            style={{ width: '18px', height: '18px', cursor: 'pointer' }}
          />
          <label htmlFor="completeComputerControl" style={{ marginBottom: 0, cursor: 'pointer' }}>Enable Complete Computer Control on Client</label>
        </div>

        <button 
          className="send-btn" 
          style={{ width: '100%', borderRadius: '8px', marginTop: '16px' }} 
          onClick={handleSave}
          disabled={isLoading}
        >
          {isLoading ? 'Saving...' : 'Save Settings'}
        </button>

        <button className="btn-danger" onClick={handleWipeMemory}>
          Wipe Memory
        </button>
      </div>
    </div>
  );
}
