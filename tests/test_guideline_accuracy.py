"""
Tests verifying that clinical guideline references in the framework configs
are accurate and up-to-date as of March 2026.

These tests validate the RESEARCH accuracy of the system — ensuring that
guideline IDs, titles, years, and clinical terminology are correct.
"""

import json
import os
import re
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.config_loader import load_framework


@pytest.fixture
def nhs_config():
    return load_framework("nhs_uk")


@pytest.fixture
def us_config():
    return load_framework("us_aha")


@pytest.fixture
def achd_scope():
    scope_path = os.path.join(ROOT, "backend", "config", "scopes", "congenital_achd.json")
    with open(scope_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ===========================================================================
# NHS UK GUIDELINE ACCURACY
# ===========================================================================

class TestNHSGuidelineAccuracy:
    """
    Verify NHS/NICE guideline references are correct and current as of 2026.
    Sources: NICE website, NHS England publications.
    """

    def test_nice_cg95_reference(self, nhs_config):
        """NICE CG95: 'Recent-onset chest pain of suspected cardiac origin'
        Published 24 Mar 2010, last updated 30 Nov 2016, confirmed current via 2019 surveillance.
        Still active as of 2026."""
        refs = nhs_config["guidelines"]["references"]
        cg95_refs = [r for r in refs if "CG95" in r]
        assert len(cg95_refs) == 1
        assert "chest pain" in cg95_refs[0].lower()

    def test_nice_ng185_reference(self, nhs_config):
        """NICE NG185: 'Acute coronary syndromes'
        Published 18 Nov 2020, reviewed Dec 2024. Still active."""
        refs = nhs_config["guidelines"]["references"]
        ng185_refs = [r for r in refs if "NG185" in r]
        assert len(ng185_refs) == 1
        assert "acs" in ng185_refs[0].lower()

    def test_nice_ng208_reference(self, nhs_config):
        """NICE NG208: 'Heart valve disease presenting in adults'
        Published 17 Nov 2021, reviewed Oct 2025. TAVI update in progress.
        Still active."""
        refs = nhs_config["guidelines"]["references"]
        ng208_refs = [r for r in refs if "NG208" in r]
        assert len(ng208_refs) == 1
        assert "valve" in ng208_refs[0].lower()

    def test_nice_ng106_reference_included(self, nhs_config):
        """NICE NG106: 'Chronic heart failure in adults'
        Major Sep 2025 update adding SGLT2i. Should be referenced."""
        refs = nhs_config["guidelines"]["references"]
        ng106_refs = [r for r in refs if "NG106" in r]
        assert len(ng106_refs) == 1, "NG106 (chronic heart failure, updated Sep 2025) should be referenced"

    def test_nice_ng238_reference_included(self, nhs_config):
        """NICE NG238: 'CVD risk assessment and lipid modification'
        Published Dec 2023, reviewed Sep 2025. Should be referenced."""
        refs = nhs_config["guidelines"]["references"]
        ng238_refs = [r for r in refs if "NG238" in r]
        assert len(ng238_refs) == 1, "NG238 (CVD risk assessment, Dec 2023) should be referenced"

    def test_nhs_cardiac_surgery_spec_reference(self, nhs_config):
        """NHS England Adult Cardiac Surgery Service Specification.
        Latest version Jul 2024."""
        refs = nhs_config["guidelines"]["references"]
        spec_refs = [r for r in refs if "Cardiac Surgery" in r]
        assert len(spec_refs) == 1
        assert "2024" in spec_refs[0], "Should reference Jul 2024 update"

    def test_18_week_rtt_target(self, nhs_config):
        """The 18-week referral-to-treatment guarantee is still current
        NHS Constitution policy as of 2026 (though performance is ~62%)."""
        assert nhs_config["guidelines"]["referral_guarantee"] == "18-week"

    def test_no_incorrect_ng196_reference(self, nhs_config):
        """NICE NG196 is about ATRIAL FIBRILLATION, NOT congenital heart disease.
        It should NOT appear in any cardiovascular triage context as a CHD reference."""
        refs_text = json.dumps(nhs_config)
        # NG196 should not be referenced at all in the NHS config
        assert "NG196" not in refs_text

    def test_dtac_reference_updated(self, nhs_config):
        """DTAC v1.0 is no longer current. The system prompt should reference
        the Feb 2026 DTAC update."""
        system_prompt = nhs_config["prompts"]["system_context"]
        assert "2026" in system_prompt, \
            "System prompt should reference the Feb 2026 DTAC update, not v1.0"

    def test_evidence_basis_text_contains_key_guidelines(self, nhs_config):
        evidence = nhs_config["guidelines"]["evidence_basis_text"]
        assert "CG95" in evidence
        assert "NG185" in evidence
        assert "NG208" in evidence
        assert "NG106" in evidence

    def test_urgency_levels_are_nhs_standard(self, nhs_config):
        """NHS uses EMERGENCY/URGENT/ROUTINE for triage."""
        assert nhs_config["urgency_levels"] == ["EMERGENCY", "URGENT", "ROUTINE"]

    def test_nhs_branding_correct(self, nhs_config):
        """NHS brand colour is #005EB8 (NHS Blue)."""
        assert nhs_config["branding"]["primary_color"] == "#005EB8"
        assert nhs_config["branding"]["logo_text"] == "NHS"


# ===========================================================================
# US AHA/ACC GUIDELINE ACCURACY
# ===========================================================================

class TestUSGuidelineAccuracy:
    """
    Verify AHA/ACC guideline references are correct and current as of 2026.
    Sources: AHA Journals (Circulation, JACC), ACC.org Guidelines Hub.
    """

    def test_chest_pain_2021_guideline(self, us_config):
        """AHA/ACC/ASE/CHEST/SAEM/SCCT/SCMR 2021 Guideline for Evaluation
        and Diagnosis of Chest Pain. Current with 2023 corrections."""
        refs = nhs_refs = us_config["guidelines"]["references"]
        cp_refs = [r for r in refs if "2021" in r and "Chest Pain" in r]
        assert len(cp_refs) == 1

    def test_vhd_2020_guideline(self, us_config):
        """ACC/AHA 2020 Guideline for Management of Patients with VHD.
        Still current as of 2026."""
        refs = us_config["guidelines"]["references"]
        vhd_refs = [r for r in refs if "2020" in r and ("VHD" in r or "Valvular" in r)]
        assert len(vhd_refs) == 1

    def test_heart_failure_2022_guideline(self, us_config):
        """AHA/ACC/HFSA 2022 Guideline for Management of Heart Failure.
        Published Apr 2022 (NOT 2023). Corrections published 2023. Still current."""
        refs = us_config["guidelines"]["references"]
        hf_refs = [r for r in refs if "2022" in r and ("Heart Failure" in r or "HF" in r)]
        assert len(hf_refs) == 1
        # The primary year must be 2022 (2023 corrections are acceptable context)
        assert hf_refs[0].startswith("AHA") or hf_refs[0].startswith("ACC")
        assert "2022" in hf_refs[0]

    def test_acs_2025_replaces_stemi(self, us_config):
        """The standalone 2013 STEMI guideline has been SUPERSEDED by the
        2025 ACC/AHA/ACEP/NAEMSP/SCAI ACS Guideline. The config should
        reference the 2025 ACS guideline, not a standalone 'STEMI guideline'."""
        refs = us_config["guidelines"]["references"]
        acs_refs = [r for r in refs if "2025" in r and
                    ("ACS" in r.upper() or "Acute Coronary" in r)]
        assert len(acs_refs) >= 1, \
            "Should reference the 2025 ACS Guideline that replaces standalone STEMI guideline"

    def test_no_standalone_stemi_guideline_reference(self, us_config):
        """There should not be a reference to a standalone 'STEMI Guidelines'
        without noting it's been replaced by the 2025 ACS guideline."""
        refs = us_config["guidelines"]["references"]
        for r in refs:
            if "STEMI" in r.upper() and "2013" not in r:
                # If STEMI is mentioned, it should be in context of the 2025 ACS replacement
                assert "2025" in r or "replaces" in r.lower() or "ACS" in r.upper(), \
                    f"Standalone STEMI reference found without 2025 ACS context: {r}"

    def test_evidence_basis_references_2025_acs(self, us_config):
        evidence = us_config["guidelines"]["evidence_basis_text"]
        assert "2025" in evidence, "Evidence basis should reference 2025 ACS guideline"

    def test_system_prompt_references_2025_acs(self, us_config):
        prompt = us_config["prompts"]["system_context"]
        assert "2025" in prompt, "System prompt should reference the 2025 ACS guideline"

    def test_urgency_levels_are_us_standard(self, us_config):
        """US procedural/surgical triage uses EMERGENT/URGENT/ELECTIVE."""
        assert us_config["urgency_levels"] == ["EMERGENT", "URGENT", "ELECTIVE"]

    def test_hipaa_referenced_in_prompt(self, us_config):
        """US system prompt should reference HIPAA awareness."""
        assert "HIPAA" in us_config["prompts"]["system_context"]

    def test_aha_branding_correct(self, us_config):
        """AHA brand colour is #C8102E (AHA Red)."""
        assert us_config["branding"]["primary_color"] == "#C8102E"
        assert us_config["branding"]["logo_text"] == "AHA"


# ===========================================================================
# ACHD GUIDELINE ACCURACY
# ===========================================================================

class TestACHDGuidelineAccuracy:
    """
    Verify ACHD scope references are correct and current.
    The 2018 AHA/ACC ACHD guideline was replaced by the 2025 version.
    ESC 2020 ACHD guideline is still current.
    """

    def test_references_2025_achd_guideline(self, achd_scope):
        """The 2025 ACC/AHA/HRS/ISACHD/SCAI Guideline for Adults with CHD
        (published Dec 2025) replaces the 2018 guideline."""
        refs = achd_scope["achd_considerations"]["guideline_references"]
        refs_text = " ".join(refs)
        assert "2025" in refs_text, "Should reference 2025 ACHD guideline"
        assert "replaces" in refs_text.lower() or "2018" in refs_text, \
            "Should note that it replaces the 2018 guideline"

    def test_references_esc_2020_achd(self, achd_scope):
        """ESC 2020 Guidelines on Adult Congenital Heart Disease are still current
        (ESC has not published a replacement as of Mar 2026)."""
        refs = achd_scope["achd_considerations"]["guideline_references"]
        refs_text = " ".join(refs)
        assert "ESC 2020" in refs_text
        assert "still current" in refs_text.lower() or "current" in refs_text.lower()

    def test_no_incorrect_ng196_in_achd(self, achd_scope):
        """NICE NG196 is about atrial fibrillation, NOT congenital heart disease.
        It must NOT be referenced in the ACHD scope."""
        scope_text = json.dumps(achd_scope)
        assert "NG196" not in scope_text, \
            "NG196 (atrial fibrillation) incorrectly referenced as ACHD guideline"

    def test_complexity_classification_aligns_with_2025_guideline(self, achd_scope):
        """Complexity classification (simple/moderate/severe) aligns with
        ACC/AHA 2025 ACHD Guideline stratification."""
        cc = achd_scope["achd_considerations"]["complexity_classification"]
        assert "simple" in cc
        assert "moderate" in cc
        assert "severe" in cc
        # Should reference the 2025 guideline basis
        for level in cc.values():
            if "basis" in level:
                assert "2025" in level["basis"]


# ===========================================================================
# CLINICAL TERMINOLOGY ACCURACY
# ===========================================================================

class TestClinicalTerminologyAccuracy:
    """
    Verify that clinical terms used in triage are medically accurate
    and appropriately categorized.
    """

    # --- Cardiovascular Red Flags (both frameworks) ---

    @pytest.mark.parametrize("term", [
        "ongoing chest pain",       # ACS indicator
        "diaphoresis",              # Autonomic response in MI
        "hypotension",              # Haemodynamic compromise
        "shock",                    # Cardiogenic shock
        "sustained ventricular tachycardia",  # Life-threatening arrhythmia
        "complete heart block",     # Conduction emergency
        "syncope on exertion",      # Red flag for structural heart disease
        "tearing chest pain",       # Classic aortic dissection
        "pulse deficit",            # Aortic dissection sign
        "pulmonary oedema",         # Acute decompensated HF
        "severe aortic stenosis",   # High-risk valve disease
    ])
    def test_nhs_red_flag_is_valid(self, nhs_config, term):
        """Each NHS red flag should be a recognized cardiovascular emergency indicator."""
        rf = [r.lower() for r in nhs_config["clinical_terms"]["red_flags"]]
        assert term.lower() in rf, f"'{term}' should be in NHS red flags"

    @pytest.mark.parametrize("term", [
        "cardiac tamponade",        # Life-threatening: Beck's triad
        "flash pulmonary edema",    # Acute decompensated HF emergency
        "cardiogenic shock",        # Shock from cardiac dysfunction
        "acute coronary syndrome",  # Umbrella term for STEMI/NSTEMI/UA
        "unstable angina",          # ACS subtype
    ])
    def test_us_additional_red_flag_is_valid(self, us_config, term):
        """US-specific red flags should be recognized emergency indicators."""
        rf = [r.lower() for r in us_config["clinical_terms"]["red_flags"]]
        assert term.lower() in rf, f"'{term}' should be in US red flags"

    # --- Surgical Indicators ---

    @pytest.mark.parametrize("term", [
        "LVAD candidacy",                       # MCS evaluation
        "CABG indication",                      # Surgical revascularization
        "mechanical circulatory support",        # LVAD/ECMO/Impella
        "transcatheter aortic valve replacement", # TAVR/TAVI
    ])
    def test_us_surgical_indicator_is_valid(self, us_config, term):
        """US surgical indicators should be recognized procedural terms."""
        si = [s.lower() for s in us_config["clinical_terms"]["surgical_indicators"]]
        assert term.lower() in si, f"'{term}' should be in US surgical indicators"

    # --- ACHD-Specific Terms ---

    @pytest.mark.parametrize("term,reason", [
        ("Eisenmenger syndrome",
         "Irreversible pulmonary hypertension from L-to-R shunt reversal; end-stage"),
        ("Eisenmenger physiology",
         "Pathophysiology underlying Eisenmenger syndrome"),
        ("Fontan failure",
         "Progressive deterioration of Fontan circuit; transplant indication"),
        ("failing Fontan circulation",
         "Synonym for Fontan failure"),
        ("protein-losing enteropathy",
         "Occurs in 4-13% of Fontan patients; 5-year survival 46-88%"),
        ("plastic bronchitis",
         "Occurs in ~4% of Fontan patients; airway cast formation"),
        ("arrhythmia in single ventricle",
         "High-risk arrhythmia in univentricular physiology"),
        ("baffle leak",
         "Complication of atrial switch (Mustard/Senning) repair"),
        ("conduit obstruction",
         "Progressive obstruction of RV-PA conduit"),
        ("paradoxical embolism",
         "Risk with residual intracardiac shunts"),
        ("pulmonary hypertension in ACHD",
         "Common complication in multiple CHD subtypes"),
    ])
    def test_achd_red_flag_is_valid(self, term, reason):
        """Each ACHD red flag should be a recognized clinical concern."""
        scope_path = os.path.join(ROOT, "backend", "config", "scopes", "congenital_achd.json")
        with open(scope_path, "r", encoding="utf-8") as f:
            scope = json.load(f)
        rf = [r.lower() for r in scope["red_flags_additional"]]
        assert term.lower() in rf, f"'{term}' should be in ACHD red flags ({reason})"

    @pytest.mark.parametrize("term,reason", [
        ("Fontan revision", "Surgical revision of failing Fontan circuit"),
        ("conduit replacement", "Replacement of degenerated RV-PA conduit"),
        ("pulmonary valve replacement", "Post-TOF repair for PR; percutaneous or surgical"),
        ("Ross procedure revision", "Re-intervention after Ross (autograft) procedure"),
        ("coarctation re-intervention", "Recurrent CoA requiring catheter or surgical intervention"),
        ("Ebstein repair", "Surgical repair of Ebstein anomaly"),
        ("cone repair", "Specific technique for Ebstein anomaly"),
        ("RVOT reconstruction", "Right ventricular outflow tract reconstruction"),
    ])
    def test_achd_surgical_indicator_is_valid(self, term, reason):
        """Each ACHD surgical indicator should be a recognized procedure/assessment."""
        scope_path = os.path.join(ROOT, "backend", "config", "scopes", "congenital_achd.json")
        with open(scope_path, "r", encoding="utf-8") as f:
            scope = json.load(f)
        si = [s.lower() for s in scope["surgical_indicators_additional"]]
        assert term.lower() in si, f"'{term}' should be in ACHD surgical indicators ({reason})"

    # --- ACHD Complexity Classification ---

    def test_complexity_simple_examples_valid(self, achd_scope):
        """Simple ACHD: isolated small ASD, repaired VSD without residua."""
        examples = achd_scope["achd_considerations"]["complexity_classification"]["simple"]["examples"]
        assert any("ASD" in e for e in examples)
        assert any("VSD" in e for e in examples)

    def test_complexity_moderate_examples_valid(self, achd_scope):
        """Moderate ACHD: repaired TOF, coarctation, Ebstein."""
        examples = achd_scope["achd_considerations"]["complexity_classification"]["moderate"]["examples"]
        assert any("Fallot" in e for e in examples)
        assert any("oarctation" in e for e in examples)

    def test_complexity_severe_examples_valid(self, achd_scope):
        """Severe ACHD: Fontan, Eisenmenger, single ventricle, TGA."""
        examples = achd_scope["achd_considerations"]["complexity_classification"]["severe"]["examples"]
        assert any("Fontan" in e for e in examples)
        assert any("Eisenmenger" in e for e in examples)
        assert any("single ventricle" in e.lower() or "Single ventricle" in e for e in examples)

    def test_follow_up_intervals_appropriate(self, achd_scope):
        """Follow-up intervals should decrease with complexity."""
        cc = achd_scope["achd_considerations"]["complexity_classification"]
        # Simple: 3-5 years
        assert "3-5 years" in cc["simple"]["follow_up_interval"]
        # Moderate: 1-2 years
        assert "1-2 years" in cc["moderate"]["follow_up_interval"]
        # Severe: 6-12 months
        assert "6-12 months" in cc["severe"]["follow_up_interval"]
