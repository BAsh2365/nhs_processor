
import os
from typing import Optional
from . import kb_chroma as kb

ROOT = os.path.dirname(os.path.dirname(__file__))
PDF_DIR = os.path.join(ROOT, "frontend", "knowledge_pdfs")

def ingest_folder(pdf_dir: Optional[str] = None):
    folder = pdf_dir or PDF_DIR
    print(f"Ingesting files from: {folder}")
    kb.ingest_folder_chunked(folder)
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_folder()
