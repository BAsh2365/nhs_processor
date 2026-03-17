"""
Tests for backend/risk_assessor.py — config-driven risk assessment.
Requires spacy to be installed.
"""

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Check if spacy is available
try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False

pytestmark = pytest.mark.skipif(not HAS_SPACY, reason="spacy not installed")

from backend.config_loader import load_framework


# ---------------------------------------------------------------------------
# Fixtures — load once per module for speed (spacy model load is slow)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def nhs_assessor():
    from backend.risk_assessor import CardiovascularRiskAssessor
    return CardiovascularRiskAssessor(config=load_framework("nhs_uk"))


@pytest.fixture(scope="module")
def us_assessor():
    from backend.risk_assessor import CardiovascularRiskAssessor
    return CardiovascularRiskAssessor(config=load_framework("us_aha"))


@pytest.fixture(scope="module")
def achd_assessor():
    from backend.risk_assessor import CardiovascularRiskAssessor
    return CardiovascularRiskAssessor(config=load_framework("nhs_uk", scopes=["congenital_achd"]))


@pytest.fixture(scope="module")
def default_assessor():
    from backend.risk_assessor import CardiovascularRiskAssessor
    return CardiovascularRiskAssessor()


# ---------------------------------------------------------------------------
# 1. Backward compatibility (no config)
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_default_init_works(self, default_assessor):
        assert default_assessor.level_emergency == "EMERGENCY"
        assert default_assessor.level_urgent == "URGENT"
        assert default_assessor.level_routine == "ROUTINE"

    def test_default_red_flags_count(self, default_assessor):
        assert len(default_assessor.red_flags) >= 26

    def test_default_surgical_indicators_count(self, default_assessor):
        assert len(default_assessor.surgical_indicators) >= 12

    def test_default_scoring_weights(self, default_assessor):
        assert default_assessor.rf_weight == 3.0
        assert default_assessor.surg_weight == 1.0
        assert default_assessor.emerg_weight == 5.0


# ---------------------------------------------------------------------------
# 2. NHS framework triage
# ---------------------------------------------------------------------------

class TestNHSTriage:
    def test_emergency_aortic_dissection(self, nhs_assessor):
        text = "Suspected acute aortic dissection with tearing chest pain radiating to back and pulse deficit."
        urgency, flags = nhs_assessor.assess_urgency(text)
        assert urgency == "EMERGENCY"
        assert len(flags) > 0

    def test_emergency_stemi(self, nhs_assessor):
        text = "ECG shows STEMI with ST elevation in leads II, III, aVF."
        urgency, flags = nhs_assessor.assess_urgency(text)
        assert urgency == "EMERGENCY"

    def test_routine_stable_angina(self, nhs_assessor):
        text = "Patient with stable exertional chest discomfort, no rest pain, no syncope. Normal ECG."
        urgency, flags = nhs_assessor.assess_urgency(text)
        assert urgency == "ROUTINE"

    def test_nhs_returns_nhs_levels(self, nhs_assessor):
        for text in ["Routine follow-up", "Syncope with murmur", "STEMI with cardiogenic shock"]:
            urgency, _ = nhs_assessor.assess_urgency(text)
            assert urgency in ["EMERGENCY", "URGENT", "ROUTINE"]


# ---------------------------------------------------------------------------
# 3. US AHA framework triage
# ---------------------------------------------------------------------------

class TestUSTriage:
    def test_uses_emergent_level(self, us_assessor):
        text = "STEMI with cardiogenic shock, activate cath lab."
        urgency, flags = us_assessor.assess_urgency(text)
        assert urgency == "EMERGENT"

    def test_uses_elective_level(self, us_assessor):
        text = "Routine annual cardiology follow-up, no symptoms."
        urgency, flags = us_assessor.assess_urgency(text)
        assert urgency == "ELECTIVE"

    def test_cardiac_tamponade_red_flag(self, us_assessor):
        text = "Patient presents with cardiac tamponade, Beck's triad, hypotension."
        urgency, flags = us_assessor.assess_urgency(text)
        assert urgency == "EMERGENT"
        assert any("tamponade" in f.lower() for f in flags)

    def test_lvad_surgical_indicator(self, us_assessor):
        text = "Evaluation for LVAD candidacy due to refractory heart failure."
        urgency, flags = us_assessor.assess_urgency(text)
        assert any("lvad" in f.lower() for f in flags)


# ---------------------------------------------------------------------------
# 4. ACHD scope triage
# ---------------------------------------------------------------------------

class TestACHDTriage:
    def test_eisenmenger_red_flag(self, achd_assessor):
        text = "Patient with Eisenmenger syndrome and progressive cyanosis."
        urgency, flags = achd_assessor.assess_urgency(text)
        assert any("eisenmenger" in f.lower() for f in flags)

    def test_fontan_failure_emergency(self, achd_assessor):
        text = "Patient with Fontan failure, declining cardiac output."
        urgency, flags = achd_assessor.assess_urgency(text)
        assert urgency == "EMERGENCY"

    def test_protein_losing_enteropathy(self, achd_assessor):
        text = "Fontan patient with protein-losing enteropathy."
        urgency, flags = achd_assessor.assess_urgency(text)
        assert any("protein-losing enteropathy" in f.lower() for f in flags)

    def test_achd_preserves_base_terms(self, achd_assessor):
        text = "Patient with tearing chest pain and pulse deficit — suspected aortic dissection."
        urgency, flags = achd_assessor.assess_urgency(text)
        assert urgency == "EMERGENCY"


# ---------------------------------------------------------------------------
# 5. Scoring mechanics
# ---------------------------------------------------------------------------

class TestScoringMechanics:
    def test_single_surgical_indicator_is_routine(self, nhs_assessor):
        text = "Known aortic stenosis, stable."
        urgency, flags = nhs_assessor.assess_urgency(text)
        assert urgency == "ROUTINE"

    def test_emergency_pattern_alone_triggers_emergency(self, nhs_assessor):
        text = "ECG confirms STEMI."
        urgency, flags = nhs_assessor.assess_urgency(text)
        assert urgency == "EMERGENCY"

    def test_empty_text_is_routine(self, nhs_assessor):
        urgency, flags = nhs_assessor.assess_urgency("")
        assert urgency == "ROUTINE"
        assert flags == []

    def test_flags_are_deduplicated(self, nhs_assessor):
        text = "Ongoing chest pain. The patient has ongoing chest pain."
        _, flags = nhs_assessor.assess_urgency(text)
        assert len(flags) == len(set(flags))


# ---------------------------------------------------------------------------
# 6. Test with actual referral files
# ---------------------------------------------------------------------------

class TestWithReferralFiles:
    @pytest.fixture
    def referral_dir(self):
        return os.path.join(ROOT, "frontend", "test_pdfs")

    def _read(self, referral_dir, filename):
        with open(os.path.join(referral_dir, filename), "r", encoding="utf-8") as f:
            return f.read()

    def test_referral_3_emergency(self, nhs_assessor, referral_dir):
        text = self._read(referral_dir, "patient_referral_3.txt")
        urgency, flags = nhs_assessor.assess_urgency(text)
        assert urgency == "EMERGENCY"

    def test_achd_referral_2_urgent_or_emergency(self, achd_assessor, referral_dir):
        text = self._read(referral_dir, "patient_referral_achd_2.txt")
        urgency, flags = achd_assessor.assess_urgency(text)
        assert urgency in ["URGENT", "EMERGENCY"]

    def test_us_referral_1_emergent(self, us_assessor, referral_dir):
        text = self._read(referral_dir, "patient_referral_us_1.txt")
        urgency, flags = us_assessor.assess_urgency(text)
        assert urgency == "EMERGENT"
