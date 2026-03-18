from typing import List, Tuple, Optional
import re

# NLP dependencies
import spacy


class CardiovascularRiskAssessor:
    """Evidence-informed cardiovascular risk assessment with simple NLP matching and rules.
    Aligns with NICE ACS/chest-pain and valve red-flag concepts. This module does NOT replace clinical judgement.
    Supports config-driven clinical terms and scoring for multi-framework operation.
    """

    # Default terms used when no config is provided (backward-compatible NHS UK)
    _DEFAULT_RED_FLAGS = [
        # Ischaemia/ACS
        "ongoing chest pain", "at rest chest pain", "ischaemic chest pain", "ischemic chest pain",
        "sweating with chest pain", "diaphoresis", "radiation to arm or jaw",
        # Haemodynamic compromise
        "hypotension", "shock", "haemodynamic instability", "hemodynamic instability",
        # Arrhythmia / syncope
        "sustained ventricular tachycardia", "vf arrest", "vt arrest", "complete heart block",
        "syncope on exertion", "collapse during exercise",
        # Aortic syndrome
        "tearing chest pain", "back migrating chest pain", "pulse deficit",
        # Acute heart failure
        "pulmonary oedema", "acute heart failure", "oxygen saturation <90%",
        # Valve red flags
        "exertional syncope", "syncope with murmur", "severe aortic stenosis"
    ]

    _DEFAULT_SURGICAL_INDICATORS = [
        "severe valvular disease", "aortic stenosis", "mitral regurgitation",
        "coronary artery disease", "triple vessel disease", "left main stem stenosis",
        "ventricular septal defect", "aortic aneurysm", "cardiac transplant",
        "lvef <30%", "ejection fraction <30", "refractory heart failure"
    ]

    _DEFAULT_EMERGENCY_PATTERNS = [
        r"\b(stemi|ongoing ischemia|cardiogenic shock|vf arrest|vt storm)\b",
        r"\b(aortic dissection|type a dissection)\b"
    ]

    def __init__(self, config: Optional[dict] = None) -> None:
        # Prefer medium model, gracefully fall back to small
        try:
            self.nlp = spacy.load("en_core_web_md")
            self.has_vectors = True
        except Exception:
            self.nlp = spacy.load("en_core_web_sm")
            self.has_vectors = False

        # Load clinical terms from config or use defaults
        if config:
            ct = config.get("clinical_terms", {})
            self.red_flags = ct.get("red_flags", self._DEFAULT_RED_FLAGS)
            self.surgical_indicators = ct.get("surgical_indicators", self._DEFAULT_SURGICAL_INDICATORS)
            self.emergency_patterns = ct.get("emergency_patterns", self._DEFAULT_EMERGENCY_PATTERNS)

            scoring = config.get("scoring", {})
            self.rf_weight = scoring.get("red_flag_weight", 3.0)
            self.surg_weight = scoring.get("surgical_indicator_weight", 1.0)
            self.emerg_weight = scoring.get("emergency_pattern_weight", 5.0)
            self.emerg_threshold = scoring.get("emergency_threshold", 5.0)
            self.urgent_threshold = scoring.get("urgent_threshold", 2.0)

            levels = config.get("urgency_levels", ["EMERGENCY", "URGENT", "ROUTINE"])
            self.level_emergency = levels[0]
            self.level_urgent = levels[1] if len(levels) > 1 else "URGENT"
            self.level_routine = levels[2] if len(levels) > 2 else "ROUTINE"
        else:
            self.red_flags = self._DEFAULT_RED_FLAGS
            self.surgical_indicators = self._DEFAULT_SURGICAL_INDICATORS
            self.emergency_patterns = self._DEFAULT_EMERGENCY_PATTERNS
            self.rf_weight = 3.0
            self.surg_weight = 1.0
            self.emerg_weight = 5.0
            self.emerg_threshold = 5.0
            self.urgent_threshold = 2.0
            self.level_emergency = "EMERGENCY"
            self.level_urgent = "URGENT"
            self.level_routine = "ROUTINE"

        # Lower-case patterns for simple lookups
        self._rf_set = {p.lower() for p in self.red_flags}
        self._surg_set = {p.lower() for p in self.surgical_indicators}

    def _find_terms(self, text: str, patterns: List[str]) -> List[str]:
        t = text.lower()
        hits = []
        for p in patterns:
            if p.lower() in t:
                hits.append(p)
        return hits

    def assess_urgency(self, text: str) -> Tuple[str, List[str]]:
        """Returns (urgency, red_flags_detected). Hard-fails safely to ROUTINE on error."""
        try:
            rf_hits = self._find_terms(text, self.red_flags)
            surg_hits = self._find_terms(text, self.surgical_indicators)

            score = 0.0
            score += self.rf_weight * len(rf_hits)
            score += self.surg_weight * len(surg_hits)

            # Heuristic tightening for explicit emergency phrases
            for pat in self.emergency_patterns:
                if re.search(pat, text, flags=re.I):
                    score += self.emerg_weight

            # Decide thresholds
            if score >= self.emerg_threshold:
                urgency = self.level_emergency
            elif score >= self.urgent_threshold:
                urgency = self.level_urgent
            else:
                urgency = self.level_routine

            return urgency, sorted(set(rf_hits + surg_hits))
        except Exception as e:
            print("DEBUG_URGENCY: scoring error:", e)
            return self.level_routine, []
