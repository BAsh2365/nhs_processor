"""
Tests for backend/clinical_extractor.py — structured clinical data extraction.

Covers:
  - Patient demographics extraction
  - Vital signs extraction
  - Blood test extraction with reference-range flagging
  - Medication extraction with dose/frequency
  - Clinical score computation (BMI, eGFR, MAP, QTc, CHA2DS2-VASc, etc.)
"""

import os
import sys
import math
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.clinical_extractor import (
    ClinicalDataExtractor,
    _compute_egfr_ckd_epi_2021,
    _compute_cha2ds2vasc,
    _compute_hasbled,
    _interpret_bmi,
    _interpret_map,
    _interpret_pp,
    _interpret_egfr,
    _interpret_qtc,
    _interpret_ahi,
    _interpret_lvef,
)


@pytest.fixture
def extractor():
    return ClinicalDataExtractor()


# ---------------------------------------------------------------------------
# 1. Patient demographics
# ---------------------------------------------------------------------------

class TestDemographics:
    def test_extracts_age_years(self, extractor):
        result = extractor.extract_demographics("72 year old male")
        assert result["age"] == 72

    def test_extracts_age_aged(self, extractor):
        result = extractor.extract_demographics("Aged 65, female")
        assert result["age"] == 65

    def test_extracts_sex_male(self, extractor):
        result = extractor.extract_demographics("A 55 year old gentleman")
        assert result["sex"] == "Male"

    def test_extracts_sex_female(self, extractor):
        result = extractor.extract_demographics("68 year old lady with chest pain")
        assert result["sex"] == "Female"

    def test_extracts_height_cm(self, extractor):
        result = extractor.extract_demographics("Height: 175 cm")
        assert result["height_cm"] == 175.0

    def test_extracts_height_m(self, extractor):
        result = extractor.extract_demographics("Height: 1.82 m")
        assert result["height_cm"] == 182.0

    def test_extracts_weight_kg(self, extractor):
        result = extractor.extract_demographics("Weight: 85 kg")
        assert result["weight_kg"] == 85.0

    def test_extracts_weight_lbs(self, extractor):
        result = extractor.extract_demographics("Weight: 180 lbs")
        assert result["weight_kg"] == pytest.approx(81.6, abs=0.5)

    def test_extracts_weight_stone(self, extractor):
        result = extractor.extract_demographics("Weight: 14 stone")
        assert result["weight_kg"] == pytest.approx(88.9, abs=0.5)

    def test_extracts_bmi_stated(self, extractor):
        result = extractor.extract_demographics("BMI 32.5")
        assert result["bmi_stated"] == 32.5

    def test_empty_text_returns_empty(self, extractor):
        result = extractor.extract_demographics("")
        assert result == {}

    def test_no_demographics_returns_empty(self, extractor):
        result = extractor.extract_demographics("The weather is nice today.")
        assert result == {}


# ---------------------------------------------------------------------------
# 2. Vital signs
# ---------------------------------------------------------------------------

class TestVitals:
    def test_extracts_blood_pressure(self, extractor):
        result = extractor.extract_vitals("BP 142/88 mmHg")
        assert result["systolic_bp"] == 142
        assert result["diastolic_bp"] == 88

    def test_extracts_blood_pressure_label(self, extractor):
        result = extractor.extract_vitals("Blood Pressure: 120/80")
        assert result["systolic_bp"] == 120
        assert result["diastolic_bp"] == 80

    def test_extracts_heart_rate(self, extractor):
        result = extractor.extract_vitals("HR 72 bpm")
        assert result["heart_rate"] == 72

    def test_extracts_pulse(self, extractor):
        result = extractor.extract_vitals("Pulse: 88")
        assert result["heart_rate"] == 88

    def test_extracts_spo2(self, extractor):
        result = extractor.extract_vitals("SpO2 97%")
        assert result["spo2"] == 97

    def test_extracts_oxygen_saturation(self, extractor):
        result = extractor.extract_vitals("Oxygen saturation: 94%")
        assert result["spo2"] == 94

    def test_extracts_temperature_celsius(self, extractor):
        result = extractor.extract_vitals("Temp 37.2 C")
        assert result["temperature_c"] == 37.2

    def test_extracts_temperature_fahrenheit(self, extractor):
        result = extractor.extract_vitals("Temperature: 98.6 F")
        assert result["temperature_c"] == pytest.approx(37.0, abs=0.1)

    def test_extracts_respiratory_rate(self, extractor):
        result = extractor.extract_vitals("RR 18")
        assert result["respiratory_rate"] == 18

    def test_extracts_resp_rate_full_label(self, extractor):
        result = extractor.extract_vitals("Respiratory Rate: 22")
        assert result["respiratory_rate"] == 22

    def test_empty_text_returns_empty(self, extractor):
        result = extractor.extract_vitals("")
        assert result == {}


# ---------------------------------------------------------------------------
# 3. Blood tests
# ---------------------------------------------------------------------------

class TestBloodTests:
    def test_extracts_troponin_t(self, extractor):
        results = extractor.extract_blood_tests("Troponin T: 22 ng/L")
        assert any(b["key"] == "hs_troponin_t" and b["value"] == 22.0 for b in results)

    def test_flags_troponin_high(self, extractor):
        results = extractor.extract_blood_tests("Troponin T: 22")
        match = [b for b in results if b["key"] == "hs_troponin_t"]
        assert match and match[0]["flag"] == "high"

    def test_flags_troponin_normal(self, extractor):
        results = extractor.extract_blood_tests("Troponin T: 8")
        match = [b for b in results if b["key"] == "hs_troponin_t"]
        assert match and match[0]["flag"] == "normal"

    def test_flags_troponin_critical(self, extractor):
        results = extractor.extract_blood_tests("Troponin T: 150")
        match = [b for b in results if b["key"] == "hs_troponin_t"]
        assert match and match[0]["flag"] == "critical_high"

    def test_extracts_nt_probnp(self, extractor):
        results = extractor.extract_blood_tests("NT-proBNP: 1450")
        match = [b for b in results if b["key"] == "nt_probnp"]
        assert match and match[0]["value"] == 1450.0

    def test_nt_probnp_not_confused_with_bnp(self, extractor):
        # NT-proBNP should be extracted, not BNP
        results = extractor.extract_blood_tests("NT-proBNP: 800")
        keys = [b["key"] for b in results]
        assert "nt_probnp" in keys

    def test_extracts_total_cholesterol(self, extractor):
        results = extractor.extract_blood_tests("Total Cholesterol: 6.2 mmol/L")
        match = [b for b in results if b["key"] == "total_cholesterol"]
        assert match and match[0]["value"] == 6.2
        assert match[0]["flag"] == "high"

    def test_extracts_ldl(self, extractor):
        results = extractor.extract_blood_tests("LDL: 2.5")
        match = [b for b in results if b["key"] == "ldl"]
        assert match and match[0]["value"] == 2.5
        assert match[0]["flag"] == "normal"

    def test_extracts_hdl_low(self, extractor):
        results = extractor.extract_blood_tests("HDL: 0.8")
        match = [b for b in results if b["key"] == "hdl"]
        assert match and match[0]["flag"] == "low"

    def test_extracts_hba1c_mmol(self, extractor):
        results = extractor.extract_blood_tests("HbA1c: 52 mmol/mol")
        match = [b for b in results if b["key"] == "hba1c_mmol"]
        assert match and match[0]["value"] == 52.0
        assert match[0]["flag"] == "high"

    def test_extracts_creatinine(self, extractor):
        results = extractor.extract_blood_tests("Creatinine: 128 µmol/L")
        match = [b for b in results if b["key"] == "creatinine"]
        assert match and match[0]["value"] == 128.0
        assert match[0]["flag"] == "high"

    def test_extracts_egfr(self, extractor):
        results = extractor.extract_blood_tests("eGFR: 48")
        match = [b for b in results if b["key"] == "egfr"]
        assert match and match[0]["value"] == 48.0
        assert match[0]["flag"] == "low"

    def test_extracts_sodium_normal(self, extractor):
        results = extractor.extract_blood_tests("Sodium: 140")
        match = [b for b in results if b["key"] == "sodium"]
        assert match and match[0]["flag"] == "normal"

    def test_extracts_potassium_critical_high(self, extractor):
        results = extractor.extract_blood_tests("Potassium: 6.8")
        match = [b for b in results if b["key"] == "potassium"]
        assert match and match[0]["flag"] == "critical_high"

    def test_extracts_haemoglobin(self, extractor):
        results = extractor.extract_blood_tests("Haemoglobin: 128 g/L")
        match = [b for b in results if b["key"] == "haemoglobin"]
        assert match and match[0]["value"] == 128.0

    def test_extracts_inr(self, extractor):
        results = extractor.extract_blood_tests("INR: 3.2")
        match = [b for b in results if b["key"] == "inr"]
        assert match and match[0]["flag"] == "high"

    def test_extracts_alt(self, extractor):
        results = extractor.extract_blood_tests("ALT: 45")
        match = [b for b in results if b["key"] == "alt"]
        assert match and match[0]["flag"] == "high"

    def test_extracts_tsh(self, extractor):
        results = extractor.extract_blood_tests("TSH: 0.3")
        match = [b for b in results if b["key"] == "tsh"]
        assert match and match[0]["flag"] == "low"

    def test_extracts_ferritin(self, extractor):
        results = extractor.extract_blood_tests("Ferritin: 85")
        match = [b for b in results if b["key"] == "ferritin"]
        assert match and match[0]["flag"] == "normal"

    def test_extracts_d_dimer(self, extractor):
        results = extractor.extract_blood_tests("D-dimer: 650")
        match = [b for b in results if b["key"] == "d_dimer"]
        assert match and match[0]["flag"] == "high"

    def test_extracts_crp(self, extractor):
        results = extractor.extract_blood_tests("CRP: 42")
        match = [b for b in results if b["key"] == "crp"]
        assert match and match[0]["flag"] == "high"

    def test_extracts_lactate(self, extractor):
        results = extractor.extract_blood_tests("Lactate: 4.5")
        match = [b for b in results if b["key"] == "lactate"]
        assert match and match[0]["flag"] == "critical_high"

    def test_no_duplicates(self, extractor):
        results = extractor.extract_blood_tests("Troponin T: 22\nTroponin T: 22")
        troponin_entries = [b for b in results if b["key"] == "hs_troponin_t"]
        assert len(troponin_entries) == 1

    def test_empty_returns_empty(self, extractor):
        results = extractor.extract_blood_tests("")
        assert results == []

    def test_reference_range_formatting(self, extractor):
        results = extractor.extract_blood_tests("Sodium: 140")
        match = [b for b in results if b["key"] == "sodium"]
        assert match and match[0]["reference_range"] == "135–145"

    def test_reference_range_lt(self, extractor):
        results = extractor.extract_blood_tests("Troponin T: 5")
        match = [b for b in results if b["key"] == "hs_troponin_t"]
        assert match and match[0]["reference_range"] == "<14"

    def test_reference_range_gt(self, extractor):
        results = extractor.extract_blood_tests("eGFR: 90")
        match = [b for b in results if b["key"] == "egfr"]
        assert match and match[0]["reference_range"] == ">60"


# ---------------------------------------------------------------------------
# 4. Medications
# ---------------------------------------------------------------------------

class TestMedications:
    def test_extracts_aspirin(self, extractor):
        results = extractor.extract_medications("aspirin 75mg OD")
        match = [m for m in results if m["name"].lower() == "aspirin"]
        assert match
        assert match[0]["drug_class"] == "Antiplatelet"
        assert match[0]["dose"] == "75 mg"
        assert match[0]["frequency"] == "OD"

    def test_extracts_bisoprolol(self, extractor):
        results = extractor.extract_medications("bisoprolol 5mg BD")
        match = [m for m in results if m["name"].lower() == "bisoprolol"]
        assert match
        assert match[0]["drug_class"] == "Beta-blocker"

    def test_extracts_ramipril(self, extractor):
        results = extractor.extract_medications("ramipril 10mg once daily")
        match = [m for m in results if m["name"].lower() == "ramipril"]
        assert match
        assert match[0]["drug_class"] == "ACE Inhibitor"
        assert match[0]["dose"] == "10 mg"

    def test_extracts_statin(self, extractor):
        results = extractor.extract_medications("atorvastatin 80mg nocte")
        match = [m for m in results if m["name"].lower() == "atorvastatin"]
        assert match
        assert match[0]["drug_class"] == "Statin"
        assert match[0]["frequency"] == "nocte"

    def test_extracts_anticoagulant(self, extractor):
        results = extractor.extract_medications("apixaban 5mg BD")
        match = [m for m in results if m["name"].lower() == "apixaban"]
        assert match
        assert match[0]["drug_class"] == "Anticoagulant"

    def test_extracts_diuretic(self, extractor):
        results = extractor.extract_medications("furosemide 40mg BD")
        match = [m for m in results if m["name"].lower() == "furosemide"]
        assert match
        assert match[0]["drug_class"] == "Diuretic"

    def test_extracts_mra(self, extractor):
        results = extractor.extract_medications("spironolactone 25mg OD")
        match = [m for m in results if m["name"].lower() == "spironolactone"]
        assert match
        assert match[0]["drug_class"] == "MRA"

    def test_extracts_sglt2i(self, extractor):
        results = extractor.extract_medications("dapagliflozin 10mg OD")
        match = [m for m in results if m["name"].lower() == "dapagliflozin"]
        assert match
        assert match[0]["drug_class"] == "SGLT2 Inhibitor"

    def test_extracts_arni(self, extractor):
        results = extractor.extract_medications("sacubitril/valsartan 49/51 mg BD")
        match = [m for m in results if "sacubitril" in m["name"].lower()]
        assert match
        assert match[0]["drug_class"] == "ARNI"

    def test_extracts_brand_name(self, extractor):
        results = extractor.extract_medications("Entresto 49/51mg BD")
        match = [m for m in results if m["name"].lower() == "entresto"]
        assert match
        assert match[0]["drug_class"] == "ARNI"

    def test_extracts_old_drug_name(self, extractor):
        results = extractor.extract_medications("frusemide 40mg OD")
        match = [m for m in results if m["name"].lower() == "frusemide"]
        assert match
        assert match[0]["drug_class"] == "Diuretic"

    def test_extracts_multiple_medications(self, extractor):
        text = "Current meds: aspirin 75mg OD, bisoprolol 5mg OD, ramipril 10mg OD"
        results = extractor.extract_medications(text)
        classes = {m["drug_class"] for m in results}
        assert "Antiplatelet" in classes
        assert "Beta-blocker" in classes
        assert "ACE Inhibitor" in classes

    def test_no_dose_still_extracts(self, extractor):
        results = extractor.extract_medications("patient is on warfarin")
        match = [m for m in results if m["name"].lower() == "warfarin"]
        assert match
        assert match[0]["dose"] is None

    def test_no_duplicates(self, extractor):
        results = extractor.extract_medications("aspirin 75mg OD, also takes aspirin")
        aspirin_entries = [m for m in results if m["name"].lower() == "aspirin"]
        assert len(aspirin_entries) == 1

    def test_empty_returns_empty(self, extractor):
        results = extractor.extract_medications("")
        assert results == []

    def test_prn_frequency(self, extractor):
        results = extractor.extract_medications("GTN spray PRN")
        match = [m for m in results if m["name"].lower() == "gtn"]
        assert match
        assert match[0]["frequency"] == "PRN"

    def test_ccb_extraction(self, extractor):
        results = extractor.extract_medications("amlodipine 10mg OD")
        match = [m for m in results if m["name"].lower() == "amlodipine"]
        assert match
        assert match[0]["drug_class"] == "Calcium Channel Blocker"

    def test_arb_extraction(self, extractor):
        results = extractor.extract_medications("losartan 50mg OD")
        match = [m for m in results if m["name"].lower() == "losartan"]
        assert match
        assert match[0]["drug_class"] == "ARB"

    def test_antiarrhythmic_extraction(self, extractor):
        results = extractor.extract_medications("amiodarone 200mg OD")
        match = [m for m in results if m["name"].lower() == "amiodarone"]
        assert match
        assert match[0]["drug_class"] == "Antiarrhythmic"


# ---------------------------------------------------------------------------
# 5. Clinical scores
# ---------------------------------------------------------------------------

class TestClinicalScores:
    def test_bmi_computed_when_height_weight_present(self, extractor):
        result = extractor.extract_all("72 year old male\nHeight: 180 cm\nWeight: 90 kg")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "BMI" in scores
        expected_bmi = round(90 / (1.80 ** 2), 1)
        assert scores["BMI"]["value"] == expected_bmi

    def test_bmi_uses_stated_if_present(self, extractor):
        result = extractor.extract_all("Height: 180 cm, Weight: 90 kg, BMI 28.5")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "BMI" in scores
        assert scores["BMI"]["value"] == 28.5  # stated takes precedence

    def test_bsa_computed(self, extractor):
        result = extractor.extract_all("Height: 180 cm, Weight: 80 kg")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "BSA" in scores
        expected = round(math.sqrt((180 * 80) / 3600), 2)
        assert scores["BSA"]["value"] == expected

    def test_map_computed(self, extractor):
        result = extractor.extract_all("BP 120/80")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "MAP" in scores
        assert scores["MAP"]["value"] == pytest.approx(93.3, abs=0.1)

    def test_pulse_pressure_computed(self, extractor):
        result = extractor.extract_all("BP 160/60")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "Pulse Pressure" in scores
        assert scores["Pulse Pressure"]["value"] == 100

    def test_egfr_ckd_epi_2021_computed(self, extractor):
        result = extractor.extract_all("72 year old male\nCreatinine: 128 µmol/L")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "eGFR (CKD-EPI 2021)" in scores
        # CKD-EPI 2021 for male, age 72, Scr 128 µmol/L (1.448 mg/dL)
        assert scores["eGFR (CKD-EPI 2021)"]["value"] > 0

    def test_qtc_bazett_computed(self, extractor):
        result = extractor.extract_all("HR 75 bpm\nQT: 400 ms")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "QTc (Bazett)" in scores
        # QTc = 400 / sqrt(60/75) = 400 / sqrt(0.8) = 400 / 0.894 ≈ 447
        assert 440 <= scores["QTc (Bazett)"]["value"] <= 455

    def test_nyha_class_extracted(self, extractor):
        result = extractor.extract_all("NYHA class III")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "NYHA Functional Class" in scores
        assert scores["NYHA Functional Class"]["value"] == "III"

    def test_nyha_numeric_extracted(self, extractor):
        result = extractor.extract_all("NYHA class 2")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "NYHA Functional Class" in scores
        assert scores["NYHA Functional Class"]["value"] == "II"

    def test_ahi_extracted(self, extractor):
        result = extractor.extract_all("AHI: 32")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "AHI" in scores
        assert scores["AHI"]["value"] == 32.0
        assert "Severe" in scores["AHI"]["interpretation"]

    def test_lvef_extracted(self, extractor):
        result = extractor.extract_all("LVEF 35%")
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "LVEF" in scores
        assert scores["LVEF"]["value"] == 35
        assert "HFrEF" in scores["LVEF"]["interpretation"]

    def test_cha2ds2vasc_computed_for_af(self, extractor):
        text = "72 year old male with atrial fibrillation, hypertension, diabetes, previous MI"
        result = extractor.extract_all(text)
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "CHA₂DS₂-VASc" in scores
        assert scores["CHA₂DS₂-VASc"]["value"] >= 3  # Age 65-74 + HTN + DM + Vasc

    def test_cha2ds2vasc_not_computed_without_af(self, extractor):
        text = "72 year old male with hypertension"
        result = extractor.extract_all(text)
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "CHA₂DS₂-VASc" not in scores

    def test_hasbled_computed_for_af(self, extractor):
        text = "72 year old male with atrial fibrillation, on aspirin"
        result = extractor.extract_all(text)
        scores = {s["name"]: s for s in result["clinical_scores"]}
        assert "HAS-BLED" in scores

    def test_all_scores_have_references(self, extractor):
        text = """72 year old male
        Height: 180 cm, Weight: 90 kg
        BP 150/90, HR 80 bpm
        Creatinine: 110 µmol/L
        NYHA class II, LVEF 40%
        atrial fibrillation, hypertension
        QT: 420 ms"""
        result = extractor.extract_all(text)
        for score in result["clinical_scores"]:
            assert "reference" in score, f"Score {score['name']} missing reference"
            assert len(score["reference"]) > 5, f"Score {score['name']} has empty reference"


# ---------------------------------------------------------------------------
# 6. Standalone equation functions
# ---------------------------------------------------------------------------

class TestEGFREquation:
    """CKD-EPI 2021 (Inker et al., NEJM 2021)."""

    def test_normal_male(self):
        # 40yo male, Scr 1.0 mg/dL => CKD-EPI 2021 ~98
        egfr = _compute_egfr_ckd_epi_2021(1.0, 40, "Male")
        assert 90 <= egfr <= 115

    def test_normal_female(self):
        # 40yo female, Scr 0.8 mg/dL => CKD-EPI 2021 ~95
        egfr = _compute_egfr_ckd_epi_2021(0.8, 40, "Female")
        assert 85 <= egfr <= 120

    def test_high_creatinine_low_egfr(self):
        # 70yo male, Scr 3.0 mg/dL => severely decreased
        egfr = _compute_egfr_ckd_epi_2021(3.0, 70, "Male")
        assert egfr < 30

    def test_age_effect(self):
        # Same creatinine, older = lower eGFR
        young = _compute_egfr_ckd_epi_2021(1.0, 30, "Male")
        old = _compute_egfr_ckd_epi_2021(1.0, 80, "Male")
        assert young > old


class TestInterpretationFunctions:
    def test_bmi_underweight(self):
        assert "Underweight" in _interpret_bmi(17.0)

    def test_bmi_normal(self):
        assert "Normal" in _interpret_bmi(22.0)

    def test_bmi_overweight(self):
        assert "Overweight" in _interpret_bmi(27.0)

    def test_bmi_obese_i(self):
        assert "Obese Class I" in _interpret_bmi(32.0)

    def test_bmi_obese_iii(self):
        assert "Obese Class III" in _interpret_bmi(42.0)

    def test_map_critical(self):
        assert "inadequate" in _interpret_map(55).lower()

    def test_map_normal(self):
        assert "Normal" in _interpret_map(85)

    def test_map_elevated(self):
        assert "hypertension" in _interpret_map(110).lower()

    def test_pp_narrow(self):
        assert "narrow" in _interpret_pp(20).lower()

    def test_pp_normal(self):
        assert "Normal" in _interpret_pp(50)

    def test_pp_widened(self):
        assert "Widened" in _interpret_pp(70)

    def test_egfr_g1(self):
        assert "G1" in _interpret_egfr(95)

    def test_egfr_g3a(self):
        assert "G3a" in _interpret_egfr(50)

    def test_egfr_g5(self):
        assert "G5" in _interpret_egfr(10)

    def test_qtc_normal_male(self):
        assert "Normal" in _interpret_qtc(430, "Male")

    def test_qtc_prolonged_male(self):
        assert "Prolonged" in _interpret_qtc(460, "Male")

    def test_qtc_high_risk(self):
        assert "Torsades" in _interpret_qtc(510, "Male")

    def test_qtc_short(self):
        assert "short" in _interpret_qtc(340, "Male").lower()

    def test_ahi_normal(self):
        assert "Normal" in _interpret_ahi(3)

    def test_ahi_mild(self):
        assert "Mild" in _interpret_ahi(10)

    def test_ahi_moderate(self):
        assert "Moderate" in _interpret_ahi(20)

    def test_ahi_severe(self):
        assert "Severe" in _interpret_ahi(35)

    def test_lvef_normal(self):
        assert "Normal" in _interpret_lvef(55)

    def test_lvef_mildly_reduced(self):
        assert "mildly" in _interpret_lvef(45).lower()

    def test_lvef_reduced(self):
        assert "HFrEF" in _interpret_lvef(35)

    def test_lvef_severely_reduced(self):
        assert "Severely" in _interpret_lvef(20)


# ---------------------------------------------------------------------------
# 7. CHA2DS2-VASc score
# ---------------------------------------------------------------------------

class TestCHA2DS2VASc:
    def test_zero_score_young_male_no_risk(self):
        result = _compute_cha2ds2vasc("", 40, "Male")
        assert result["score"] == 0

    def test_age_75_scores_2(self):
        result = _compute_cha2ds2vasc("", 76, "Male")
        assert result["components"]["Age ≥75"] == 2
        assert result["score"] >= 2

    def test_age_65_74_scores_1(self):
        result = _compute_cha2ds2vasc("", 68, "Male")
        assert result["components"]["Age 65-74"] == 1

    def test_female_scores_1(self):
        result = _compute_cha2ds2vasc("", 40, "Female")
        assert result["components"]["Female sex"] == 1

    def test_hypertension_scores_1(self):
        result = _compute_cha2ds2vasc("patient has hypertension", 40, "Male")
        assert result["components"]["Hypertension"] == 1

    def test_diabetes_scores_1(self):
        result = _compute_cha2ds2vasc("type 2 diabetes", 40, "Male")
        assert result["components"]["Diabetes"] == 1

    def test_stroke_scores_2(self):
        result = _compute_cha2ds2vasc("previous stroke", 40, "Male")
        assert result["components"]["Stroke/TIA"] == 2

    def test_vascular_disease_scores_1(self):
        result = _compute_cha2ds2vasc("previous MI and peripheral vascular disease", 40, "Male")
        assert result["components"]["Vascular disease"] == 1

    def test_chf_scores_1(self):
        result = _compute_cha2ds2vasc("heart failure with reduced ejection fraction", 40, "Male")
        assert result["components"]["CHF/LV dysfunction"] == 1

    def test_max_score(self):
        text = "heart failure, hypertension, diabetes, previous stroke, previous MI"
        result = _compute_cha2ds2vasc(text, 76, "Female")
        assert result["score"] == 9

    def test_high_risk_interpretation(self):
        result = _compute_cha2ds2vasc("hypertension, diabetes, stroke", 76, "Male")
        assert "anticoagulation recommended" in result["interpretation"].lower()


# ---------------------------------------------------------------------------
# 8. HAS-BLED score
# ---------------------------------------------------------------------------

class TestHASBLED:
    def test_zero_score_young_no_risk(self):
        result = _compute_hasbled("", 40, {})
        assert result["score"] == 0

    def test_elderly_scores_1(self):
        result = _compute_hasbled("", 70, {})
        assert result["components"]["Elderly (>65)"] == 1

    def test_aspirin_scores_1(self):
        result = _compute_hasbled("on aspirin", 40, {})
        assert result["components"]["Drugs (antiplatelet/NSAID)"] == 1

    def test_stroke_history_scores_1(self):
        result = _compute_hasbled("previous stroke", 40, {})
        assert result["components"]["Stroke history"] == 1

    def test_renal_impairment(self):
        result = _compute_hasbled("", 40, {"creatinine": 250})
        assert result["components"]["Abnormal renal function"] == 1

    def test_high_risk_interpretation(self):
        result = _compute_hasbled("previous stroke, bleeding history, on aspirin, alcohol", 70, {"creatinine": 250})
        assert result["score"] >= 3
        assert "high" in result["interpretation"].lower()


# ---------------------------------------------------------------------------
# 9. Full integration (extract_all)
# ---------------------------------------------------------------------------

class TestExtractAll:
    def test_full_referral_letter(self, extractor):
        text = """
        Referral Letter — Dr Smith to Cardiology
        Patient: 72 year old male
        Height: 175 cm, Weight: 92 kg
        BP 158/94 mmHg, HR 88 bpm, SpO2 96%

        Blood Tests:
        NT-proBNP: 1450
        Creatinine: 128 µmol/L
        Sodium: 138
        Potassium: 4.8
        Haemoglobin: 128 g/L

        Medications: bisoprolol 5mg OD, ramipril 10mg OD, furosemide 40mg BD

        Diagnosis: atrial fibrillation, hypertension, heart failure
        NYHA class III, LVEF 35%
        """
        result = extractor.extract_all(text)

        # Demographics
        assert result["patient_demographics"]["age"] == 72
        assert result["patient_demographics"]["sex"] == "Male"
        assert result["patient_demographics"]["height_cm"] == 175.0
        assert result["patient_demographics"]["weight_kg"] == 92.0

        # Vitals
        assert result["vitals"]["systolic_bp"] == 158
        assert result["vitals"]["heart_rate"] == 88

        # Blood tests present
        bt_keys = {b["key"] for b in result["blood_tests"]}
        assert "nt_probnp" in bt_keys
        assert "creatinine" in bt_keys
        assert "sodium" in bt_keys

        # Medications present
        med_names = {m["name"].lower() for m in result["medications"]}
        assert "bisoprolol" in med_names
        assert "ramipril" in med_names
        assert "furosemide" in med_names

        # Scores present
        score_names = {s["name"] for s in result["clinical_scores"]}
        assert "BMI" in score_names
        assert "MAP" in score_names
        assert "LVEF" in score_names
        assert "NYHA Functional Class" in score_names
        assert "CHA₂DS₂-VASc" in score_names
        assert "HAS-BLED" in score_names

    def test_empty_text_returns_structure(self, extractor):
        result = extractor.extract_all("")
        assert "patient_demographics" in result
        assert "vitals" in result
        assert "blood_tests" in result
        assert "medications" in result
        assert "clinical_scores" in result
        assert result["blood_tests"] == []
        assert result["medications"] == []
        assert result["clinical_scores"] == []

    def test_minimal_text_no_crash(self, extractor):
        result = extractor.extract_all("Patient referred for review.")
        assert result["blood_tests"] == []
        assert result["medications"] == []
