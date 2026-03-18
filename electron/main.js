const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let pythonProcess;

// Configuration
const PYTHON_PORT = 5000;
const API_URL = `http://127.0.0.1:${PYTHON_PORT}`;

// Path to Python backend
const PROJECT_ROOT = path.join(__dirname, '..');
const BACKEND_SCRIPT = path.join(PROJECT_ROOT, 'frontend', 'app.py');

// Determine Python executable
let pythonExecutable = 'python'; // Default to PATH

// Check for local venv (Windows)
const venvPythonWin = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe');
if (fs.existsSync(venvPythonWin)) {
  pythonExecutable = venvPythonWin;
}

// Check for local venv (Unix)
const venvPythonUnix = path.join(PROJECT_ROOT, '.venv', 'bin', 'python');
if (fs.existsSync(venvPythonUnix)) {
  pythonExecutable = venvPythonUnix;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false, // For simple IPC if needed
    },
    title: "NHS Cardio Triage AI",
  });

  // Load the Next.js static export
  // In development, you might want to load http://localhost:3000
  // But for the final build, we load the file.
  const startUrl = path.join(PROJECT_ROOT, 'ui', 'out', 'index.html');
  
  if (fs.existsSync(startUrl)) {
    mainWindow.loadFile(startUrl);
  } else {
    console.error(`Could not find UI at ${startUrl}. Did you run 'npm run build' in ui/?`);
    mainWindow.loadURL('data:text/html,<h1>Error: UI build not found.</h1><p>Please run <code>npm run build</code> in the <code>ui/</code> directory.</p>');
  }

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

function startPythonBackend() {
  console.log(`Starting Python backend with: ${pythonExecutable}`);
  console.log(`Script: ${BACKEND_SCRIPT}`);

  // Set environment variables for the backend
  const env = { ...process.env, NHS_API_KEYS: 'dev-key', FLASK_ENV: 'production' };

  pythonProcess = spawn(pythonExecutable, [BACKEND_SCRIPT], {
    cwd: PROJECT_ROOT, // Run from project root so imports work
    env: env
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Backend]: ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Backend Error]: ${data}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Backend process exited with code ${code}`);
  });
}

app.on('ready', () => {
  startPythonBackend();
  // Give the backend a moment to start (optional, but polite)
  setTimeout(createWindow, 1000);
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', function () {
  if (mainWindow === null) {
    createWindow();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) {
    console.log('Killing Python backend...');
    pythonProcess.kill();
  }
});
