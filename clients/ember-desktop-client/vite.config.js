import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Dynamically read the Host IP from ember_config.json so we don't have to hardcode or regex replace it!
let targetUrl = 'http://127.0.0.1:8000';
let wsTargetUrl = 'ws://127.0.0.1:8000';

try {
  const configPath = path.resolve(__dirname, '../../ember_config.json');
  if (fs.existsSync(configPath)) {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    // Look for chroma_server_url to extract the Host IP if it's set to the Tailscale IP.
    // Otherwise, we default to the Host PC's known Tailscale IP: 100.100.150.74
    let hostIp = '100.100.150.74';
    if (config.chroma_server_url && !config.chroma_server_url.includes('127.0.0.1')) {
      hostIp = config.chroma_server_url.split('://')[1].split(':')[0];
    }
    
    targetUrl = `http://${hostIp}:8000`;
    wsTargetUrl = `ws://${hostIp}:8000`;
  }
} catch (e) {
  console.error("Failed to dynamically read ember_config.json:", e.message);
  console.error("Path attempted:", path.resolve(__dirname, '../ember_config.json'));
}

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    host: true,
    port: 5199,
    strictPort: true,
    proxy: {
      '/api': {
        target: targetUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/ws': {
        target: wsTargetUrl,
        ws: true
      }
    }
  }
});
