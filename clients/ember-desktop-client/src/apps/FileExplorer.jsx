import React, { useState, useEffect } from 'react';
import { Folder, File, ArrowLeft } from 'lucide-react';

const FileExplorer = ({ onOpenFile, initialPath }) => {
  const [currentPath, setCurrentPath] = useState(initialPath || 'C:\\');
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadDirectory(currentPath);
  }, [currentPath]);

  useEffect(() => {
    if (initialPath) {
      setCurrentPath(initialPath);
    }
  }, [initialPath]);

  const loadDirectory = async (path) => {
    if (!window.electron) return;
    try {
      const result = await window.electron.ipcRenderer.invoke('read-dir', path);
      if (result.error) {
        setError(result.error);
      } else {
        setError(null);
        // Sort directories first, then files
        const sorted = result.sort((a, b) => {
          if (a.isDirectory && !b.isDirectory) return -1;
          if (!a.isDirectory && b.isDirectory) return 1;
          return a.name.localeCompare(b.name);
        });
        setItems(sorted);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const handleNavigateUp = () => {
    if (currentPath.length <= 3) return; // e.g., 'C:\'
    const parentPath = currentPath.substring(0, currentPath.lastIndexOf('\\')) || currentPath.substring(0, 3);
    setCurrentPath(parentPath);
  };

  const handleItemClick = (item) => {
    const fullPath = currentPath.endsWith('\\') ? `${currentPath}${item.name}` : `${currentPath}\\${item.name}`;
    if (item.isDirectory) {
      setCurrentPath(fullPath);
    } else {
      onOpenFile(fullPath);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', backgroundColor: '#0d0d0d' }}>
      <div style={{ padding: '16px', backgroundColor: '#1a1a1a', borderBottom: '1px solid #333', display: 'flex', alignItems: 'center', gap: '16px' }}>
        <button 
          onClick={handleNavigateUp} 
          disabled={currentPath.length <= 3}
          style={{ background: 'transparent', border: '1px solid #333', color: '#fff', padding: '8px', borderRadius: '4px', cursor: currentPath.length <= 3 ? 'not-allowed' : 'pointer', opacity: currentPath.length <= 3 ? 0.5 : 1 }}
        >
          <ArrowLeft size={20} />
        </button>
        <div style={{ color: '#fff', fontSize: '1.2rem', fontFamily: 'monospace', flex: 1 }}>{currentPath}</div>
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {error ? (
          <div style={{ color: '#e63946', fontSize: '1.2rem' }}>Error: {error}</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '16px' }}>
            {items.map((item, index) => (
              <div 
                key={index} 
                onClick={() => handleItemClick(item)}
                style={{ 
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', 
                  padding: '16px', backgroundColor: '#1a1a1a', borderRadius: '8px', border: '1px solid #333',
                  cursor: 'pointer', textAlign: 'center'
                }}
              >
                {item.isDirectory ? <Folder size={48} color="#fcd53f" /> : <File size={48} color="#a0a0a0" />}
                <span style={{ color: '#fff', fontSize: '1rem', wordBreak: 'break-all' }}>{item.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default FileExplorer;
