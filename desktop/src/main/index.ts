import { app, BrowserWindow, session } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import net from 'net';

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const backendHost = process.env.BILITOOLS_HOST || '127.0.0.1';
const backendPort = Number(process.env.BILITOOLS_PORT || process.env.PORT || '8001');
const backendOrigin = `http://${backendHost}:${backendPort}`;

function isBackendListening(): Promise<boolean> {
  return new Promise((resolve) => {
    const probe = net.createConnection(backendPort, backendHost);
    probe.once('connect', () => {
      probe.destroy();
      resolve(true);
    });
    probe.once('error', () => resolve(false));
    probe.setTimeout(800, () => {
      probe.destroy();
      resolve(false);
    });
  });
}

async function startBackend(): Promise<void> {
  if (await isBackendListening()) {
    console.log(`[Plus] Reusing existing backend on ${backendOrigin}`);
    return;
  }

  const isDev = !app.isPackaged;

  let backendDir: string;
  let command: string;
  let args: string[];

  if (isDev) {
    const projectRoot = path.resolve(__dirname, '../../..');
    backendDir = projectRoot;
    const pythonBin = process.platform === 'win32'
      ? path.join('app', '.venv', 'Scripts', 'python.exe')
      : path.join('app', '.venv', 'bin', 'python');
    command = path.join(projectRoot, pythonBin);
    args = ['-m', 'app.main'];
  } else {
    backendDir = path.resolve(process.resourcesPath, 'backend');
    const executableName = process.platform === 'win32' ? 'backend.exe' : 'backend';
    command = path.join(backendDir, executableName);
    args = [];
    if (!fs.existsSync(command)) {
      const embeddedPython = process.platform === 'win32'
        ? path.join('python', 'python.exe')
        : path.join('python', 'bin', 'python');
      command = path.join(backendDir, embeddedPython);
      args = ['-m', 'app.main'];
    }
  }

  console.log('[Plus] Starting backend from:', backendDir);
  console.log('[Plus] Backend command:', command, args.join(' '));

  return new Promise((resolve) => {
    backendProcess = spawn(command, args, {
      cwd: backendDir,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUNBUFFERED: '1', BILITOOLS_PLUS_ROOT: backendDir, PORT: String(backendPort) },
    });

    let started = false;
    backendProcess.stdout?.on('data', (data) => {
      const msg = data.toString();
      console.log('[Backend]', msg);
      if (!started && msg.includes('Uvicorn running')) {
        started = true;
        resolve();
      }
    });
    backendProcess.stderr?.on('data', (data) => {
      const msg = data.toString();
      console.error('[Backend Error]', msg);
      if (!started && msg.includes('Uvicorn running')) {
        started = true;
        resolve();
      }
    });
    backendProcess.on('error', (err) => console.error('Backend failed to start:', err));

    // 5s fallback — don't block window creation forever
    setTimeout(resolve, 5000);
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 16, y: 16 },
    backgroundColor: '#070a0e',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (app.isPackaged) {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  } else {
    mainWindow.loadURL('http://localhost:1420');
  }

  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(async () => {
  // Allow file:// origin to make cross-origin requests to the backend
  await session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const responseHeaders: Record<string, string[]> = {
      ...(details.responseHeaders || {}),
    };
    // Inject CORS headers for backend responses so file:// renderer can read them
    if (details.url.startsWith(backendOrigin) || details.url.startsWith(`http://localhost:${backendPort}`)) {
      responseHeaders['access-control-allow-origin'] = ['*'];
      responseHeaders['access-control-allow-headers'] = ['*'];
      responseHeaders['access-control-allow-methods'] = ['GET, POST, PUT, DELETE, OPTIONS'];
    }
    callback({ responseHeaders });
  });

  if (process.env.BILITOOLS_SKIP_BACKEND !== '1') {
    await startBackend();
  }
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  backendProcess?.kill();
  if (process.platform !== 'darwin') app.quit();
});
