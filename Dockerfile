# Dockerfile — NHS Medical Document Processor
#
# Build (with model prewarm — ~3GB larger image but zero cold-start):
#   docker build -t nhs-processor .
#
# Build (without prewarm — smaller image, 30s cold-start on first request):
#   docker build --build-arg PREWARM_MODELS=0 -t nhs-processor .
#
# Run (CPU):
#   docker run -p 5000:5000 --env-file .env nhs-processor
#
# Run (GPU — requires nvidia-container-toolkit):
#   docker run --gpus all -p 5000:5000 --env-file .env nhs-processor

FROM python:3.11-slim

# Build arg: set to 0 to skip model prewarming (smaller image, slower first request)
ARG PREWARM_MODELS=1

# System deps for PDF processing (poppler for pdf2image, tesseract for OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Pre-download ML models at build time for zero cold-start
# Clinical reasoning now handled by Ollama (Phi-3) in a separate container.
# BioGPT is kept as a fallback but not prewarmed to save image size.
RUN if [ "$PREWARM_MODELS" = "1" ]; then \
    echo "[Prewarm] Downloading ML models..." && \
    python -c "\
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline; \
from sentence_transformers import SentenceTransformer; \
print('Downloading BART-large-cnn...'); \
pipeline('summarization', model='facebook/bart-large-cnn'); \
print('Downloading sentence-transformers...'); \
SentenceTransformer('all-MiniLM-L6-v2'); \
print('[Prewarm] All models downloaded.'); \
print('[Note] Clinical reasoning uses Ollama (Phi-3) — pull model with: docker exec nhs-processor-ollama ollama pull phi3:mini'); \
" ; \
    else echo "[Prewarm] Skipping model download (PREWARM_MODELS=0)"; fi

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Single worker — PyTorch models are not thread-safe with CUDA
# Timeout 300s for first-request model loading
# forwarded-allow-ips for nginx X-Forwarded-For trust
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--threads", "1", \
     "--timeout", "300", \
     "--forwarded-allow-ips", "*", \
     "--access-logfile", "-", \
     "wsgi:app"]
