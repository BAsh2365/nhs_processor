"""
Tests for backend/recommendation.py — config-driven recommendation engine.
These tests focus on the fallback recommendation logic (no model loading required)
and config wiring. Requires transformers/torch to import.
"""

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Check if ML dependencies are available
try:
    import torch
    import transformers
    HAS_ML_DEPS = True
except ImportError:
    HAS_ML_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_ML_DEPS, reason="ML dependencies (torch, transformers) not installed")

from backend.config_loader import load_framework


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def nhs_engine():
    from backend.recommendation import ClinicalRecommendationEngine
    cfg = load_framework("nhs_uk")
    return ClinicalRecommendationEngine(use_gpu=False, config=cfg)


@pytest.fixture(scope="module")
def us_engine():
    from backend.recommendation import ClinicalRecommendationEngine
    cfg = load_framework("us_aha")
    return ClinicalRecommendationEngine(use_gpu=False, config=cfg)


@pytest.fixture(scope="module")
def achd_engine():
    from backend.recommendation import ClinicalRecommendationEngine
    cfg = load_framework("nhs_uk", scopes=["congenital_achd"])
    return ClinicalRecommendationEngine(use_gpu=False, config=cfg)


@pytest.fixture(scope="module")
def default_engine():
    from backend.recommendation import ClinicalRecommendationEngine
    return ClinicalRecommendationEngine(use_gpu=False)


# ---------------------------------------------------------------------------
# 1. Initialization
# ---------------------------------------------------------------------------

class TestInitialization:
    def test_default_init(self, default_engine):
        assert default_engine._level_emergency == "EMERGENCY"
        assert default_engine._level_urgent == "URGENT"
        assert default_engine._level_routine == "ROUTINE"

    def test_nhs_init(self, nhs_engine):
        assert nhs_engine._level_emergency == "EMERGENCY"
        assert "NICE" in nhs_engine._evidence_basis or "NHS" in nhs_engine._evidence_basis

    def test_us_init(self, us_engine):
        assert us_engine._level_emergency == "EMERGENT"
        assert us_engine._level_urgent == "URGENT"
        assert us_engine._level_routine == "ELECTIVE"
        assert "AHA" in us_engine._evidence_basis or "ACC" in us_engine._evidence_basis

    def test_achd_init(self, achd_engine):
        assert "fallback_signals" in achd_engine.config

    def test_model_ids_from_config(self, nhs_engine):
        assert nhs_engine._reasoning_model_id == "microsoft/BioGPT"
        assert nhs_engine._summarizer_model_id == "facebook/bart-large-cnn"


# ---------------------------------------------------------------------------
# 2. Fallback recommendation — NHS
# ---------------------------------------------------------------------------

class TestNHSFallback:
    def test_aortic_dissection_emergency(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation(
            "Suspected aortic dissection with tearing chest pain and mediastinal widening."
        )
        assert rec["urgency"] == "EMERGENCY"

    def test_ongoing_chest_pain_emergency(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation("Ongoing chest pain at rest, unresponsive to GTN.")
        assert rec["urgency"] == "EMERGENCY"

    def test_acs_urgent(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation("Elevated troponin, possible NSTEMI.")
        assert rec["urgency"] == "URGENT"

    def test_syncope_urgent(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation("Patient had syncope while walking.")
        assert rec["urgency"] == "URGENT"

    def test_endocarditis_urgent(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation("Suspected infective endocarditis with vegetation on echo.")
        assert rec["urgency"] == "URGENT"

    def test_stable_routine(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation("Stable patient, mild exertional dyspnoea.")
        assert rec["urgency"] == "ROUTINE"

    def test_empty_text_routine(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation("")
        assert rec["urgency"] == "ROUTINE"

    def test_nhs_evidence_basis(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation("Chest pain.")
        assert "NICE" in rec["evidence_basis"]

    def test_result_structure(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation("Test input.")
        for key in ["recommendation_type", "urgency", "suggested_timeframe",
                     "red_flags", "confidence_level", "evidence_basis", "reasoning"]:
            assert key in rec


# ---------------------------------------------------------------------------
# 3. Fallback recommendation — US AHA
# ---------------------------------------------------------------------------

class TestUSFallback:
    def test_uses_emergent_level(self, us_engine):
        rec = us_engine._fallback_recommendation("Aortic dissection with haemodynamic instability.")
        assert rec["urgency"] == "EMERGENT"

    def test_uses_elective_level(self, us_engine):
        rec = us_engine._fallback_recommendation("Stable patient, routine follow-up.")
        assert rec["urgency"] == "ELECTIVE"

    def test_us_evidence_basis(self, us_engine):
        rec = us_engine._fallback_recommendation("Chest pain.")
        assert "AHA" in rec["evidence_basis"] or "ACC" in rec["evidence_basis"]


# ---------------------------------------------------------------------------
# 4. Fallback recommendation — ACHD signals
# ---------------------------------------------------------------------------

class TestACHDFallback:
    def test_fontan_failure_emergency(self, achd_engine):
        rec = achd_engine._fallback_recommendation("Patient with Fontan failure and declining output.")
        assert rec["urgency"] == "EMERGENCY"

    def test_eisenmenger_crisis_emergency(self, achd_engine):
        rec = achd_engine._fallback_recommendation("Eisenmenger crisis with acute cyanotic deterioration.")
        assert rec["urgency"] == "EMERGENCY"

    def test_protein_losing_enteropathy_urgent(self, achd_engine):
        rec = achd_engine._fallback_recommendation(
            "Fontan patient with protein-losing enteropathy, albumin 18 g/L."
        )
        assert rec["urgency"] == "URGENT"

    def test_conduit_obstruction_urgent(self, achd_engine):
        rec = achd_engine._fallback_recommendation("Rising gradient suggesting conduit obstruction.")
        assert rec["urgency"] == "URGENT"

    def test_achd_preserves_standard_signals(self, achd_engine):
        rec = achd_engine._fallback_recommendation("STEMI with cardiogenic shock.")
        assert rec["urgency"] == "EMERGENCY"

    def test_no_achd_signals_without_scope(self, nhs_engine):
        rec = nhs_engine._fallback_recommendation("Fontan failure with declining output.")
        assert not any("ACHD" in s for s in rec["red_flags"])


# ---------------------------------------------------------------------------
# 5. Sanitization
# ---------------------------------------------------------------------------

class TestSanitization:
    def test_removes_xml_tags(self, nhs_engine):
        assert nhs_engine._sanitize_output("<TITLE>Test</TITLE>") == "Test"

    def test_removes_special_tokens(self, nhs_engine):
        assert nhs_engine._sanitize_output("Hello</s><pad>World") == "Hello World"

    def test_empty_input(self, nhs_engine):
        assert nhs_engine._sanitize_output("") == ""
        assert nhs_engine._sanitize_output(None) == ""


# ---------------------------------------------------------------------------
# 6. Public API
# ---------------------------------------------------------------------------

class TestPublicAPI:
    def test_summarize_empty(self, nhs_engine):
        assert nhs_engine.summarize("") == ""

    def test_generate_recommendation_empty(self, nhs_engine):
        rec = nhs_engine.generate_recommendation("")
        assert rec["urgency"] == "ROUTINE"

    def test_fallback_alias(self, nhs_engine):
        rec1 = nhs_engine._fallback_recommendation("Syncope.")
        rec2 = nhs_engine.fallback_recommendation("Syncope.")
        assert rec1 == rec2
