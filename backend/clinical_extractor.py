# backend/clinical_extractor.py
"""
Structured clinical data extraction from unstructured medical referral text.

Extracts:
  - Patient demographics (height, weight, BMI, age, sex)
  - Vital signs (BP, HR, SpO2, temperature, respiratory rate)
  - Blood test results with reference-range flagging
  - Medications with dose/frequency
  - Computed clinical scores (BMI, eGFR, MAP, pulse pressure, BSA, QTc,
    CHA2DS2-VASc, HAS-BLED, NYHA class)

References:
  - eGFR: CKD-EPI 2021 (Inker et al., NEJM 2021;385:1737-1749)
  - BMI: WHO Technical Report Series 894 (2000)
  - CHA2DS2-VASc: Lip et al., Chest 2010;137:263-272
  - HAS-BLED: Pisters et al., Chest 2010;138:1093-1100
  - MAP: Guyton & Hall, Textbook of Medical Physiology
  - BSA: Mosteller, NEJM 1987;317:1098
  - QTc: Bazett, Heart 1920;7:353-370
  - NYHA: Criteria Committee of the NYHA, 9th ed, 1994
  - AHI: AASM Manual v2.0 (Berry et al., 2012)
  - Blood test ranges: NHS Pathology Harmony, NICE guidelines, ESC/AHA
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 1. BLOOD TEST REFERENCE RANGES
# ---------------------------------------------------------------------------
# Each entry: (display_name, unit, low_normal, high_normal, critical_low, critical_high, category)
# None means "no threshold defined".
# Sources: NHS Pathology Harmony, Gloucestershire Hospitals NHS, NICE, ESC

BLOOD_TEST_PATTERNS: Dict[str, Dict[str, Any]] = {
    # --- Cardiac biomarkers ---
    "hs_troponin_t": {
        "name": "High-Sensitivity Troponin T", "abbr": "hs-cTnT", "unit": "ng/L",
        "low": None, "high": 14, "crit_low": None, "crit_high": 70,
        "category": "cardiac_biomarkers",
        "patterns": [
            r"(?:hs[- ]?)?troponin[\s-]?T[\s:]*[<>]?\s*(\d+\.?\d*)",
            r"hs[- ]?cTnT[\s:]*[<>]?\s*(\d+\.?\d*)",
        ],
    },
    "hs_troponin_i": {
        "name": "High-Sensitivity Troponin I", "abbr": "hs-cTnI", "unit": "ng/L",
        "low": None, "high": 26, "crit_low": None, "crit_high": 260,
        "category": "cardiac_biomarkers",
        "patterns": [
            r"(?:hs[- ]?)?troponin[\s-]?I[\s:]*[<>]?\s*(\d+\.?\d*)",
            r"hs[- ]?cTnI[\s:]*[<>]?\s*(\d+\.?\d*)",
        ],
    },
    "troponin": {
        "name": "Troponin", "abbr": "Trop", "unit": "ng/L",
        "low": None, "high": 14, "crit_low": None, "crit_high": 70,
        "category": "cardiac_biomarkers",
        "patterns": [
            r"troponin[\s:]*[<>]?\s*(\d+\.?\d*)",
        ],
    },
    "bnp": {
        "name": "BNP", "abbr": "BNP", "unit": "pg/mL",
        "low": None, "high": 100, "crit_low": None, "crit_high": 500,
        "category": "cardiac_biomarkers",
        "patterns": [
            r"(?:^|(?<!pro))BNP[\s:]*[<>]?\s*(\d+\.?\d*)",
        ],
    },
    "nt_probnp": {
        "name": "NT-proBNP", "abbr": "NT-proBNP", "unit": "pg/mL",
        "low": None, "high": 125, "crit_low": None, "crit_high": 2000,
        "category": "cardiac_biomarkers",
        "patterns": [
            r"NT[- ]?pro[- ]?BNP[\s:]*[<>]?\s*(\d+\.?\d*)",
        ],
    },
    "ck_mb": {
        "name": "CK-MB", "abbr": "CK-MB", "unit": "ng/mL",
        "low": None, "high": 5, "crit_low": None, "crit_high": None,
        "category": "cardiac_biomarkers",
        "patterns": [r"CK[- ]?MB[\s:]*[<>]?\s*(\d+\.?\d*)"],
    },
    "d_dimer": {
        "name": "D-dimer", "abbr": "D-dimer", "unit": "ng/mL FEU",
        "low": None, "high": 500, "crit_low": None, "crit_high": 4000,
        "category": "cardiac_biomarkers",
        "patterns": [r"[Dd][- ]?dimer[\s:]*[<>]?\s*(\d+\.?\d*)"],
    },
    "crp": {
        "name": "C-Reactive Protein", "abbr": "CRP", "unit": "mg/L",
        "low": None, "high": 5, "crit_low": None, "crit_high": 100,
        "category": "cardiac_biomarkers",
        "patterns": [
            r"(?:hs[- ]?)?CRP[\s:]*[<>]?\s*(\d+\.?\d*)",
            r"C[- ]?reactive\s+protein[\s:]*[<>]?\s*(\d+\.?\d*)",
        ],
    },
    # --- Lipid panel ---
    "total_cholesterol": {
        "name": "Total Cholesterol", "abbr": "TC", "unit": "mmol/L",
        "low": None, "high": 5.0, "crit_low": None, "crit_high": 9.0,
        "category": "lipids",
        "patterns": [
            r"total\s+cholesterol[\s:]*(\d+\.?\d*)",
            r"TC[\s:]+(\d+\.?\d*)\s*(?:mmol|$)",
        ],
    },
    "ldl": {
        "name": "LDL Cholesterol", "abbr": "LDL", "unit": "mmol/L",
        "low": None, "high": 3.0, "crit_low": None, "crit_high": 4.9,
        "category": "lipids",
        "patterns": [r"LDL(?:[- ]?C)?[\s:]*(\d+\.?\d*)"],
    },
    "hdl": {
        "name": "HDL Cholesterol", "abbr": "HDL", "unit": "mmol/L",
        "low": 1.0, "high": None, "crit_low": None, "crit_high": None,
        "category": "lipids",
        "patterns": [r"HDL(?:[- ]?C)?[\s:]*(\d+\.?\d*)"],
    },
    "triglycerides": {
        "name": "Triglycerides", "abbr": "TG", "unit": "mmol/L",
        "low": None, "high": 1.7, "crit_low": None, "crit_high": 10.0,
        "category": "lipids",
        "patterns": [
            r"[Tt]riglycerides?[\s:]*(\d+\.?\d*)",
            r"TG[\s:]+(\d+\.?\d*)\s*(?:mmol|$)",
        ],
    },
    "non_hdl": {
        "name": "Non-HDL Cholesterol", "abbr": "Non-HDL", "unit": "mmol/L",
        "low": None, "high": 4.0, "crit_low": None, "crit_high": 7.5,
        "category": "lipids",
        "patterns": [r"[Nn]on[- ]?HDL(?:[- ]?C)?[\s:]*(\d+\.?\d*)"],
    },
    # --- Metabolic ---
    "hba1c_mmol": {
        "name": "HbA1c", "abbr": "HbA1c", "unit": "mmol/mol",
        "low": None, "high": 42, "crit_low": None, "crit_high": 130,
        "category": "metabolic",
        "patterns": [r"HbA1c[\s:]*(\d+\.?\d*)\s*mmol"],
    },
    "hba1c_pct": {
        "name": "HbA1c", "abbr": "HbA1c", "unit": "%",
        "low": None, "high": 6.0, "crit_low": None, "crit_high": 14.0,
        "category": "metabolic",
        "patterns": [r"HbA1c[\s:]*(\d+\.?\d*)\s*%"],
    },
    "fasting_glucose": {
        "name": "Fasting Glucose", "abbr": "FPG", "unit": "mmol/L",
        "low": 4.0, "high": 5.4, "crit_low": 2.2, "crit_high": 25.0,
        "category": "metabolic",
        "patterns": [
            r"fasting\s+(?:plasma\s+)?glucose[\s:]*(\d+\.?\d*)",
            r"FPG[\s:]+(\d+\.?\d*)",
        ],
    },
    "creatinine": {
        "name": "Creatinine", "abbr": "Cr", "unit": "µmol/L",
        "low": 45, "high": 110, "crit_low": None, "crit_high": 500,
        "category": "metabolic",
        "patterns": [
            r"[Cc]reatinine[\s:]*(\d+\.?\d*)\s*(?:µ|u|micro)?mol",
            r"[Cc]reatinine[\s:]*(\d+\.?\d*)\s*(?!mg)",
        ],
    },
    "creatinine_mg": {
        "name": "Creatinine", "abbr": "Cr", "unit": "mg/dL",
        "low": 0.5, "high": 1.2, "crit_low": None, "crit_high": 5.7,
        "category": "metabolic",
        "patterns": [r"[Cc]reatinine[\s:]*(\d+\.?\d*)\s*mg"],
    },
    "urea": {
        "name": "Urea", "abbr": "Urea", "unit": "mmol/L",
        "low": 2.5, "high": 7.8, "crit_low": None, "crit_high": 35.0,
        "category": "metabolic",
        "patterns": [
            r"[Uu]rea[\s:]*(\d+\.?\d*)",
            r"BUN[\s:]*(\d+\.?\d*)",
        ],
    },
    "egfr": {
        "name": "eGFR", "abbr": "eGFR", "unit": "mL/min/1.73m²",
        "low": 60, "high": None, "crit_low": 15, "crit_high": None,
        "category": "metabolic",
        "patterns": [r"eGFR[\s:]*[<>]?\s*(\d+\.?\d*)"],
    },
    "sodium": {
        "name": "Sodium", "abbr": "Na⁺", "unit": "mmol/L",
        "low": 135, "high": 145, "crit_low": 120, "crit_high": 160,
        "category": "metabolic",
        "patterns": [
            r"[Ss]odium[\s:]*(\d+\.?\d*)",
            r"\bNa\+?[\s:]+(\d{3})",
        ],
    },
    "potassium": {
        "name": "Potassium", "abbr": "K⁺", "unit": "mmol/L",
        "low": 3.5, "high": 5.0, "crit_low": 2.5, "crit_high": 6.5,
        "category": "metabolic",
        "patterns": [
            r"[Pp]otassium[\s:]*(\d+\.?\d*)",
            r"\bK\+?[\s:]+(\d+\.?\d*)",
        ],
    },
    # --- Haematology ---
    "haemoglobin": {
        "name": "Haemoglobin", "abbr": "Hb", "unit": "g/L",
        "low": 115, "high": 180, "crit_low": 70, "crit_high": 200,
        "category": "haematology",
        "patterns": [
            r"(?:H(?:ae)?moglobin|Hb)[\s:]*(\d+\.?\d*)\s*g/L",
            r"(?:H(?:ae)?moglobin|Hb)[\s:]*(\d+\.?\d*)\s*(?!g/d)",
        ],
    },
    "wcc": {
        "name": "White Cell Count", "abbr": "WCC", "unit": "×10⁹/L",
        "low": 3.6, "high": 11.0, "crit_low": 1.0, "crit_high": 30.0,
        "category": "haematology",
        "patterns": [
            r"(?:WCC|WBC|[Ww]hite\s+(?:cell|blood)\s+count)[\s:]*(\d+\.?\d*)",
        ],
    },
    "platelets": {
        "name": "Platelets", "abbr": "Plt", "unit": "×10⁹/L",
        "low": 140, "high": 400, "crit_low": 20, "crit_high": 1000,
        "category": "haematology",
        "patterns": [
            r"[Pp]latelets?[\s:]*(\d+\.?\d*)",
            r"Plt[\s:]+(\d+\.?\d*)",
        ],
    },
    "inr": {
        "name": "INR", "abbr": "INR", "unit": "",
        "low": 0.8, "high": 1.2, "crit_low": None, "crit_high": 5.0,
        "category": "haematology",
        "patterns": [r"INR[\s:]*(\d+\.?\d*)"],
    },
    # --- Liver ---
    "alt": {
        "name": "ALT", "abbr": "ALT", "unit": "IU/L",
        "low": None, "high": 40, "crit_low": None, "crit_high": 1000,
        "category": "liver",
        "patterns": [r"ALT[\s:]*(\d+\.?\d*)"],
    },
    "ast": {
        "name": "AST", "abbr": "AST", "unit": "IU/L",
        "low": None, "high": 40, "crit_low": None, "crit_high": 1000,
        "category": "liver",
        "patterns": [r"AST[\s:]*(\d+\.?\d*)"],
    },
    "alp": {
        "name": "ALP", "abbr": "ALP", "unit": "IU/L",
        "low": 30, "high": 130, "crit_low": None, "crit_high": None,
        "category": "liver",
        "patterns": [
            r"ALP[\s:]*(\d+\.?\d*)",
            r"[Aa]lkaline\s+[Pp]hosphatase[\s:]*(\d+\.?\d*)",
        ],
    },
    "bilirubin": {
        "name": "Bilirubin", "abbr": "Bili", "unit": "µmol/L",
        "low": None, "high": 21, "crit_low": None, "crit_high": 200,
        "category": "liver",
        "patterns": [r"[Bb]ilirubin[\s:]*(\d+\.?\d*)"],
    },
    "albumin": {
        "name": "Albumin", "abbr": "Alb", "unit": "g/L",
        "low": 35, "high": 50, "crit_low": 20, "crit_high": None,
        "category": "liver",
        "patterns": [r"[Aa]lbumin[\s:]*(\d+\.?\d*)"],
    },
    # --- Thyroid ---
    "tsh": {
        "name": "TSH", "abbr": "TSH", "unit": "mU/L",
        "low": 0.4, "high": 4.0, "crit_low": 0.1, "crit_high": 10.0,
        "category": "thyroid",
        "patterns": [r"TSH[\s:]*(\d+\.?\d*)"],
    },
    # --- Other CV-relevant ---
    "lactate": {
        "name": "Lactate", "abbr": "Lac", "unit": "mmol/L",
        "low": None, "high": 2.0, "crit_low": None, "crit_high": 4.0,
        "category": "other",
        "patterns": [r"[Ll]actate[\s:]*(\d+\.?\d*)"],
    },
    "magnesium": {
        "name": "Magnesium", "abbr": "Mg²⁺", "unit": "mmol/L",
        "low": 0.7, "high": 1.0, "crit_low": 0.5, "crit_high": 2.0,
        "category": "other",
        "patterns": [r"[Mm]agnesium[\s:]*(\d+\.?\d*)"],
    },
    "calcium": {
        "name": "Corrected Calcium", "abbr": "Ca²⁺", "unit": "mmol/L",
        "low": 2.20, "high": 2.60, "crit_low": 1.80, "crit_high": 3.50,
        "category": "other",
        "patterns": [
            r"(?:[Cc]orrected\s+)?[Cc]alcium[\s:]*(\d+\.?\d*)",
        ],
    },
    "ferritin": {
        "name": "Ferritin", "abbr": "Ferritin", "unit": "µg/L",
        "low": 11, "high": 340, "crit_low": None, "crit_high": 1000,
        "category": "other",
        "patterns": [r"[Ff]erritin[\s:]*(\d+\.?\d*)"],
    },
}


# ---------------------------------------------------------------------------
# 2. MEDICATION DICTIONARIES
# ---------------------------------------------------------------------------
# Organised by BNF class.  Generic names + common brand names + old UK names.
# Sources: BNF online, NICE, AHA/ACC HF guideline 2022.

_MEDICATION_CLASSES: Dict[str, List[str]] = {
    "Antiplatelet": [
        "aspirin", "clopidogrel", "plavix", "ticagrelor", "brilique",
        "prasugrel", "efient", "dipyridamole", "persantin", "cangrelor",
    ],
    "Anticoagulant": [
        "warfarin", "coumadin", "apixaban", "eliquis", "rivaroxaban",
        "xarelto", "edoxaban", "lixiana", "dabigatran", "pradaxa",
        "enoxaparin", "clexane", "dalteparin", "fragmin", "tinzaparin",
        "innohep", "heparin", "fondaparinux", "arixtra",
    ],
    "Beta-blocker": [
        "bisoprolol", "cardicor", "atenolol", "tenormin", "metoprolol",
        "betaloc", "lopresor", "nebivolol", "nebilet", "propranolol",
        "inderal", "carvedilol", "labetalol", "trandate", "sotalol",
        "sotacor", "nadolol", "celiprolol", "acebutolol",
    ],
    "ACE Inhibitor": [
        "ramipril", "tritace", "lisinopril", "zestril", "enalapril",
        "innovace", "perindopril", "coversyl", "captopril", "capoten",
        "trandolapril", "gopten", "fosinopril", "quinapril", "accupro",
        "imidapril", "tanatril",
    ],
    "ARB": [
        "losartan", "cozaar", "candesartan", "amias", "valsartan",
        "diovan", "irbesartan", "aprovel", "olmesartan", "olmetec",
        "telmisartan", "micardis", "azilsartan", "edarbi",
    ],
    "Calcium Channel Blocker": [
        "amlodipine", "istin", "nifedipine", "adalat", "felodipine",
        "plendil", "lercanidipine", "zanidip", "diltiazem", "tildiem",
        "adizem", "verapamil", "securon", "isoptin", "lacidipine",
        "nicardipine",
    ],
    "Statin": [
        "atorvastatin", "lipitor", "rosuvastatin", "crestor",
        "simvastatin", "zocor", "pravastatin", "lipostat",
        "fluvastatin", "lescol",
    ],
    "Other Lipid-Lowering": [
        "ezetimibe", "ezetrol", "fenofibrate", "lipantil",
        "alirocumab", "praluent", "evolocumab", "repatha",
        "inclisiran", "leqvio", "bempedoic acid", "nilemdo",
        "colestyramine", "questran",
    ],
    "Diuretic": [
        "furosemide", "lasix", "frusemide", "bumetanide", "burinex",
        "torasemide", "bendroflumethiazide", "bendrofluazide",
        "indapamide", "natrilix", "chlortalidone", "metolazone",
        "hydrochlorothiazide", "xipamide",
    ],
    "MRA": [
        "spironolactone", "aldactone", "eplerenone", "inspra",
        "finerenone", "kerendia",
    ],
    "Nitrate": [
        "glyceryl trinitrate", "gtn", "isosorbide mononitrate",
        "ismn", "imdur", "isotard", "isosorbide dinitrate", "isdn",
    ],
    "Antiarrhythmic": [
        "amiodarone", "cordarone", "flecainide", "tambocor",
        "dronedarone", "multaq", "propafenone", "arythmol",
        "disopyramide", "rythmodan", "adenosine", "adenocor",
        "digoxin", "lanoxin",
    ],
    "SGLT2 Inhibitor": [
        "dapagliflozin", "forxiga", "empagliflozin", "jardiance",
        "canagliflozin", "invokana", "ertugliflozin", "steglatro",
    ],
    "ARNI": [
        "sacubitril/valsartan", "sacubitril-valsartan",
        "sacubitril valsartan", "entresto",
    ],
    "Antianginal": [
        "nicorandil", "ikorel", "ranolazine", "ranexa",
        "ivabradine", "procoralan", "trimetazidine", "perhexiline",
    ],
    "Inotrope / Vasopressor": [
        "dobutamine", "dopamine", "milrinone", "primacor",
        "noradrenaline", "norepinephrine", "adrenaline", "epinephrine",
        "levosimendan", "isoprenaline",
    ],
    "Other Antihypertensive": [
        "doxazosin", "cardura", "hydralazine", "apresoline",
        "minoxidil", "loniten", "moxonidine", "physiotens",
        "methyldopa", "aldomet", "clonidine", "catapres", "aliskiren",
    ],
    "Pulmonary Hypertension": [
        "sildenafil", "revatio", "tadalafil", "adcirca",
        "bosentan", "tracleer", "ambrisentan", "volibris",
        "macitentan", "opsumit", "riociguat", "adempas",
    ],
}

# Build a flat lookup: lowercase drug -> class
_DRUG_TO_CLASS: Dict[str, str] = {}
for _cls, _drugs in _MEDICATION_CLASSES.items():
    for _d in _drugs:
        _DRUG_TO_CLASS[_d.lower()] = _cls

# Build a sorted list longest-first for regex (avoids partial matches)
_ALL_DRUG_NAMES = sorted(_DRUG_TO_CLASS.keys(), key=len, reverse=True)
_DRUG_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(d) for d in _ALL_DRUG_NAMES) + r")\b",
    re.IGNORECASE,
)

# Dose + unit pattern (captures number, optional /number, and unit)
_DOSE_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*(?:/\s*(\d+\.?\d*)\s*)?"
    r"(mg|mcg|µg|microgram(?:s)?|g|ml|mL|unit(?:s)?|IU|mmol|%)",
    re.IGNORECASE,
)

# Frequency pattern
_FREQ_PATTERN = re.compile(
    r"(?i)\b("
    r"OD|BD|TDS|QDS|PRN|nocte|mane|ON|OM|stat|daily|weekly|monthly"
    r"|once\s+(?:a\s+)?dai?ly|twice\s+(?:a\s+)?dai?ly"
    r"|once\s+a\s+day|twice\s+a\s+day"
    r"|three\s+times?\s+(?:a\s+)?dai?ly|four\s+times?\s+(?:a\s+)?dai?ly"
    r"|at\s+night|at\s+bedtime|in\s+the\s+morning"
    r"|each\s+(?:morning|night)|every\s+(?:other\s+)?(?:morning|night|day)"
    r"|every\s+\d+\s+hours?|\d+[\s-]?hourly"
    r"|as\s+(?:required|needed)|when\s+(?:required|needed)"
    r"|alternate\s+days?"
    r")\b"
)


# ---------------------------------------------------------------------------
# 3. MAIN EXTRACTOR CLASS
# ---------------------------------------------------------------------------

class ClinicalDataExtractor:
    """Extract structured clinical data from unstructured referral text."""

    def extract_all(self, text: str) -> Dict[str, Any]:
        """Run all extractors and return a unified dict."""
        demographics = self.extract_demographics(text)
        vitals = self.extract_vitals(text)
        blood_tests = self.extract_blood_tests(text)
        medications = self.extract_medications(text)

        # Compute clinical scores from extracted data
        scores = self.compute_clinical_scores(text, demographics, vitals, blood_tests)

        return {
            "patient_demographics": demographics,
            "vitals": vitals,
            "blood_tests": blood_tests,
            "medications": medications,
            "clinical_scores": scores,
        }

    # ---- Demographics ----

    def extract_demographics(self, text: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        # Age
        age_m = re.search(
            r"(?:age[d]?|(\d{1,3})\s*(?:year|yr|y/?o))[:\s]*(\d{1,3})?",
            text, re.IGNORECASE,
        )
        if age_m:
            result["age"] = int(age_m.group(2) or age_m.group(1))

        # Sex
        sex_m = re.search(
            r"\b(male|female|man|woman|gentleman|lady)\b", text, re.IGNORECASE,
        )
        if sex_m:
            val = sex_m.group(1).lower()
            result["sex"] = "Male" if val in ("male", "man", "gentleman") else "Female"

        # Height (cm or m)
        ht_m = re.search(
            r"[Hh]eight[\s:]*(\d+\.?\d*)\s*(cm|m|metres?|meters?)", text
        )
        if ht_m:
            val = float(ht_m.group(1))
            unit = ht_m.group(2).lower()
            result["height_cm"] = val if unit == "cm" else val * 100

        # Weight (kg or lbs)
        wt_m = re.search(
            r"[Ww]eight[\s:]*(\d+\.?\d*)\s*(kg|lbs?|pounds?|kilograms?|stone)", text
        )
        if wt_m:
            val = float(wt_m.group(1))
            unit = wt_m.group(2).lower()
            if unit.startswith("lb") or unit.startswith("pound"):
                result["weight_kg"] = round(val * 0.453592, 1)
            elif unit == "stone":
                result["weight_kg"] = round(val * 6.35029, 1)
            else:
                result["weight_kg"] = val

        # BMI (if explicitly stated)
        bmi_m = re.search(r"BMI[\s:]*(\d+\.?\d*)", text, re.IGNORECASE)
        if bmi_m:
            result["bmi_stated"] = float(bmi_m.group(1))

        return result

    # ---- Vital Signs ----

    def extract_vitals(self, text: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        # Blood pressure (SBP/DBP)
        bp_m = re.search(
            r"(?:BP|[Bb]lood\s+[Pp]ressure)[\s:]*(\d{2,3})\s*/\s*(\d{2,3})",
            text,
        )
        if bp_m:
            result["systolic_bp"] = int(bp_m.group(1))
            result["diastolic_bp"] = int(bp_m.group(2))

        # Heart rate
        hr_m = re.search(
            r"(?:HR|[Hh]eart\s+[Rr]ate|[Pp]ulse)[\s:]*(\d{2,3})\s*(?:bpm|/min|beats)?",
            text,
        )
        if hr_m:
            result["heart_rate"] = int(hr_m.group(1))

        # SpO2
        spo2_m = re.search(
            r"(?:SpO2|[Ss]aturations?|[Oo]xygen\s+sat(?:uration)?)[\s:]*(\d{2,3})\s*%?",
            text,
        )
        if spo2_m:
            result["spo2"] = int(spo2_m.group(1))

        # Temperature
        temp_m = re.search(
            r"(?:[Tt]emp(?:erature)?)[\s:]*(\d{2}\.?\d*)\s*°?\s*([CcFf])?",
            text,
        )
        if temp_m:
            val = float(temp_m.group(1))
            unit = (temp_m.group(2) or "C").upper()
            if unit == "F":
                val = round((val - 32) * 5 / 9, 1)
            result["temperature_c"] = val

        # Respiratory rate
        rr_m = re.search(
            r"(?:RR|[Rr]espiratory\s+[Rr]ate|resp\s+rate|resps?)[\s:]*(\d{1,2})",
            text,
        )
        if rr_m:
            result["respiratory_rate"] = int(rr_m.group(1))

        return result

    # ---- Blood Tests ----

    def extract_blood_tests(self, text: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        seen_keys: set = set()

        for key, spec in BLOOD_TEST_PATTERNS.items():
            for pat in spec["patterns"]:
                m = re.search(pat, text, re.IGNORECASE)
                if m and key not in seen_keys:
                    try:
                        value = float(m.group(1))
                    except (ValueError, IndexError):
                        continue

                    flag = self._flag_result(value, spec)
                    entry = {
                        "key": key,
                        "name": spec["name"],
                        "abbr": spec["abbr"],
                        "value": value,
                        "unit": spec["unit"],
                        "category": spec["category"],
                        "flag": flag,
                        "reference_range": self._format_range(spec),
                    }
                    results.append(entry)
                    seen_keys.add(key)
                    break  # first matching pattern wins

        return results

    @staticmethod
    def _flag_result(value: float, spec: dict) -> str:
        """Flag a blood test value: normal / low / high / critical_low / critical_high."""
        crit_low = spec.get("crit_low")
        crit_high = spec.get("crit_high")
        low = spec.get("low")
        high = spec.get("high")

        if crit_low is not None and value < crit_low:
            return "critical_low"
        if crit_high is not None and value > crit_high:
            return "critical_high"
        if low is not None and value < low:
            return "low"
        if high is not None and value > high:
            return "high"
        return "normal"

    @staticmethod
    def _format_range(spec: dict) -> str:
        low = spec.get("low")
        high = spec.get("high")
        if low is not None and high is not None:
            return f"{low}–{high}"
        if low is not None:
            return f">{low}"
        if high is not None:
            return f"<{high}"
        return "—"

    # ---- Medications ----

    def extract_medications(self, text: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        seen: set = set()

        for m in _DRUG_PATTERN.finditer(text):
            drug_name = m.group(1).lower()

            # Deduplicate by canonical name (map brand -> generic handled via class)
            canonical = drug_name
            if canonical in seen:
                continue
            seen.add(canonical)

            drug_class = _DRUG_TO_CLASS.get(canonical, "Unknown")

            # Look ahead for dose and frequency (window of 60 chars after match)
            window = text[m.end(): m.end() + 60]

            dose_str = None
            dose_m = _DOSE_PATTERN.search(window)
            if dose_m:
                num = dose_m.group(1)
                num2 = dose_m.group(2)
                unit = dose_m.group(3)
                dose_str = f"{num}{'/' + num2 if num2 else ''} {unit}"

            freq_str = None
            freq_m = _FREQ_PATTERN.search(window)
            if freq_m:
                freq_str = freq_m.group(1).strip()

            results.append({
                "name": m.group(1),  # preserve original casing
                "drug_class": drug_class,
                "dose": dose_str,
                "frequency": freq_str,
            })

        return results

    # ---- Clinical Scores ----

    def compute_clinical_scores(
        self,
        text: str,
        demographics: Dict[str, Any],
        vitals: Dict[str, Any],
        blood_tests: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        scores: List[Dict[str, Any]] = []
        bt = {b["key"]: b["value"] for b in blood_tests}

        # --- BMI ---
        height_cm = demographics.get("height_cm")
        weight_kg = demographics.get("weight_kg")
        bmi = demographics.get("bmi_stated")

        if height_cm and weight_kg and not bmi:
            height_m = height_cm / 100
            bmi = round(weight_kg / (height_m ** 2), 1)

        if bmi:
            scores.append({
                "name": "BMI",
                "value": bmi,
                "unit": "kg/m²",
                "interpretation": _interpret_bmi(bmi),
                "reference": "WHO Technical Report Series 894, 2000",
            })

        # --- BSA (Mosteller) ---
        if height_cm and weight_kg:
            bsa = round(math.sqrt((height_cm * weight_kg) / 3600), 2)
            scores.append({
                "name": "BSA",
                "value": bsa,
                "unit": "m²",
                "interpretation": "Mosteller formula",
                "reference": "Mosteller, NEJM 1987;317:1098",
            })

        # --- MAP ---
        sbp = vitals.get("systolic_bp")
        dbp = vitals.get("diastolic_bp")
        if sbp and dbp:
            map_val = round(dbp + (sbp - dbp) / 3, 1)
            scores.append({
                "name": "MAP",
                "value": map_val,
                "unit": "mmHg",
                "interpretation": _interpret_map(map_val),
                "reference": "Guyton & Hall, Textbook of Medical Physiology",
            })

            # --- Pulse Pressure ---
            pp = sbp - dbp
            scores.append({
                "name": "Pulse Pressure",
                "value": pp,
                "unit": "mmHg",
                "interpretation": _interpret_pp(pp),
                "reference": "Franklin et al., Circulation 1999;100:354-360",
            })

        # --- eGFR (CKD-EPI 2021) ---
        age = demographics.get("age")
        sex = demographics.get("sex")
        cr_umol = bt.get("creatinine")
        cr_mg = bt.get("creatinine_mg")

        if age and sex and (cr_umol or cr_mg):
            scr_mg = cr_mg if cr_mg else round(cr_umol / 88.4, 3)
            egfr = _compute_egfr_ckd_epi_2021(scr_mg, age, sex)
            if egfr:
                scores.append({
                    "name": "eGFR (CKD-EPI 2021)",
                    "value": egfr,
                    "unit": "mL/min/1.73m²",
                    "interpretation": _interpret_egfr(egfr),
                    "reference": "Inker et al., NEJM 2021;385:1737-1749",
                })

        # --- QTc (Bazett) ---
        hr = vitals.get("heart_rate")
        qt_m = re.search(r"QT[\s:]*(\d{3,4})\s*(?:ms)?", text, re.IGNORECASE)
        if qt_m and hr and hr > 0:
            qt_ms = int(qt_m.group(1))
            rr_sec = 60.0 / hr
            qtc = round(qt_ms / math.sqrt(rr_sec))
            scores.append({
                "name": "QTc (Bazett)",
                "value": qtc,
                "unit": "ms",
                "interpretation": _interpret_qtc(qtc, sex),
                "reference": "Bazett, Heart 1920;7:353-370",
            })

        # --- NYHA class (extract from text) ---
        nyha_m = re.search(
            r"NYHA\s+(?:class\s+|functional\s+class\s+)?(I{1,3}V?|[1-4])",
            text, re.IGNORECASE,
        )
        if nyha_m:
            raw = nyha_m.group(1).upper()
            nyha_map = {"1": "I", "2": "II", "3": "III", "4": "IV"}
            nyha_class = nyha_map.get(raw, raw)
            scores.append({
                "name": "NYHA Functional Class",
                "value": nyha_class,
                "unit": "",
                "interpretation": _NYHA_DESCRIPTIONS.get(nyha_class, ""),
                "reference": "NYHA Criteria Committee, 9th ed, 1994",
            })

        # --- AHI (if reported) ---
        ahi_m = re.search(r"AHI[\s:]*(\d+\.?\d*)", text, re.IGNORECASE)
        if ahi_m:
            ahi = float(ahi_m.group(1))
            scores.append({
                "name": "AHI",
                "value": ahi,
                "unit": "events/hr",
                "interpretation": _interpret_ahi(ahi),
                "reference": "AASM Manual v2.0, Berry et al., 2012",
            })

        # --- CHA₂DS₂-VASc (if AF mentioned and enough data) ---
        has_af = bool(re.search(
            r"\b(atrial\s+fibrillation|AF|a\.?\s*fib)\b", text, re.IGNORECASE
        ))
        if has_af and age and sex:
            cha2ds2 = _compute_cha2ds2vasc(text, age, sex)
            scores.append({
                "name": "CHA₂DS₂-VASc",
                "value": cha2ds2["score"],
                "unit": "points",
                "interpretation": cha2ds2["interpretation"],
                "components": cha2ds2["components"],
                "reference": "Lip et al., Chest 2010;137:263-272",
            })

        # --- HAS-BLED (if AF and anticoagulation context) ---
        if has_af and age:
            hasbled = _compute_hasbled(text, age, bt)
            scores.append({
                "name": "HAS-BLED",
                "value": hasbled["score"],
                "unit": "points",
                "interpretation": hasbled["interpretation"],
                "components": hasbled["components"],
                "reference": "Pisters et al., Chest 2010;138:1093-1100",
            })

        # --- LVEF (extract from text) ---
        ef_m = re.search(
            r"(?:LVEF|[Ee]jection\s+[Ff]raction|EF)[\s:]*(?:of\s+)?(\d{1,2})[\s]*%?",
            text,
        )
        if ef_m:
            ef = int(ef_m.group(1))
            scores.append({
                "name": "LVEF",
                "value": ef,
                "unit": "%",
                "interpretation": _interpret_lvef(ef),
                "reference": "ESC 2021 HF Guidelines",
            })

        return scores


# ---------------------------------------------------------------------------
# 4. INTERPRETATION HELPERS
# ---------------------------------------------------------------------------

_NYHA_DESCRIPTIONS = {
    "I": "No limitation of physical activity.",
    "II": "Slight limitation; ordinary activity causes fatigue/dyspnoea.",
    "III": "Marked limitation; less than ordinary activity causes symptoms.",
    "IV": "Unable to carry on any physical activity without discomfort; symptoms at rest.",
}


def _interpret_bmi(bmi: float) -> str:
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25.0:
        return "Normal weight"
    if bmi < 30.0:
        return "Overweight"
    if bmi < 35.0:
        return "Obese Class I"
    if bmi < 40.0:
        return "Obese Class II"
    return "Obese Class III"


def _interpret_map(v: float) -> str:
    if v < 60:
        return "Critical — inadequate organ perfusion"
    if v < 70:
        return "Low — minimum perfusion threshold"
    if v <= 100:
        return "Normal"
    return "Elevated — possible hypertension"


def _interpret_pp(v: int) -> str:
    if v < 25:
        return "Critically narrow — consider low cardiac output"
    if v < 40:
        return "Narrow"
    if v <= 60:
        return "Normal"
    return "Widened — associated with increased CV risk"


def _interpret_egfr(v: int) -> str:
    if v >= 90:
        return "G1 — Normal or high"
    if v >= 60:
        return "G2 — Mildly decreased"
    if v >= 45:
        return "G3a — Mildly to moderately decreased"
    if v >= 30:
        return "G3b — Moderately to severely decreased"
    if v >= 15:
        return "G4 — Severely decreased"
    return "G5 — Kidney failure"


def _interpret_qtc(v: int, sex: Optional[str]) -> str:
    is_female = sex and sex.lower() == "female"
    threshold = 470 if is_female else 450
    if v > 500:
        return "Prolonged — high risk for Torsades de Pointes"
    if v > threshold:
        return "Prolonged"
    if v < 350:
        return "Short QT — possible short QT syndrome"
    return "Normal"


def _interpret_ahi(v: float) -> str:
    if v < 5:
        return "Normal"
    if v < 15:
        return "Mild OSA"
    if v < 30:
        return "Moderate OSA"
    return "Severe OSA"


def _interpret_lvef(v: int) -> str:
    if v >= 50:
        return "Normal / HFpEF"
    if v >= 41:
        return "Mildly reduced / HFmrEF"
    if v >= 30:
        return "Reduced / HFrEF"
    return "Severely reduced / HFrEF"


# ---------------------------------------------------------------------------
# 5. CLINICAL SCORE COMPUTATIONS
# ---------------------------------------------------------------------------

def _compute_egfr_ckd_epi_2021(scr_mg: float, age: int, sex: str) -> Optional[int]:
    """CKD-EPI 2021 race-free creatinine equation.

    Reference: Inker et al., NEJM 2021;385:1737-1749.
    """
    is_female = sex.lower() == "female"
    kappa = 0.7 if is_female else 0.9
    alpha = -0.241 if is_female else -0.302
    sex_mult = 1.012 if is_female else 1.0

    min_ratio = min(scr_mg / kappa, 1.0)
    max_ratio = max(scr_mg / kappa, 1.0)

    egfr = 142 * (min_ratio ** alpha) * (max_ratio ** -1.200) * (0.9938 ** age) * sex_mult
    return round(egfr)


def _compute_cha2ds2vasc(text: str, age: int, sex: str) -> Dict[str, Any]:
    """CHA₂DS₂-VASc score for AF stroke risk.

    Reference: Lip et al., Chest 2010;137:263-272.
    """
    t = text.lower()
    components = {}
    score = 0

    # C — CHF / LV dysfunction
    if any(p in t for p in ["heart failure", "lvef", "ef <", "lv dysfunction",
                             "reduced ejection", "hfref", "hfpef", "cardiomyopathy"]):
        components["CHF/LV dysfunction"] = 1
        score += 1
    else:
        components["CHF/LV dysfunction"] = 0

    # H — Hypertension
    if any(p in t for p in ["hypertension", "hypertensive", "high blood pressure",
                             "bp " + r"\d{3}"]):
        components["Hypertension"] = 1
        score += 1
    else:
        components["Hypertension"] = 0

    # A2 — Age >= 75
    if age >= 75:
        components["Age ≥75"] = 2
        score += 2
    else:
        components["Age ≥75"] = 0

    # D — Diabetes
    if any(p in t for p in ["diabetes", "diabetic", "hba1c", "type 1", "type 2",
                             "insulin", "metformin"]):
        components["Diabetes"] = 1
        score += 1
    else:
        components["Diabetes"] = 0

    # S2 — Stroke / TIA / thromboembolism
    if any(p in t for p in ["stroke", "tia", "transient ischaemic", "transient ischemic",
                             "cerebrovascular", "thromboembolism", "cva"]):
        components["Stroke/TIA"] = 2
        score += 2
    else:
        components["Stroke/TIA"] = 0

    # V — Vascular disease
    if any(p in t for p in ["myocardial infarction", "previous mi", "peripheral vascular",
                             "peripheral arterial", "aortic plaque", "pvd", "pad"]):
        components["Vascular disease"] = 1
        score += 1
    else:
        components["Vascular disease"] = 0

    # A — Age 65-74
    if 65 <= age <= 74:
        components["Age 65-74"] = 1
        score += 1
    else:
        components["Age 65-74"] = 0

    # Sc — Female sex
    is_female = sex.lower() == "female"
    components["Female sex"] = 1 if is_female else 0
    if is_female:
        score += 1

    # Interpretation (ESC guidelines)
    if is_female:
        if score <= 1:
            interp = "Low risk — anticoagulation generally not recommended"
        elif score == 2:
            interp = "Low-moderate risk — consider anticoagulation"
        else:
            interp = "Moderate-high risk — anticoagulation recommended"
    else:
        if score == 0:
            interp = "Low risk — anticoagulation generally not recommended"
        elif score == 1:
            interp = "Low-moderate risk — consider anticoagulation"
        else:
            interp = "Moderate-high risk — anticoagulation recommended"

    return {"score": score, "interpretation": interp, "components": components}


def _compute_hasbled(text: str, age: int, bt: Dict[str, float]) -> Dict[str, Any]:
    """HAS-BLED score for bleeding risk in AF.

    Reference: Pisters et al., Chest 2010;138:1093-1100.
    """
    t = text.lower()
    components = {}
    score = 0

    # H — Hypertension (uncontrolled, SBP > 160)
    bp_m = re.search(r"(?:BP|blood\s+pressure)[\s:]*(\d{2,3})", t)
    hyp = any(p in t for p in ["hypertension", "hypertensive"])
    if bp_m and int(bp_m.group(1)) > 160:
        components["Hypertension (SBP>160)"] = 1
        score += 1
    elif hyp:
        components["Hypertension (SBP>160)"] = "?"  # flagged but unconfirmed
    else:
        components["Hypertension (SBP>160)"] = 0

    # A — Abnormal renal function
    cr = bt.get("creatinine")
    renal = 1 if (cr and cr >= 200) or "dialysis" in t or "renal transplant" in t else 0
    components["Abnormal renal function"] = renal
    score += renal

    # A — Abnormal liver function
    liver = 1 if any(p in t for p in ["cirrhosis", "chronic liver", "hepatic disease"]) else 0
    alt_val = bt.get("alt")
    if alt_val and alt_val > 120:  # >3x ULN
        liver = 1
    components["Abnormal liver function"] = liver
    score += liver

    # S — Stroke
    stroke = 1 if any(p in t for p in ["stroke", "tia", "cva", "cerebrovascular"]) else 0
    components["Stroke history"] = stroke
    score += stroke

    # B — Bleeding
    bleed = 1 if any(p in t for p in ["bleeding", "haemorrhage", "hemorrhage",
                                       "anaemia", "anemia"]) else 0
    components["Bleeding history"] = bleed
    score += bleed

    # L — Labile INR
    labile = 1 if any(p in t for p in ["labile inr", "unstable inr", "ttr <60",
                                        "ttr < 60"]) else 0
    components["Labile INR"] = labile
    score += labile

    # E — Elderly (>65)
    elderly = 1 if age > 65 else 0
    components["Elderly (>65)"] = elderly
    score += elderly

    # D — Drugs (antiplatelets / NSAIDs)
    drugs = 1 if any(p in t for p in ["aspirin", "clopidogrel", "nsaid", "ibuprofen",
                                       "naproxen", "diclofenac"]) else 0
    components["Drugs (antiplatelet/NSAID)"] = drugs
    score += drugs

    # D — Alcohol
    alcohol = 1 if any(p in t for p in ["alcohol", "units per week", "drinks per week",
                                         "ethanol"]) else 0
    components["Alcohol excess"] = alcohol
    score += alcohol

    if score >= 3:
        interp = "High bleeding risk — closer monitoring and risk-factor modification needed"
    elif score >= 2:
        interp = "Moderate bleeding risk"
    else:
        interp = "Low bleeding risk"

    return {"score": score, "interpretation": interp, "components": components}
