"""
Tests for backend/kb_chroma.py — multi-collection knowledge base.
These tests verify the interface and config wiring without requiring
a fully initialized ChromaDB + SentenceTransformer (which are heavy).
"""

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.config_loader import load_framework


class TestKBInterface:
    """Test that the KB module's public API signatures are correct."""

    def test_query_accepts_collections_param(self):
        from backend import kb_chroma as kb
        # Should accept collections parameter without error (may return [] if no store)
        result = kb.query("test query", k=3, collections=["nhs_kb"])
        assert isinstance(result, list)

    def test_query_accepts_embed_model_id(self):
        from backend import kb_chroma as kb
        result = kb.query("test query", k=3, embed_model_id="all-MiniLM-L6-v2")
        assert isinstance(result, list)

    def test_query_empty_returns_empty(self):
        from backend import kb_chroma as kb
        result = kb.query("", k=3)
        assert result == []

    def test_query_default_collection(self):
        from backend import kb_chroma as kb
        # Without collections param, defaults to ["nhs_kb"]
        result = kb.query("chest pain guidelines", k=3)
        assert isinstance(result, list)


class TestKBConfigIntegration:
    """Test that KB collections are correctly specified in configs."""

    def test_nhs_kb_collection(self):
        cfg = load_framework("nhs_uk")
        assert "nhs_kb" in cfg["kb_collections"]

    def test_us_kb_collection(self):
        cfg = load_framework("us_aha")
        assert "us_aha_kb" in cfg["kb_collections"]

    def test_achd_adds_collection(self):
        cfg = load_framework("nhs_uk", scopes=["congenital_achd"])
        assert "nhs_kb" in cfg["kb_collections"]
        assert "congenital_achd_kb" in cfg["kb_collections"]

    def test_us_with_achd_collections(self):
        cfg = load_framework("us_aha", scopes=["congenital_achd"])
        assert "us_aha_kb" in cfg["kb_collections"]
        assert "congenital_achd_kb" in cfg["kb_collections"]

    def test_embedding_model_in_config(self):
        cfg = load_framework("nhs_uk")
        model_id = cfg["models"]["embeddings"]["model_id"]
        assert model_id == "all-MiniLM-L6-v2"


class TestIngestKBCLI:
    """Test that ingest_kb module has CLI argument support."""

    def test_ingest_module_imports(self):
        from backend import ingest_kb
        assert hasattr(ingest_kb, 'ingest_folder')

    def test_ingest_folder_accepts_collection_name(self):
        import inspect
        from backend.ingest_kb import ingest_folder
        sig = inspect.signature(ingest_folder)
        assert "collection_name" in sig.parameters


class TestKBDirectoryStructure:
    """Verify knowledge base directories exist."""

    def test_nhs_dir_exists(self):
        path = os.path.join(ROOT, "frontend", "knowledge_pdfs", "nhs")
        assert os.path.isdir(path)

    def test_us_aha_dir_exists(self):
        path = os.path.join(ROOT, "frontend", "knowledge_pdfs", "us_aha")
        assert os.path.isdir(path)

    def test_congenital_achd_dir_exists(self):
        path = os.path.join(ROOT, "frontend", "knowledge_pdfs", "congenital_achd")
        assert os.path.isdir(path)

    def test_nhs_dir_has_pdfs(self):
        path = os.path.join(ROOT, "frontend", "knowledge_pdfs", "nhs")
        pdfs = [f for f in os.listdir(path) if f.lower().endswith(".pdf")]
        assert len(pdfs) >= 6, "NHS directory should contain the 6 original PDFs"
