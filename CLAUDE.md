# CLAUDE.md — NHS Medical Document Processor (Cardiovascular Triage AI)

## Project Overview

This is a **research-grade, locally-deployed AI triage assistant** for cardiovascular referral letters received by cardiothoracic surgical teams. It processes GP referral letters, anonymises patient data, and generates evidence-based triage recommendations (urgency classification, red-flag detection, clinical reasoning) using local ML models — no patient data leaves the deployment infrastructure.

> **CRITICAL DISCLAIMER:** This system is a decision-support tool only. Every triage output **must be reviewed and validated by a qualified clinician** before any clinical action is taken. The system does not replace clinical judgement. It is not a CE-marked medical device and must not be used as a standalone clinical decision-making instrument.

---

## Repository Structure

```
backend/
  anonymizer.py          # PII redaction (NHS number, SSN, MRN, postcodes, etc.)
  clinical_extractor.py  # Structured clinical data extraction (demographics, vitals, bloods, meds, scores)
  config_loader.py       # Multi-framework JSON config loading + scope merging
  ingest_kb.py           # ChromaDB ingestion CLI for PDF/TXT guidelines
  kb_chroma.py           # Vector similarity search over ingested guidelines
  logger.py              # DTAC-aligned audit logging (append-only daily files)
  models.py              # Dataclasses: PatientData, ClinicalRecommendation
  pdf_processor.py       # PDF text extraction (pypdf → PyMuPDF → OCR fallback)
  processor.py           # Main document processing pipeline
  recommendation.py      # ClinicalRecommendationEngine (Ollama → BioGPT → rules)
  risk_assessor.py       # CardiovascularRiskAssessor (NLP keyword + regex scoring)
  config/
    frameworks/
      nhs_uk.json        # NHS UK framework (EMERGENCY/URGENT/ROUTINE)
      us_aha.json        # US AHA/ACC framework (EMERGENT/URGENT/ELECTIVE)
    scopes/
      congenital_achd.json  # ACHD scope overlay (Fontan, Eisenmenger, etc.)

frontend/
  app.py                 # Flask REST API (JSON-only, CORS-enabled for Next.js UI)
  knowledge_pdfs/        # Source guideline PDFs for KB ingestion
    nhs/                 # NICE CG95, NG185, NG208, NG106, NG238 + NHS cardiac spec
    us_aha/              # AHA/ACC 2025 ACS, 2020 VHD, 2022 HF, 2021 Chest Pain
    congenital_achd/     # ESC 2020 ACHD, ACC/AHA 2025 ACHD
  test_pdfs/             # Dummy referral letters for testing (no real patient data)

ui/                      # Next.js 16 frontend (React UI)
tests/                   # pytest suite
deploy/                  # Docker Compose, nginx, Ollama
```

---

## Running Locally

```bash
# 1. Python environment
python -m venv .venv
.venv/Scripts/activate      # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 2. Ingest knowledge base (run once, or when guidelines change)
python -m backend.ingest_kb --collection nhs_kb       --folder frontend/knowledge_pdfs/nhs
python -m backend.ingest_kb --collection us_aha_kb    --folder frontend/knowledge_pdfs/us_aha
python -m backend.ingest_kb --collection congenital_achd_kb --folder frontend/knowledge_pdfs/congenital_achd

# 3. Start Flask API backend (port 5000)
python frontend/app.py

# 4. Start Next.js UI (port 3000, in a separate terminal)
cd ui && npm install && npm run dev
```

**Production (Docker):**
```bash
cd deploy && docker compose up -d
# Ollama pulls phi3:mini on first start (~2 GB). Wait ~2 min before first request.
```

---

## Tests

```bash
# All tests (84 auto-skip if ML deps unavailable)
pytest tests/ -v

# No-ML subset (fast, always green)
pytest tests/test_config_loader.py tests/test_anonymizer.py \
       tests/test_guideline_accuracy.py tests/test_kb_chroma.py -v
```

382 total tests; 298 pass without ML dependencies installed. Tests cover:
- Framework config structure validation
- Regex pattern compilation
- PII anonymisation (NHS, US patterns)
- Urgency classification logic
- ACHD scope merging
- Flask endpoint responses
- Guideline reference accuracy (dates, guideline IDs)
- Clinical data extraction (demographics, vitals, 36 blood tests, 250+ medications)
- Validated clinical equations (eGFR CKD-EPI 2021, CHA₂DS₂-VASc, HAS-BLED, QTc, BMI, BSA, MAP, etc.)
- Interpretation function thresholds

---

## Adding a New Clinical Framework

1. Create `backend/config/frameworks/<id>.json` following the NHS/US schema (see `nhs_uk.json` as template)
2. Add guideline PDFs to `frontend/knowledge_pdfs/<id>/`
3. Ingest: `python -m backend.ingest_kb --collection <id>_kb --folder frontend/knowledge_pdfs/<id>/`
4. Select in UI or pass `framework=<id>` in POST request

---

## Architecture Notes

### AI Pipeline (in priority order)
1. **Ollama / Phi-3 mini** — primary reasoning model (instruction-following, structured output). Runs in a separate Docker container.
2. **BioGPT (microsoft/BioGPT)** — fallback local biomedical language model (text completion, not instruction-following). Used when Ollama is unavailable.
3. **Rule-based fallback** — deterministic keyword + regex scoring. Always available. Conservative safety bias.

### Summarisation
- **BART-large-cnn (facebook/bart-large-cnn)** — abstractive summarisation of referral text. Truncated to 600 words to stay within the 1 024-token position embedding limit.

### Vector Knowledge Base
- **ChromaDB (0.4.22)** + **all-MiniLM-L6-v2** sentence embeddings
- Cosine similarity, top-k=3 snippets per query
- Separate collections per framework (nhs_kb, us_aha_kb, congenital_achd_kb)

### Risk Scoring (risk_assessor.py)
| Signal type           | Default weight |
|----------------------|---------------|
| Red flag match        | 3.0           |
| Surgical indicator    | 1.0           |
| Emergency regex match | 5.0           |
| Emergency threshold   | ≥ 5.0         |
| Urgent threshold      | ≥ 2.0         |

---

## Compliance and Security

| Area              | Implementation                                                    |
|-------------------|------------------------------------------------------------------|
| PII redaction     | Regex (NHS #, postcodes, SSN, MRN, DOB, phone, email, address)  |
| Patient ID        | SHA-256 hashed; only hash is logged or stored                    |
| Audit logging     | Append-only daily JSON files in `backend/audit_logs/`           |
| File lifecycle    | Uploads deleted after processing                                 |
| External APIs     | None — all inference is local                                    |
| DTAC (Feb 2026)   | Updated form; clinical safety via DCB0129; data protection via UK-GDPR |
| Authentication    | Optional API key list (`NHS_API_KEYS` env var)                   |
| Rate limiting     | flask-limiter, 10/min, 60/hr per IP                              |
| TLS               | nginx TLS termination in production; self-signed cert script included |

---

## Environment Variables

See `.env.example`. Key variables:

| Variable          | Default              | Purpose                              |
|-------------------|----------------------|--------------------------------------|
| `NHS_API_KEYS`    | (empty = auth off)   | Comma-separated valid API keys       |
| `FLASK_SECRET_KEY`| —                    | Flask session signing key            |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434`| Ollama service URL (use `http://ollama:11434` in Docker) |
| `OLLAMA_MODEL`    | `phi3:mini`          | LLM for clinical reasoning           |
| `FORCE_CPU`       | `0`                  | Set to `1` to disable GPU            |
| `HF_HOME`         | `~/.cache/huggingface` | Hugging Face model cache path      |

---

## Known Limitations and Future Work

- Results require fine-tuning; the system is **not production-ready**.
- BioGPT is a text-completion model, not an instruction-following model. It generates prose that must be heuristically parsed.
- Knowledge base PDFs are publicly available NHS/NICE/AHA documents; no proprietary clinical data.
- Single-worker Gunicorn deployment (PyTorch models are not thread-safe under CUDA).
- No persistent session history; audit logs are the only record.
- See README for planned improvements (graph DB, larger context window, human-in-the-loop).
