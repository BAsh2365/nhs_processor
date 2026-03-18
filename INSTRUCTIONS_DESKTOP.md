# NHS Cardio Triage - Desktop App Setup

This document describes how to run the application as a standalone desktop app using Electron.

## Prerequisites

1.  **Python Environment:** Ensure you have the Python virtual environment set up and dependencies installed.
    ```bash
    # Windows
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    ```
    *Note: `flask-cors` has been added to requirements.txt.*

2.  **Node.js:** Ensure Node.js is installed.

## Setup Steps

### 1. Build the UI

The Next.js frontend needs to be built as a static site.

```bash
cd ui
npm install
npm run build
# This will create an 'out' directory in 'ui/'
cd ..
```

### 2. Install Electron Dependencies

```bash
cd electron
npm install
cd ..
```

### 3. Run the Desktop App

You can now launch the desktop application. The Electron wrapper will automatically start the Python backend in the background.

```bash
cd electron
npm start
```

## Development Notes

-   **Backend:** The Flask backend (`frontend/app.py`) has been modified to serve only JSON APIs and support CORS.
-   **Frontend:** The Next.js app (`ui/`) is configured for static export (`output: 'export'`).
-   **Electron:** The `electron/main.js` script orchestrates the Python process and the frontend window.
-   **API Key:** The Electron app sets `NHS_API_KEYS=dev-key` automatically for the backend process.

## Troubleshooting

-   **Backend Fails to Start:** Check the console output in the terminal where you ran `npm start`. Errors from the Python process will be logged there. Ensure `flask-cors` is installed (`pip install flask-cors`).
-   **White Screen:** If the window is blank, check if `ui/out/index.html` exists. Run `npm run build` in the `ui` directory again.
