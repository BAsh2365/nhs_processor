# backend/ingest_kb.py

import os
import sys
import argparse
from typing import Optional

# Add parent directory to path to allow imports
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from backend import kb_chroma as kb
except ImportError:
    import kb_chroma as kb

PDF_DIR = os.path.join(ROOT, "frontend", "knowledge_pdfs")


def ingest_folder(pdf_dir: Optional[str] = None, collection_name: str = "nhs_kb"):
    folder = pdf_dir or PDF_DIR
    print(f"Ingesting files from: {folder}")
    print(f"Target collection: {collection_name}")

    if not os.path.exists(folder):
        print(f"ERROR: Directory does not exist: {folder}")
        print(f"Creating directory: {folder}")
        os.makedirs(folder, exist_ok=True)
        print(f"Directory created. Please add PDF files to: {folder}")
        return

    pdf_files = [f for f in os.listdir(folder) if f.lower().endswith(('.pdf', '.txt', '.md'))]
    if not pdf_files:
        print(f"WARNING: No PDF/TXT/MD files found in: {folder}")
        print("Please add guideline files to this directory")
        return

    print(f"Found {len(pdf_files)} files to ingest")
    kb.ingest_folder_chunked(folder, collection_name=collection_name)
    print("Ingestion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest knowledge base documents into ChromaDB")
    parser.add_argument("--collection", default="nhs_kb",
                        help="ChromaDB collection name (default: nhs_kb)")
    parser.add_argument("--folder", default=None,
                        help="Path to folder containing documents (default: frontend/knowledge_pdfs)")
    args = parser.parse_args()

    ingest_folder(pdf_dir=args.folder, collection_name=args.collection)
