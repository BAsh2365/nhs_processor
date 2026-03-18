#!/bin/bash
# Ollama entrypoint: start server and pull the configured model on first run.
# Used in docker-compose to ensure the model is available before the app starts.

set -e

# Start Ollama server in background
ollama serve &
SERVER_PID=$!

# Wait for server to be ready
echo "[Ollama] Waiting for server to start..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "[Ollama] Server ready."
        break
    fi
    sleep 1
done

# Pull model if not already present
MODEL="${OLLAMA_MODEL:-phi3:mini}"
echo "[Ollama] Ensuring model '$MODEL' is available..."
ollama pull "$MODEL"
echo "[Ollama] Model '$MODEL' ready."

# Keep server running in foreground
wait $SERVER_PID
