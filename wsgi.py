# wsgi.py — Production WSGI entrypoint
#
# Usage:
#   gunicorn -w 1 --threads 1 -b 0.0.0.0:5000 wsgi:app    (Linux/cloud)
#   waitress-serve --port=5000 wsgi:app                      (Windows laptop)
#
# IMPORTANT: Use exactly 1 worker for PyTorch GPU models (not thread-safe).

import os

# Load .env file if present (python-dotenv)
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.isfile(env_path):
        load_dotenv(env_path)
        print(f"[wsgi] Loaded environment from {env_path}")
except ImportError:
    pass

from frontend.app import create_app

app = create_app()
