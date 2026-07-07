import { app, BrowserWindow, ipcMain, globalShortcut, Tray, Menu, screen, nativeImage } from 'electron';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs/promises';
import si from 'systeminformation';
import os from 'os';
import pty from 'node-pty';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const isDev = process.env.NODE_ENV !== 'production' && !app.isPackaged;

app.commandLine.appendSwitch('disable-renderer-backgrounding');
app.commandLine.appendSwitch('disable-background-timer-throttling');
app.commandLine.appendSwitch('disable-backgrounding-occluded-windows', 'true');
app.commandLine.appendSwitch('disable-features', 'CalculateNativeWinOcclusion');
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

let mainWindow;
let companionWindow = null;
let tray = null;
let isAlwaysOnTop = false;
let isAppHidden = false;

function hideMainWindow() {
  if (mainWindow) {
    isAppHidden = true;
    mainWindow.setOpacity(0);
    mainWindow.setSkipTaskbar(true);
    mainWindow.setIgnoreMouseEvents(true);
    mainWindow.webContents.send('window-visibility-change', 'hidden');
    if (companionWindow && !companionWindow.isDestroyed()) {
      companionWindow.webContents.send('window-visibility-change', 'hidden');
    }
  }
}

function showMainWindow() {
  if (mainWindow) {
    isAppHidden = false;
    mainWindow.setOpacity(1);
    mainWindow.setSkipTaskbar(false);
    mainWindow.setIgnoreMouseEvents(false);
    mainWindow.show();
    mainWindow.focus();
    mainWindow.webContents.send('window-visibility-change', 'visible');
    if (companionWindow && !companionWindow.isDestroyed()) {
      companionWindow.webContents.send('window-visibility-change', 'visible');
    }
  }
}

function createCompanionWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  
  companionWindow = new BrowserWindow({
    width: 280,
    height: 450,
    x: width - 300,
    y: height - 490,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    movable: true,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      backgroundThrottling: false
    }
  });

  if (isDev) {
    companionWindow.loadURL('http://localhost:5199?mode=companion');
  } else {
    companionWindow.loadURL(`file://${path.join(__dirname, 'dist', 'index.html')}?mode=companion`);
  }

  companionWindow.once('ready-to-show', () => {
    if (companionWindow) {
      companionWindow.show();
      companionWindow.setIgnoreMouseEvents(true, { forward: true });
      companionWindow.setMinimumSize(240, 300);
    }
  });

  companionWindow.on('closed', () => {
    companionWindow = null;
  });
}

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  
  mainWindow = new BrowserWindow({
    width,
    height,
    frame: false,
    transparent: false,
    backgroundColor: '#0a0a0a',
    alwaysOnTop: isAlwaysOnTop,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true, // Securely exposes window.electron
      webviewTag: true, // Enable <webview> for native browser
      backgroundThrottling: false // Keep audio stream alive when minimized
    }
  });

  if (isDev) {
    // Load Vite dev server
    mainWindow.loadURL('http://localhost:5199');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    // Load built React app
    mainWindow.loadURL(`file://${path.join(__dirname, 'dist', 'index.html')}`);
  }

  // Maximize the window so it fills the screen without covering the taskbar
  mainWindow.maximize();

  // Handle close
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      hideMainWindow();
    }
    return false;
  });
}

function createTray() {
  // We'll use a native image placeholder or an existing icon
  const iconPath = isDev ? path.join(__dirname, 'public', 'flame.png') : path.join(__dirname, 'dist', 'flame.png');
  try {
    tray = new Tray(iconPath);
  } catch(e) {
    // If no icon is found, use a blank or default native image
    tray = new Tray(nativeImage.createFromPath(iconPath));
  }
  
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show App', click: () => { mainWindow.show(); } },
    { label: 'Quit', click: () => { app.isQuitting = true; app.quit(); } }
  ]);
  
  tray.setToolTip('Ember Companion');
  tray.setContextMenu(contextMenu);
  
  tray.on('click', () => {
    !isAppHidden ? hideMainWindow() : showMainWindow();
  });
}

app.whenReady().then(() => {
  createWindow();
  createCompanionWindow();
  createTray();

  // Register Global Shortcut
  globalShortcut.register('CommandOrControl+Space', () => {
    if (!isAppHidden) {
      hideMainWindow();
    } else {
      showMainWindow();
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
      createCompanionWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// IPC handlers for UI to communicate with Electron
ipcMain.on('set-always-on-top', (event, status) => {
  isAlwaysOnTop = status;
  if (status) {
    mainWindow.setAlwaysOnTop(true, 'screen-saver', 1);
  } else {
    mainWindow.setAlwaysOnTop(false);
  }
  event.reply('always-on-top-status', isAlwaysOnTop);
});

ipcMain.on('close-app', () => {
  app.isQuitting = true;
  app.quit();
});

ipcMain.on('minimize-app', () => {
  hideMainWindow(); // Hide to tray instead of minimizing
});

ipcMain.on('hide-app', () => {
  hideMainWindow();
});

ipcMain.on('show-app', () => {
  showMainWindow();
});

ipcMain.on('set-companion-click-through', (event, ignore) => {
  if (companionWindow && !companionWindow.isDestroyed()) {
    companionWindow.setIgnoreMouseEvents(ignore, { forward: true });
  }
});

ipcMain.on('move-companion-window', (event, { deltaX, deltaY }) => {
  if (companionWindow && !companionWindow.isDestroyed()) {
    const [x, y] = companionWindow.getPosition();
    const [w, h] = companionWindow.getSize();
    const targetX = x + deltaX;
    const targetY = y + deltaY;
    
    // Get the display nearest to where the window is being moved
    const display = screen.getDisplayNearestPoint({ x: Math.round(targetX + w/2), y: Math.round(targetY + h/2) });
    const bounds = display.bounds; // Use full bounds (allows walking on the taskbar)

    // Loose clamp: allow the window to go mostly off-screen but keep at least 50px visible
    const clampedX = Math.max(bounds.x - w + 50, Math.min(bounds.x + bounds.width - 50, targetX));
    const clampedY = Math.max(bounds.y - h + 50, Math.min(bounds.y + bounds.height - 50, targetY));
    
    companionWindow.setPosition(Math.round(clampedX), Math.round(clampedY));
  }
});

ipcMain.on('companion-send-message', (event, text) => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('companion-send-message', text);
  }
});

ipcMain.on('companion-toggle-listening', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('companion-toggle-listening');
  }
});

ipcMain.on('toggle-companion-window', (event, show) => {
  if (companionWindow && !companionWindow.isDestroyed()) {
    if (show) {
      companionWindow.show();
    } else {
      companionWindow.hide();
    }
  } else if (show) {
    createCompanionWindow();
  }
});

ipcMain.on('forward-to-companion', (event, { channel, data }) => {
  if (companionWindow && !companionWindow.isDestroyed()) {
    companionWindow.webContents.send(channel, data);
  }
});

ipcMain.on('resize-companion-window', (event, scale) => {
  if (companionWindow && !companionWindow.isDestroyed()) {
    const [oldW, oldH] = companionWindow.getSize();
    const [x, y] = companionWindow.getPosition();
    
    const newW = Math.round(280 * scale);
    const newH = Math.round(450 * scale);
    
    const newX = x + Math.round((oldW - newW) / 2);
    const newY = y + Math.round((oldH - newH) / 2);
    
    companionWindow.setBounds({ x: newX, y: newY, width: newW, height: newH });
  }
});

// --- File System IPC Handlers ---
ipcMain.handle('read-dir', async (event, dirPath) => {
  try {
    const files = await fs.readdir(dirPath, { withFileTypes: true });
    return files.map(f => ({ name: f.name, isDirectory: f.isDirectory() }));
  } catch (error) {
    console.error('Error reading dir:', error);
    return [];
  }
});

ipcMain.handle('read-file', async (event, filePath) => {
  try {
    return await fs.readFile(filePath, 'utf-8');
  } catch (error) {
    console.error('Error reading file:', error);
    return '';
  }
});

ipcMain.handle('write-file', async (event, filePath, content) => {
  try {
    await fs.writeFile(filePath, content, 'utf-8');
    return true;
  } catch (error) {
    console.error('Error writing file:', error);
    return false;
  }
});

// --- System Monitor IPC Handlers ---
ipcMain.handle('get-system-info', async () => {
  try {
    const cpu = await si.currentLoad();
    const mem = await si.mem();
    const graphics = await si.graphics();
    return {
      cpuLoad: cpu.currentLoad,
      memTotal: mem.total,
      memUsed: mem.active,
      gpus: graphics.controllers
    };
  } catch (error) {
    console.error('Error getting sys info:', error);
    return null;
  }
});

// --- Terminal IPC Handlers ---
let ptyProcess = null;
try {
  const shell = os.platform() === 'win32' ? 'powershell.exe' : 'bash';
  ptyProcess = pty.spawn(shell, [], {
    name: 'xterm-color',
    cols: 80,
    rows: 30,
    cwd: process.env.USERPROFILE || process.cwd(),
    env: process.env
  });

  ptyProcess.onData((data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('terminal-incData', data);
    }
  });

  ipcMain.on('terminal-intoTerm', (event, data) => {
    if (ptyProcess) ptyProcess.write(data);
  });

  ipcMain.on('terminal-resize', (event, { cols, rows }) => {
    if (ptyProcess) {
      try {
        ptyProcess.resize(cols, rows);
      } catch (e) {
        console.error('Resize error', e);
      }
    }
  });
} catch (error) {
  console.error("Failed to initialize node-pty", error);
}

// --- Memory Telemetry Loop (Placeholder) ---
// Ideally, we capture screenshots using desktopCapturer and grab active window.
// We'd send this to the React app which has the websocket.
setInterval(() => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    // Send telemetry to frontend to forward to backend WS
    mainWindow.webContents.send('memory-telemetry', {
      timestamp: Date.now(),
      active_window: "Unknown Window",
      keystrokes: [] // Requires global keylogger like iohook
    });
  }
}, 10000);
