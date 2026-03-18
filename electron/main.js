const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const crypto = require('crypto');
const http = require('http');

let mainWindow;
let pythonProcess;
let splashWindow;

// Configuration
const PYTHON_PORT = 5000;
const API_URL = `http://127.0.0.1:${PYTHON_PORT}`;
const HEALTH_CHECK_INTERVAL = 500; // ms between health checks
const HEALTH_CHECK_TIMEOUT = 60000; // max wait for backend startup (ms)

// Path to Python backend
const PROJECT_ROOT = path.join(__dirname, '..');
const BACKEND_SCRIPT = path.join(PROJECT_ROOT, 'frontend', 'app.py');
const UI_OUT_DIR = path.join(PROJECT_ROOT, 'ui', 'out');

// --- Data directories ---
// Use platform-appropriate app data directory for runtime data (logs, uploads, etc.)
function getAppDataDir() {
  const appData = app.getPath('userData'); // e.g. %APPDATA%/nhs-cardio-triage-desktop
  fs.mkdirSync(appData, { recursive: true });
  return appData;
}

// --- Persistent secret key ---
// Generate once and persist so sessions survive app restarts
function getOrCreateSecretKey() {
  const appData = getAppDataDir();
  const keyFile = path.join(appData, '.flask_secret_key');
  try {
    if (fs.existsSync(keyFile)) {
      return fs.readFileSync(keyFile, 'utf-8').trim();
    }
  } catch (_) { /* regenerate */ }
  const key = crypto.randomBytes(32).toString('hex');
  fs.writeFileSync(keyFile, key, { mode: 0o600 });
  return key;
}

// --- Python executable detection ---
function findPythonExecutable() {
  // Check for local venv first (Windows then Unix)
  const venvPythonWin = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venvPythonWin)) return venvPythonWin;

  const venvPythonUnix = path.join(PROJECT_ROOT, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPythonUnix)) return venvPythonUnix;

  return 'python'; // Fall back to PATH
}

// --- UI build check ---
function isUIBuilt() {
  return fs.existsSync(path.join(UI_OUT_DIR, 'index.html'));
}

// --- Splash / loading window ---
function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 480,
    height: 320,
    frame: false,
    resizable: false,
    transparent: false,
    alwaysOnTop: true,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });

  const splashHTML = `data:text/html,${encodeURIComponent(`
    <!DOCTYPE html>
    <html>
    <head><style>
      body { margin:0; font-family: 'Segoe UI', system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0;
             display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; }
      h1 { font-size: 1.4rem; margin-bottom: 0.5rem; color: #00b4d8; }
      .spinner { width:40px; height:40px; border:3px solid #333; border-top:3px solid #00b4d8;
                 border-radius:50%; animation: spin 1s linear infinite; margin: 1rem; }
      @keyframes spin { to { transform: rotate(360deg); } }
      p { font-size: 0.9rem; color: #999; }
    </style></head>
    <body>
      <h1>NHS Cardio Triage AI</h1>
      <div class="spinner"></div>
      <p>Starting backend services...</p>
    </body>
    </html>
  `)}`;

  splashWindow.loadURL(splashHTML);
}

// --- Main window ---
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    title: 'NHS Cardio Triage AI',
    show: false, // Show after content loads
  });

  mainWindow.loadFile(path.join(UI_OUT_DIR, 'index.html'));

  mainWindow.once('ready-to-show', () => {
    if (splashWindow) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// --- Health check: poll backend until ready ---
function waitForBackend() {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();

    const check = () => {
      const req = http.get(`${API_URL}/health`, { timeout: 2000 }, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
          scheduleRetry();
        }
        res.resume(); // drain response
      });

      req.on('error', () => scheduleRetry());
      req.on('timeout', () => { req.destroy(); scheduleRetry(); });
    };

    const scheduleRetry = () => {
      if (Date.now() - startTime > HEALTH_CHECK_TIMEOUT) {
        reject(new Error('Backend failed to start within timeout'));
        return;
      }
      setTimeout(check, HEALTH_CHECK_INTERVAL);
    };

    check();
  });
}

// --- Start Python backend ---
function startPythonBackend() {
  const pythonExecutable = findPythonExecutable();
  console.log(`[Electron] Starting backend: ${pythonExecutable} ${BACKEND_SCRIPT}`);

  const appData = getAppDataDir();
  const secretKey = getOrCreateSecretKey();

  const env = {
    ...process.env,
    // Auth: dev key for local desktop use
    NHS_API_KEYS: process.env.NHS_API_KEYS || 'dev-key',
    FLASK_ENV: 'production',
    // Persistent session key
    FLASK_SECRET_KEY: secretKey,
    // Ollama: use localhost (not Docker hostname) for desktop
    OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434',
    // Desktop-appropriate data paths
    NHS_AUDIT_LOG_DIR: path.join(appData, 'audit_logs'),
    NHS_UPLOAD_DIR: path.join(appData, 'uploads'),
  };

  pythonProcess = spawn(pythonExecutable, [BACKEND_SCRIPT], {
    cwd: PROJECT_ROOT,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trimEnd()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Backend] ${data.toString().trimEnd()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Electron] Backend exited with code ${code}`);
    pythonProcess = null;
  });
}

// --- Graceful shutdown ---
function killBackend() {
  if (!pythonProcess) return;
  console.log('[Electron] Stopping backend...');
  try {
    // On Windows, kill the process tree; on Unix, send SIGTERM
    if (process.platform === 'win32') {
      execSync(`taskkill /pid ${pythonProcess.pid} /T /F`, { stdio: 'ignore' });
    } else {
      pythonProcess.kill('SIGTERM');
    }
  } catch (_) {
    // Process may have already exited
  }
  pythonProcess = null;
}

// --- App lifecycle ---
app.on('ready', async () => {
  // Check UI build exists
  if (!isUIBuilt()) {
    dialog.showErrorBox(
      'UI Not Built',
      `The Next.js UI has not been built yet.\n\nPlease run:\n  cd ui && npm install && npm run build\n\nThen restart the app.`
    );
    app.quit();
    return;
  }

  createSplashWindow();
  startPythonBackend();

  try {
    await waitForBackend();
    createMainWindow();
  } catch (err) {
    if (splashWindow) splashWindow.close();
    dialog.showErrorBox(
      'Backend Startup Failed',
      `The Python backend did not start in time.\n\n${err.message}\n\nCheck the console for errors.`
    );
    killBackend();
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null && isUIBuilt()) {
    createMainWindow();
  }
});

app.on('will-quit', () => {
  killBackend();
});
