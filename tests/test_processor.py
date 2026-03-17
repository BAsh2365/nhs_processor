"""
Tests for backend/processor.py — multi-framework processor integration.
Tests config wiring and interface via mocking to avoid ML dependency requirements.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.config_loader import load_framework

# Check if ML dependencies are available
try:
    import spacy
    import torch
    import transformers
    HAS_ML_DEPS = True
except ImportError:
    HAS_ML_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_ML_DEPS, reason="ML dependencies (spacy, torch, transformers) not installed")


# ---------------------------------------------------------------------------
# 1. Processor initialization
# ---------------------------------------------------------------------------

class TestProcessorInit:
    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    def test_default_framework_is_nhs(self, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor
        proc = MedicalDocumentProcessor(framework_id="nhs_uk")
        assert proc.framework_id == "nhs_uk"
        assert proc.config["urgency_levels"] == ["EMERGENCY", "URGENT", "ROUTINE"]

    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    def test_us_framework(self, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor
        proc = MedicalDocumentProcessor(framework_id="us_aha")
        assert proc.framework_id == "us_aha"
        assert proc.config["urgency_levels"] == ["EMERGENT", "URGENT", "ELECTIVE"]

    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    def test_achd_scope(self, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor
        proc = MedicalDocumentProcessor(framework_id="nhs_uk", scopes=["congenital_achd"])
        assert "congenital_achd" in proc.scopes
        assert "congenital_achd_kb" in proc._kb_collections

    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    def test_config_passed_to_risk_assessor(self, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor
        proc = MedicalDocumentProcessor(framework_id="nhs_uk")
        mock_risk.assert_called_once()
        call_kwargs = mock_risk.call_args
        assert "config" in call_kwargs.kwargs

    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    def test_config_passed_to_engine(self, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor
        proc = MedicalDocumentProcessor(framework_id="nhs_uk")
        mock_engine.assert_called_once()
        call_kwargs = mock_engine.call_args
        assert "config" in call_kwargs.kwargs

    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    def test_kb_collections_from_config(self, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor
        proc = MedicalDocumentProcessor(framework_id="us_aha")
        assert proc._kb_collections == ["us_aha_kb"]

    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    def test_nonexistent_framework_raises(self, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor
        with pytest.raises(FileNotFoundError):
            MedicalDocumentProcessor(framework_id="nonexistent")


# ---------------------------------------------------------------------------
# 2. Process text (mocked components)
# ---------------------------------------------------------------------------

class TestProcessText:
    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    @patch("backend.processor.anonymize_text")
    @patch("backend.processor.kb")
    def test_process_text_returns_framework_name(self, mock_kb, mock_anon, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor

        mock_anon.return_value = ("anonymized text " * 10, "abc123hash")
        mock_kb.query.return_value = []
        mock_risk_instance = mock_risk.return_value
        mock_risk_instance.assess_urgency.return_value = ("URGENT", ["syncope"])
        mock_engine_instance = mock_engine.return_value
        mock_engine_instance.summarize.return_value = "Test summary"
        mock_engine_instance.generate_recommendation.return_value = {
            "urgency": "URGENT", "red_flags": ["syncope"],
            "suggested_timeframe": "2 weeks", "evidence_basis": "NICE",
            "reasoning": "test", "recommendation_type": "CARDIOVASCULAR_TRIAGE",
            "confidence_level": "cautious"
        }

        proc = MedicalDocumentProcessor(framework_id="nhs_uk")
        result = proc.process_text("This is test clinical text with enough content for processing.")
        assert result["status"] == "success"
        assert result["framework"] == "NHS UK"

    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    def test_process_text_too_short(self, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor
        proc = MedicalDocumentProcessor(framework_id="nhs_uk")
        result = proc.process_text("Short.")
        assert result["status"] == "error"

    @patch("backend.processor.ClinicalRecommendationEngine")
    @patch("backend.processor.CardiovascularRiskAssessor")
    @patch("backend.processor.anonymize_text")
    @patch("backend.processor.kb")
    def test_process_text_passes_kb_collections(self, mock_kb, mock_anon, mock_risk, mock_engine):
        from backend.processor import MedicalDocumentProcessor

        mock_anon.return_value = ("anonymized text " * 10, "abc123hash")
        mock_kb.query.return_value = []
        mock_risk.return_value.assess_urgency.return_value = ("ROUTINE", [])
        mock_engine.return_value.summarize.return_value = "Summary"
        mock_engine.return_value.generate_recommendation.return_value = {
            "urgency": "ROUTINE", "red_flags": [], "suggested_timeframe": "",
            "evidence_basis": "", "reasoning": "", "recommendation_type": "",
            "confidence_level": ""
        }

        proc = MedicalDocumentProcessor(framework_id="nhs_uk", scopes=["congenital_achd"])
        proc.process_text("Test clinical text with enough content for processing properly.")

        call_kwargs = mock_kb.query.call_args
        assert "nhs_kb" in call_kwargs.kwargs.get("collections", [])
        assert "congenital_achd_kb" in call_kwargs.kwargs.get("collections", [])
