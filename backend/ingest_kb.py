# backend/ingest_kb.py - UPDATED

import os
import sys
from typing import Optional

# Add parent directory to path to allow imports
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Now import will work
try:
    from backend import kb_chroma as kb
except ImportError:
    import kb_chroma as kb

PDF_DIR = os.path.join(ROOT, "frontend", "knowledge_pdfs")

def ingest_folder(pdf_dir: Optional[str] = None):
    folder = pdf_dir or PDF_DIR
    print(f"Ingesting files from: {folder}")
    
    # Check if folder exists
    if not os.path.exists(folder):
        print(f"ERROR: Directory does not exist: {folder}")
        print(f"Creating directory: {folder}")
        os.makedirs(folder, exist_ok=True)
        print(f"Directory created. Please add PDF files to: {folder}")
        return
    
    # Check if folder has PDF files
    pdf_files = [f for f in os.listdir(folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print(f"⚠️  WARNING: No PDF files found in: {folder}")
        print(f"Please add NHS guideline PDFs to this directory")