"""
Tests for backend/config_loader.py — configuration loading, merging, and validation.
"""

import json
import os
import re
import pytest
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.config_loader import load_framework, list_frameworks, list_scopes


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def nhs_config():
    return load_framework("nhs_uk")


@pytest.fixture
def us_config():
    return load_framework("us_aha")


@pytest.fixture
def nhs_achd_config():
    return load_framework("nhs_uk", scopes=["congenital_achd"])


@pytest.fixture
def us_achd_config():
    return load_framework("us_aha", scopes=["congenital_achd"])


# ---------------------------------------------------------------------------
# 1. Framework discovery
# ---------------------------------------------------------------------------

class TestFrameworkDiscovery:
    def test_list_frameworks_returns_both(self):
        fws = list_frameworks()
        assert "nhs_uk" in fws
        assert "us_aha" in fws

    def test_list_scopes_returns_achd(self):
        scopes = list_scopes()
        assert "congenital_achd" in scopes

    def test_nonexistent_framework_raises(self):
        with pytest.raises(FileNotFoundError):
            load_framework("nonexistent_framework")

    def test_nonexistent_scope_raises(self):
        with pytest.raises(FileNotFoundError):
            load_framework("nhs_uk", scopes=["nonexistent_scope"])


# ---------------------------------------------------------------------------
# 2. JSON structure validation
# ---------------------------------------------------------------------------

class TestConfigStructure:
    REQUIRED_TOP_KEYS = [
        "id", "name", "clinical_terms", "scoring", "urgency_levels",
        "guidelines", "prompts", "pii_patterns", "branding", "kb_collections", "models"
    ]

    REQUIRED_CLINICAL_KEYS = ["red_flags", "surgical_indicators", "emergency_patterns"]
    REQUIRED_SCORING_KEYS = [
        "red_flag_weight", "surgical_indicator_weight", "emergency_pattern_weight",
        "emergency_threshold", "urgent_threshold"
    ]
    REQUIRED_PROMPT_KEYS = ["system_context", "summary_suffix", "schema_hint_suffix"]
    REQUIRED_BRANDING_KEYS = ["primary_color", "secondary_color", "logo_text"]
    REQUIRED_MODEL_KEYS = ["medical_reasoning", "summarization", "embeddings"]

    @pytest.mark.parametrize("framework_id", ["nhs_uk", "us_aha"])
    def test_has_required_top_level_keys(self, framework_id):
        cfg = load_framework(framework_id)
        for key in self.REQUIRED_TOP_KEYS:
            assert key in cfg, f"Missing key '{key}' in {framework_id}"

    @pytest.mark.parametrize("framework_id", ["nhs_uk", "us_aha"])
    def test_has_required_clinical_keys(self, framework_id):
        ct = load_framework(framework_id)["clinical_terms"]
        for key in self.REQUIRED_CLINICAL_KEYS:
            assert key in ct, f"Missing clinical_terms.{key} in {framework_id}"

    @pytest.mark.parametrize("framework_id", ["nhs_uk", "us_aha"])
    def test_has_required_scoring_keys(self, framework_id):
        sc = load_framework(framework_id)["scoring"]
        for key in self.REQUIRED_SCORING_KEYS:
            assert key in sc, f"Missing scoring.{key} in {framework_id}"

    @pytest.mark.parametrize("framework_id", ["nhs_uk", "us_aha"])
    def test_has_required_prompt_keys(self, framework_id):
        pr = load_framework(framework_id)["prompts"]
        for key in self.REQUIRED_PROMPT_KEYS:
            assert key in pr, f"Missing prompts.{key} in {framework_id}"

    @pytest.mark.parametrize("framework_id", ["nhs_uk", "us_aha"])
    def test_has_required_model_keys(self, framework_id):
        models = load_framework(framework_id)["models"]
        for key in self.REQUIRED_MODEL_KEYS:
            assert key in models, f"Missing models.{key} in {framework_id}"
            assert "model_id" in models[key]

    @pytest.mark.parametrize("framework_id", ["nhs_uk", "us_aha"])
    def test_urgency_levels_has_three(self, framework_id):
        levels = load_framework(framework_id)["urgency_levels"]
        assert len(levels) == 3

    @pytest.mark.parametrize("framework_id", ["nhs_uk", "us_aha"])
    def test_branding_colors_are_hex(self, framework_id):
        branding = load_framework(framework_id)["branding"]
        for key in self.REQUIRED_BRANDING_KEYS:
            if "color" in key:
                assert re.match(r'^#[0-9A-Fa-f]{6}$', branding[key]), \
                    f"Invalid hex color for {key}: {branding[key]}"


# ---------------------------------------------------------------------------
# 3. Regex pattern validation
# ---------------------------------------------------------------------------

class TestRegexPatterns:
    @pytest.mark.parametrize("framework_id", ["nhs_uk", "us_aha"])
    def test_emergency_patterns_compile(self, framework_id):
        cfg = load_framework(framework_id)
        for pat in cfg["clinical_terms"]["emergency_patterns"]:
            try:
                re.compile(pat)
            except re.error as e:
                pytest.fail(f"Invalid emergency regex in {framework_id}: {pat} -> {e}")

    @pytest.mark.parametrize("framework_id", ["nhs_uk", "us_aha"])
    def test_pii_patterns_compile(self, framework_id):
        cfg = load_framework(framework_id)
        for key, pii in cfg["pii_patterns"].items():
            try:
                re.compile(pii["pattern"])
            except re.error as e:
                pytest.fail(f"Invalid PII regex {key} in {framework_id}: {pii['pattern']} -> {e}")

    def test_achd_emergency_patterns_compile(self):
        cfg = load_framework("nhs_uk", scopes=["congenital_achd"])
        for pat in cfg["clinical_terms"]["emergency_patterns"]:
            try:
                re.compile(pat)
            except re.error as e:
                pytest.fail(f"Invalid ACHD emergency regex: {pat} -> {e}")

    def test_nhs_number_pattern_matches(self, nhs_config):
        pat = nhs_config["pii_patterns"]["nhs_number"]["pattern"]
        assert re.search(pat, "NHS Number: 432 876 2190")
        assert re.search(pat, "NHS Number 1234562190")

    def test_uk_postcode_pattern_matches(self, nhs_config):
        pat = nhs_config["pii_patterns"]["uk_postcode"]["pattern"]
        assert re.search(pat, "BS8 4QR", re.I)
        assert re.search(pat, "SW1A 1AA", re.I)
        assert re.search(pat, "EX1 1HS", re.I)

    def test_ssn_pattern_matches(self, us_config):
        pat = us_config["pii_patterns"]["ssn"]["pattern"]
        assert re.search(pat, "SSN: 451-78-3294")
        assert not re.search(pat, "12345")

    def test_mrn_pattern_matches(self, us_config):
        pat = us_config["pii_patterns"]["mrn"]["pattern"]
        assert re.search(pat, "MRN: 20458931", re.I)
        assert re.search(pat, "Medical Record Number: 12345678", re.I)

    def test_stemi_emergency_pattern(self, nhs_config):
        pat = nhs_config["clinical_terms"]["emergency_patterns"][0]
        assert re.search(pat, "patient has STEMI", re.I)
        assert re.search(pat, "cardiogenic shock present", re.I)

    def test_aortic_dissection_pattern(self, nhs_config):
        pat = nhs_config["clinical_terms"]["emergency_patterns"][1]
        assert re.search(pat, "suspected aortic dissection", re.I)
        assert re.search(pat, "Type A dissection", re.I)


# ---------------------------------------------------------------------------
# 4. Scope merging
# ---------------------------------------------------------------------------

class TestScopeMerging:
    def test_achd_adds_red_flags(self, nhs_config, nhs_achd_config):
        base_count = len(nhs_config["clinical_terms"]["red_flags"])
        merged_count = len(nhs_achd_config["clinical_terms"]["red_flags"])
        assert merged_count > base_count
        # Specific ACHD terms should be present
        rf = [r.lower() for r in nhs_achd_config["clinical_terms"]["red_flags"]]
        assert "eisenmenger syndrome" in rf
        assert "fontan failure" in rf
        assert "protein-losing enteropathy" in rf
        assert "plastic bronchitis" in rf

    def test_achd_adds_surgical_indicators(self, nhs_config, nhs_achd_config):
        base_count = len(nhs_config["clinical_terms"]["surgical_indicators"])
        merged_count = len(nhs_achd_config["clinical_terms"]["surgical_indicators"])
        assert merged_count > base_count
        si = [s.lower() for s in nhs_achd_config["clinical_terms"]["surgical_indicators"]]
        assert "fontan revision" in si
        assert "conduit replacement" in si
        assert "pulmonary valve replacement" in si

    def test_achd_adds_emergency_patterns(self, nhs_config, nhs_achd_config):
        base_count = len(nhs_config["clinical_terms"]["emergency_patterns"])
        merged_count = len(nhs_achd_config["clinical_terms"]["emergency_patterns"])
        assert merged_count > base_count

    def test_achd_adds_kb_collections(self, nhs_config, nhs_achd_config):
        assert "nhs_kb" in nhs_achd_config["kb_collections"]
        assert "congenital_achd_kb" in nhs_achd_config["kb_collections"]
        assert len(nhs_achd_config["kb_collections"]) > len(nhs_config["kb_collections"])

    def test_achd_sets_active_scopes(self, nhs_achd_config):
        assert "congenital_achd" in nhs_achd_config.get("active_scopes", [])

    def test_achd_includes_considerations(self, nhs_achd_config):
        assert "achd_considerations" in nhs_achd_config
        cc = nhs_achd_config["achd_considerations"]["complexity_classification"]
        assert "simple" in cc
        assert "moderate" in cc
        assert "severe" in cc

    def test_achd_includes_fallback_signals(self, nhs_achd_config):
        assert "fallback_signals" in nhs_achd_config
        assert "emergency" in nhs_achd_config["fallback_signals"]
        assert "urgent" in nhs_achd_config["fallback_signals"]

    def test_achd_works_with_us_framework(self, us_achd_config):
        """ACHD scope should merge onto US framework too."""
        rf = [r.lower() for r in us_achd_config["clinical_terms"]["red_flags"]]
        assert "eisenmenger syndrome" in rf
        assert "cardiac tamponade" in rf  # from US base
        assert us_achd_config["urgency_levels"][0] == "EMERGENT"  # US levels preserved

    def test_base_config_not_mutated_by_merge(self):
        """Loading with scope should not mutate the cached base config."""
        base = load_framework("nhs_uk")
        base_rf_count = len(base["clinical_terms"]["red_flags"])
        merged = load_framework("nhs_uk", scopes=["congenital_achd"])
        merged_rf_count = len(merged["clinical_terms"]["red_flags"])
        # The cached base should still have the original count
        base2 = load_framework("nhs_uk")
        assert len(base2["clinical_terms"]["red_flags"]) == base_rf_count
        assert merged_rf_count > base_rf_count


# ---------------------------------------------------------------------------
# 5. Caching
# ---------------------------------------------------------------------------

class TestCaching:
    def test_same_framework_returns_same_object(self):
        cfg1 = load_framework("nhs_uk")
        cfg2 = load_framework("nhs_uk")
        assert cfg1 is cfg2

    def test_different_scopes_return_different_objects(self):
        cfg1 = load_framework("nhs_uk")
        cfg2 = load_framework("nhs_uk", scopes=["congenital_achd"])
        assert cfg1 is not cfg2


# ---------------------------------------------------------------------------
# 6. NHS-specific config content
# ---------------------------------------------------------------------------

class TestNHSContent:
    def test_urgency_levels(self, nhs_config):
        assert nhs_config["urgency_levels"] == ["EMERGENCY", "URGENT", "ROUTINE"]

    def test_has_minimum_red_flags(self, nhs_config):
        assert len(nhs_config["clinical_terms"]["red_flags"]) >= 26

    def test_has_minimum_surgical_indicators(self, nhs_config):
        assert len(nhs_config["clinical_terms"]["surgical_indicators"]) >= 12

    def test_referral_guarantee_18_weeks(self, nhs_config):
        assert nhs_config["guidelines"]["referral_guarantee"] == "18-week"

    def test_nhs_branding(self, nhs_config):
        assert nhs_config["branding"]["logo_text"] == "NHS"
        assert nhs_config["branding"]["primary_color"] == "#005EB8"

    def test_kb_collection(self, nhs_config):
        assert nhs_config["kb_collections"] == ["nhs_kb"]


# ---------------------------------------------------------------------------
# 7. US AHA-specific config content
# ---------------------------------------------------------------------------

class TestUSContent:
    def test_urgency_levels(self, us_config):
        assert us_config["urgency_levels"] == ["EMERGENT", "URGENT", "ELECTIVE"]

    def test_has_us_specific_red_flags(self, us_config):
        rf = [r.lower() for r in us_config["clinical_terms"]["red_flags"]]
        assert "cardiac tamponade" in rf
        assert "flash pulmonary edema" in rf
        assert "cardiogenic shock" in rf

    def test_has_us_specific_surgical_indicators(self, us_config):
        si = [s.lower() for s in us_config["clinical_terms"]["surgical_indicators"]]
        assert "lvad candidacy" in si
        assert "cabg indication" in si
        assert "mechanical circulatory support" in si

    def test_no_referral_guarantee(self, us_config):
        assert us_config["guidelines"]["referral_guarantee"] is None

    def test_aha_branding(self, us_config):
        assert us_config["branding"]["logo_text"] == "AHA"
        assert us_config["branding"]["primary_color"] == "#C8102E"

    def test_has_ssn_pii_pattern(self, us_config):
        assert "ssn" in us_config["pii_patterns"]

    def test_has_mrn_pii_pattern(self, us_config):
        assert "mrn" in us_config["pii_patterns"]

    def test_kb_collection(self, us_config):
        assert us_config["kb_collections"] == ["us_aha_kb"]
