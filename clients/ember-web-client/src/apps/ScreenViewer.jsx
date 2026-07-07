import React, { useState, useEffect } from 'react';

const ScreenViewer = () => {
  const [imgSrc, setImgSrc] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let intervalId;
    
    const fetchScreenshot = async () => {
      try {
        const res = await fetch('/api/screenshot', {
          headers: { 'X-API-Key': 'ember-secret-key-123' }
        });
        if (!res.ok) throw new Error("Failed to fetch screenshot");
        const data = await res.json();
        setImgSrc(`data:image/png;base64,${data.image_base64}`);
        setError(null);
      } catch (e) {
        setError("API Error: " + e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchScreenshot();
    intervalId = setInterval(fetchScreenshot, 3000); // Poll every 3s

    return () => clearInterval(intervalId);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', backgroundColor: '#0d0d0d' }}>
      <div style={{ padding: '16px', backgroundColor: '#1a1a1a', borderBottom: '1px solid #333', color: '#e63946', fontSize: '1.2rem', fontWeight: 'bold' }}>
        Live Screen Viewer
      </div>
      <div style={{ flex: 1, padding: '16px', display: 'flex', justifyContent: 'center', alignItems: 'center', overflow: 'hidden' }}>
        {error ? (
          <div style={{ color: '#e63946' }}>Error: {error}</div>
        ) : loading ? (
          <div style={{ color: '#a0a0a0' }}>Capturing screen...</div>
        ) : (
          <img 
            src={imgSrc} 
            alt="Host Desktop" 
            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: '8px', border: '1px solid #333' }}
          />
        )}
      </div>
    </div>
  );
};

export default ScreenViewer;
