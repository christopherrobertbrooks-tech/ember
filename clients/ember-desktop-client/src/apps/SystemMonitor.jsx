import React, { useState, useEffect } from 'react';

const SystemMonitor = () => {
  const [sysInfo, setSysInfo] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let intervalId;
    
    const fetchInfo = async () => {
      try {
        const res = await fetch('/api/system_info', {
          headers: { 'X-API-Key': 'ember-secret-key-123' }
        });
        if (!res.ok) throw new Error("Failed to fetch system info");
        const info = await res.json();
        setSysInfo(info);
        setError(null);
      } catch (e) {
        setError("API Error: " + e.message);
      }
    };

    fetchInfo();
    intervalId = setInterval(fetchInfo, 2000);

    return () => clearInterval(intervalId);
  }, []);

  if (error) return <div style={{ padding: '24px', color: 'red' }}>Error: {error}</div>;
  if (!sysInfo) return <div style={{ padding: '24px' }}>Loading System Stats...</div>;

  const memPercent = ((sysInfo.memUsed / sysInfo.memTotal) * 100).toFixed(1);

  return (
    <div style={{ padding: '40px', color: '#e0e0e0', flex: 1, overflowY: 'auto' }}>
      <h1 style={{ fontSize: '2rem', marginBottom: '32px', color: '#e63946' }}>System Monitor</h1>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        <div style={{ backgroundColor: '#1a1a1a', padding: '24px', borderRadius: '12px', border: '1px solid #333' }}>
          <h2 style={{ marginBottom: '16px', color: '#a0a0a0' }}>CPU Load</h2>
          <div style={{ fontSize: '3rem', fontWeight: 'bold' }}>{sysInfo.cpuLoad.toFixed(1)}%</div>
        </div>

        <div style={{ backgroundColor: '#1a1a1a', padding: '24px', borderRadius: '12px', border: '1px solid #333' }}>
          <h2 style={{ marginBottom: '16px', color: '#a0a0a0' }}>Memory Usage</h2>
          <div style={{ fontSize: '3rem', fontWeight: 'bold' }}>{memPercent}%</div>
          <div style={{ color: '#888', marginTop: '8px' }}>
            {(sysInfo.memUsed / 1024 / 1024 / 1024).toFixed(1)} GB / {(sysInfo.memTotal / 1024 / 1024 / 1024).toFixed(1)} GB
          </div>
        </div>
      </div>

      {sysInfo.fans && sysInfo.fans.length > 0 && (
        <>
          <h2 style={{ fontSize: '1.5rem', marginTop: '40px', marginBottom: '24px', color: '#e63946' }}>Fans</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '16px' }}>
            {sysInfo.fans.map((fan, idx) => (
              <div key={idx} style={{ backgroundColor: '#1a1a1a', padding: '20px', borderRadius: '12px', border: '1px solid #333' }}>
                <div style={{ color: '#a0a0a0', marginBottom: '8px', fontSize: '0.9rem' }}>{fan.name}</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>{Math.round(fan.value)} RPM</div>
              </div>
            ))}
          </div>
        </>
      )}

      {sysInfo.temperatures && sysInfo.temperatures.length > 0 && (
        <>
          <h2 style={{ fontSize: '1.5rem', marginTop: '40px', marginBottom: '24px', color: '#e63946' }}>Temperatures</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '16px' }}>
            {sysInfo.temperatures.map((temp, idx) => (
              <div key={idx} style={{ backgroundColor: '#1a1a1a', padding: '20px', borderRadius: '12px', border: '1px solid #333' }}>
                <div style={{ color: '#a0a0a0', marginBottom: '8px', fontSize: '0.9rem' }}>{temp.name}</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>{temp.value.toFixed(1)} °C</div>
              </div>
            ))}
          </div>
        </>
      )}

      <h2 style={{ fontSize: '1.5rem', marginTop: '40px', marginBottom: '24px', color: '#e63946' }}>GPU Statistics (NVIDIA)</h2>
      {sysInfo.gpus && sysInfo.gpus.map((gpu, idx) => (
        <div key={idx} style={{ backgroundColor: '#1a1a1a', padding: '24px', borderRadius: '12px', border: '1px solid #333', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>{gpu.model || gpu.name || 'Unknown GPU'}</h3>
          <p style={{ color: '#a0a0a0' }}>VRAM: {gpu.vram ? `${gpu.vram} MB` : 'Unknown'}</p>
          <p style={{ color: '#a0a0a0' }}>Vendor: {gpu.vendor}</p>
        </div>
      ))}
    </div>
  );
};

export default SystemMonitor;
