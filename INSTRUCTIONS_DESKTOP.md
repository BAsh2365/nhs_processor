# NHS Cardio Triage - Desktop App

Run the application as a standalone desktop app using Electron + Next.js static export + Flask backend.

## Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with npm

## Quick Start

```bash
# 1. Python environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 2. Build the UI (static export)
cd ui
npm install
npm run build                 # Creates ui/out/
cd ..

# 3. Install Electron
cd electron
npm install
cd ..

# 4. Launch
cd electron
npm start
```

The Electron app will:
1. Show a splash screen while the backend starts
2. Launch the Flask backend with correct environment variables
3. Health-check the backend (polls `/health` until ready)
4. Open the main window once the backend is live

## AI Model Fallback Chain

The app tries AI models in this order:

| Priority | Model | Source | Quality | Requirement |
|----------|-------|--------|---------|-------------|
| 1 | Phi-3 mini | Ollama (localhost:11434) | Best | Install [Ollama](https://ollama.com) and run `ollama pull phi3:mini` |
| 2 | BioGPT | HuggingFace (local) | Good | Auto-downloaded on first use (~1.5 GB) |
| 3 | Rule-based | Built-in | Conservative | Always available |

**Without Ollama installed**, the app falls back to BioGPT or rule-based triage automatically.
This is safe — the rule-based fallback has a conservative safety bias.

To use Ollama for best results:
```bash
# Install Ollama from https://ollama.com, then:
ollama pull phi3:mini
# Ollama runs on localhost:11434 by default — the desktop app connects there automatically
```

## Data Storage

The desktop app stores runtime data in your OS app data directory:

| Data | Location |
|------|----------|
| Audit logs | `%APPDATA%/nhs-cardio-triage-desktop/audit_logs/` |
| Uploads (temp) | `%APPDATA%/nhs-cardio-triage-desktop/uploads/` |
| Session key | `%APPDATA%/nhs-cardio-triage-desktop/.flask_secret_key` |

Uploaded files are deleted immediately after processing.

## Environment Variables

Override defaults by setting these before launching:

| Variable | Desktop Default | Purpose |
|----------|----------------|---------|
| `NHS_API_KEYS` | `dev-key` | API authentication keys |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama service URL |
| `OLLAMA_MODEL` | `phi3:mini` | LLM model for clinical reasoning |
| `FORCE_CPU` | `0` | Set `1` to disable GPU |

## Building a Distributable

```bash
cd electron
npm run dist    # Creates installer in electron/dist/
```

This packages the Electron shell. Users still need Python + dependencies installed separately (or bundle with PyInstaller for a fully self-contained build).

## Troubleshooting

- **"UI Not Built" error**: Run `cd ui && npm install && npm run build`
- **Backend timeout**: Check console output for Python errors. Ensure `pip install -r requirements.txt` completed successfully.
- **Blank/white screen**: Verify `ui/out/index.html` exists after build.
- **Ollama not detected**: The app will silently fall back to BioGPT/rules. Install Ollama for better results.

## Server Deployment

For server/cloud deployment (Docker, gunicorn), see the `deploy/` directory and use `requirements-server.txt` instead.
