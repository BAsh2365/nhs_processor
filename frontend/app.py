# --- ensure repo root is on sys.path when running this file directly ---
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]   # .../nhs_processor
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# ----------------------------------------------------------------------

from backend.processor import MedicalDocumentProcessor

import os
import io
import json
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any
import logging

from flask import (
    Flask, request, jsonify, render_template_string, render_template,
    abort, make_response
)
from werkzeug.utils import secure_filename

# ---- Flexible imports so this works with or without a 'backend' package ----
try:
    from backend.processor import MedicalDocumentProcessor
except Exception:
    from processor import MedicalDocumentProcessor


# ---- KB startup ingest (background) ---------------------------------
import threading

def _background_ingest():
    try:
        from backend.ingest_kb import ingest_folder
        ingest_folder()  # indexes frontend/knowledge_pdfs
        print("[KB] Background ingestion complete")
    except Exception as e:
        print(f"[KB] Background ingestion failed: {e}")

def _warm_kb_async_if_empty():
    try:
        from backend import kb_chroma as kb
        client, col, emb = kb._ensure()
        if col is None or not getattr(col, "count", None) or emb is None:
            print("[KB] Vector store not available → skipping ingest")
            return
        count = col.count()
        if count == 0:
            print("[KB] Empty index → starting background ingestion…")
            threading.Thread(target=_background_ingest, daemon=True).start()
        else:
            print(f"[KB] Existing chunks: {count} → skip ingest")
    except Exception as e:
        print(f"[KB] Startup ingest skipped: {e}")
# ---------------------------------------------------------------------



import re

def summarize_text(text: str, max_sentences: int = 4) -> str:
    t = " ".join((text or "").split())
    if not t:
        return ""
    import re
    parts = re.split(r'(?<=[\.\?\!])\s+', t)
    parts = [p.strip() for p in parts if len(p.strip()) > 3]
    if not parts and len(t) < 280:
        return t  # fall back to raw text if it's short
    return " ".join(parts[:max_sentences])

def humanize_recommendation(rec: dict) -> str:
    if not rec:
        return "No recommendation available."
    urgency = rec.get("urgency", "ROUTINE")
    timeframe = rec.get("suggested_timeframe", "")
    red_flags = rec.get("red_flags", []) or []
    reasoning = rec.get("reasoning", "")
    evidence = rec.get("evidence_basis", "")
    conf = rec.get("confidence_level", "cautious")
    # Build short, readable sentences
    lines = []
    lines.append(f"Urgency: {urgency}.")
    if timeframe:
        lines.append(f"Suggested timeframe: {timeframe}.")
    if red_flags:
        lines.append("Signals detected: " + ", ".join(red_flags) + ".")
    if reasoning:
        lines.append(f"Rationale: {reasoning}")
    if evidence:
        lines.append(f"Evidence: {evidence}")
    lines.append(f"Confidence: {conf}.")
    return " ".join(lines)
# -------------------------------------------------------------

# -----------------------------------------------------------------------------
# Flask setup
# -----------------------------------------------------------------------------
app = Flask(__name__)

# Hard caps and basic security
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB PDF cap
app.config["ALLOWED_EXTENSIONS"] = {"pdf"}
app.config["JSON_SORT_KEYS"] = False

# Optional CORS (comment in if you serve a separate front end domain)
# from flask_cors import CORS
# CORS(app, resources={r"/api/*": {"origins": "*"}})

# Instantiate your processor (Anthropic API key optional; can also be taken from env)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", None)
PROCESSOR = MedicalDocumentProcessor(api_key=ANTHROPIC_API_KEY, user_id=os.getenv("APP_USER_ID", "WEBAPP"))

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Cardiac Triage – NHS MVP</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 2rem; line-height: 1.45; }
    .card { max-width: 640px; border: 1px solid #ddd; border-radius: 12px; padding: 1.5rem; }
    label { display:block; margin: 0.5rem 0 0.25rem; }
    input[type="text"], input[type="file"] { width: 100%; padding: 0.5rem; }
    button { margin-top: 1rem; padding: 0.6rem 1rem; border-radius: 8px; border: 1px solid #333; background: #000; color: #fff; cursor: pointer; }
    pre { background: #f6f6f6; padding: 1rem; border-radius: 8px; overflow-x: auto;}
    .note { color: #555; font-size: 0.9rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Cardiovascular Triage (NHS MVP)</h1>
    <p class="note">Only PDF uploads are accepted. Max size 20 MB. Outputs align to NICE CG95 / NG185 / NG208 phrasing; human-in-the-loop required.</p>
    <form action="/upload" method="post" enctype="multipart/form-data">
      <label for="patient_id">Patient Identifier (hashed, not stored):</label>
      <input type="text" id="patient_id" name="patient_id" placeholder="e.g., hospital number (will be hashed)" />
      <label for="file">Upload clinical PDF</label>
      <input type="file" id="file" name="file" accept="application/pdf" required />
      <button type="submit">Analyze</button>
    </form>
    {% if result %}
      <h2>Result</h2>
      <pre>{{ result | tojson(indent=2) }}</pre>
    {% elif message %}
      <p class="note">{{ message }}</p>
    {% endif %}
  </div>
</body>
</html>
"""

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

def is_pdf_mimetype(mtype: Optional[str]) -> bool:
    return mtype in ("application/pdf", "application/x-pdf", "application/octet-stream")  # some browsers send octet-stream

def to_fhir_servicerequest(rec: Dict[str, Any], patient_identifier: str) -> Dict[str, Any]:
    """
    Minimal FHIR R4 ServiceRequest wrapper for interoperability evidence (DTAC C4).
    This does NOT claim clinical validity; it's a packaging format for downstream systems.
    """
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    urgency_map = {
        "EMERGENCY": "asap",
        "URGENT": "urgent",
        "ROUTINE": "routine"
    }
    priority = urgency_map.get(rec.get("urgency", "ROUTINE"), "routine")
    reason_text = rec.get("reasoning", "")[:1000]
    code_text = rec.get("recommendation_type", "CARDIOVASCULAR_TRIAGE")

    return {
        "resourceType": "ServiceRequest",
        "id": f"sr-{int(datetime.utcnow().timestamp())}",
        "status": "active",
        "intent": "order",
        "priority": priority,
        "code": {
            "text": code_text
        },
        "subject": {
            "identifier": {
                "system": "https://example.nhs.uk/ids",
                "value": patient_identifier  # will be hashed/stored only in audit trails by backend; this is for transport
            }
        },
        "authoredOn": now,
        "reasonCode": [{"text": reason_text}],
        "note": [
            {"text": f"Evidence: {rec.get('evidence_basis', '')}"},
            {"text": f"Suggested timeframe: {rec.get('suggested_timeframe', '')}"},
        ]
    }

# -----------------------------------------------------------------------------
# Security headers
# -----------------------------------------------------------------------------
@app.after_request
def set_security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline';"
    return resp

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template_string(INDEX_HTML, message=None, result=None)

@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}), 200

from flask import jsonify

@app.get("/admin/kb_status")
def kb_status():
    try:
        from backend import kb_chroma as kb
        client, col, emb = kb._ensure()
        if col is None or not getattr(col, "count", None) or emb is None:
            return jsonify({"available": False, "message": "Vector store not available"}), 200
        return jsonify({"available": True, "chunks": col.count()}), 200
    except Exception as e:
        return jsonify({"available": False, "error": str(e)}), 500

@app.post("/admin/ingest")
def admin_ingest():
    try:
        from backend.ingest_kb import ingest_folder
        ingest_folder()
        from backend import kb_chroma as kb
        _, col, _ = kb._ensure()
        chunks = col.count() if (col and getattr(col, "count", None)) else 0
        return jsonify({"ok": True, "chunks": chunks}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# /upload
# /upload
@app.post("/upload")
def upload_form():
    from io import BytesIO
    try:
        file = request.files.get("file")
        patient_id = request.form.get("patient_id", "") or "ANON"

        # Basic validations
        if file is None or file.filename == "":
            return render_template(
                "result.html", summary_text="", human_text="",
                raw={"success": False, "error": "No file provided."},
                error_msg="No file provided."
            ), 400

        if not allowed_file(file.filename):
            return render_template(
                "result.html", summary_text="", human_text="",
                raw={"success": False, "error": "Only PDF files are allowed."},
                error_msg="Only PDF files are allowed."
            ), 400

        if not is_pdf_mimetype(file.mimetype):
            return render_template(
                "result.html", summary_text="", human_text="",
                raw={"success": False, "error": "Invalid content type. Only PDFs are allowed."},
                error_msg="Invalid content type. Only PDFs are allowed."
            ), 400

        # Read file
        pdf_bytes = file.read() or b""
        if not pdf_bytes:
            return render_template(
                "result.html", summary_text="", human_text="",
                raw={"success": False, "error": "Empty file or unreadable content."},
                error_msg="Empty file or unreadable content."
            ), 400

        if len(pdf_bytes) > app.config["MAX_CONTENT_LENGTH"]:
            return render_template(
                "result.html", summary_text="", human_text="",
                raw={"success": False, "error": "File too large."},
                error_msg="File too large."
            ), 413

        # ---- NEW: pre-extract text so we can always show a summary, even if backend fails
        try:
            from backend.pdf_processor import PDFProcessor
            pre_text = PDFProcessor.extract_text_from_uploaded_file(BytesIO(pdf_bytes), use_ocr=True)
        except Exception as _e:
            pre_text = ""  # keep going; backend may still handle it
        pre_summary = summarize_text(pre_text) if pre_text else ""

        # Run the full pipeline
        result = PROCESSOR.process_document(BytesIO(pdf_bytes), patient_identifier=patient_id)
        if not isinstance(result, dict):
            result = {}

        # Normalise output
        success = bool(result.get("success"))
        normalized_excerpt = result.get("normalized_excerpt") or ""
        rec_dict = result.get("recommendation") or {}
        error_msg = (result.get("error") or None) if not success else None

        # If backend claims success but returned nothing useful, treat as soft failure
        if success and not (normalized_excerpt.strip() or rec_dict):
            success = False
            error_msg = "Backend returned no extractable text or recommendation."

        # Build display strings (prefer backend excerpt, else our pre-extract)
        summary_source = normalized_excerpt.strip() or pre_summary or pre_text
        summary_text = summarize_text(summary_source) if summary_source else ""
        human_text = humanize_recommendation(rec_dict) if rec_dict else ""

        status = 200 if success else 500

        # If still empty, give a user-facing hint
        if not summary_text:
            if not pre_text:
                error_msg = error_msg or "No readable text detected (this looks like a scanned PDF). Enable OCR or upload a text-based PDF."
            else:
                error_msg = error_msg or "Summary unavailable from this document."

        if not human_text:
            if rec_dict == {} and success is False and not error_msg:
                error_msg = "No recommendation generated."

        return render_template(
            "result.html",
            summary_text=summary_text or "No summary available.",
            human_text=human_text or "No recommendation available.",
            raw=result if result else {"note": "No backend result; showing pre-extracted preview only."},
            error_msg=error_msg
        ), status

    except Exception as e:
        # Final safety net
        return render_template(
            "result.html",
            summary_text="",
            human_text="",
            raw={"success": False, "error": str(e)},
            error_msg=f"Processing error: {e}"
        ), 500


@app.post("/api/analyze")
def api_analyze():
    """
    JSON API for programmatic clients.
    Returns the raw dict coming from the backend (includes patient_data, recommendation, excerpt).
    """
    if "file" not in request.files:
        return jsonify({"error": "file field required"}), 400

    file = request.files["file"]
    patient_id = request.form.get("patient_id", "") or "ANON"

    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed."}), 400

    if not is_pdf_mimetype(file.mimetype):
        return jsonify({"error": "Invalid content type. Only PDFs are allowed."}), 400

    try:
        pdf_bytes = file.read()
        # Safety check: avoid huge in-memory payloads
        if len(pdf_bytes) > app.config["MAX_CONTENT_LENGTH"]:
            return jsonify({"error": "File too large."}), 413

        result = PROCESSOR.process_document(io.BytesIO(pdf_bytes), patient_identifier=patient_id)
        status = 200 if result.get("success") else 500
        return jsonify(result), status

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.post("/api/fhir/servicerequest")
def api_fhir_service_request():
    """
    Wrap the recommendation into a minimal FHIR R4 ServiceRequest resource.
    Useful for testing interoperability (DTAC C4).
    """
    if "file" not in request.files:
        return jsonify({"error": "file field required"}), 400

    file = request.files["file"]
    patient_id = request.form.get("patient_id", "") or "ANON"

    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed."}), 400

    if not is_pdf_mimetype(file.mimetype):
        return jsonify({"error": "Invalid content type. Only PDFs are allowed."}), 400

    try:
        pdf_bytes = file.read()
        if len(pdf_bytes) > app.config["MAX_CONTENT_LENGTH"]:
            return jsonify({"error": "File too large."}), 413

        result = PROCESSOR.process_document(io.BytesIO(pdf_bytes), patient_identifier=patient_id)
        if not result.get("success"):
            return jsonify(result), 500

        fhir = to_fhir_servicerequest(result.get("recommendation", {}), patient_identifier=patient_id)
        return jsonify({"success": True, "fhir": fhir, "source": result}), 200

    except Exception as e:
        logging.exception('Unhandled exception processing FHIR ServiceRequest')
        return jsonify({"success": False, "error": "An internal error occurred."}), 500

# -----------------------------------------------------------------------------
# Error handlers
# -----------------------------------------------------------------------------
@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "File too large"}), 413

@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(405)
def method_not_allowed(_):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def server_error(err):
    return jsonify({"error": "Internal server error", "detail": str(err)}), 500

# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    _warm_kb_async_if_empty()
    port = int(os.getenv("PORT", "5057"))
    app.run(host="127.0.0.1", port=port, debug=os.getenv("DEBUG", "false").lower() == "true")

