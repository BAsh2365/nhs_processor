from typing import List, Dict, Tuple
import re

# NLP dependencies
import spacy

class CardiovascularRiskAssessor:
    """Evidence-informed cardiovascular risk assessment with simple NLP matching and rules.
    Aligns with NICE ACS/chest-pain and valve red-flag concepts. This module does NOT replace clinical judgement.
    """

    RED_FLAGS = [
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

    SURGICAL_INDICATORS = [
        "severe valvular disease", "aortic stenosis", "mitral regurgitation",
        "coronary artery disease", "triple vessel disease", "left main stem stenosis",
        "ventricular septal defect", "aortic aneurysm", "cardiac transplant",
        "lvef <30%", "ejection fraction <30", "refractory heart failure"
    ]

    def __init__(self) -> None:
        # Prefer medium model, gracefully fall back to small
        try:
            self.nlp = spacy.load("en_core_web_md")
            self.has_vectors = True
        except Exception:
            self.nlp = spacy.load("en_core_web_sm")
            self.has_vectors = False

        # Lower-case patterns for simple lookups
        self._rf_set = {p.lower() for p in self.RED_FLAGS}
        self._surg_set = {p.lower() for p in self.SURGICAL_INDICATORS}

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
            rf_hits = self._find_terms(text, self.RED_FLAGS)
            surg_hits = self._find_terms(text, self.SURGICAL_INDICATORS)

            score = 0.0
            score += 3.0 * len(rf_hits)     # red flags dominate
            score += 1.0 * len(surg_hits)   # surgical indicators increase urgency

            # Heuristic tightening for explicit emergency phrases
            emerg_patterns = [
                r"\b(stemi|ongoing ischemia|cardiogenic shock|vf arrest|vt storm)\b",
                r"\b(aortic dissection|type a dissection)\b"
            ]
            for pat in emerg_patterns:
                if re.search(pat, text, flags=re.I):
                    score += 5.0

            # Decide thresholds
            if score >= 5.0:
                urgency = "EMERGENCY"
            elif score >= 2.0:
                urgency = "URGENT"
            else:
                urgency = "ROUTINE"

            return urgency, sorted(set(rf_hits + surg_hits))
        except Exception as e:
            print("DEBUG_URGENCY: scoring error:", e)
            return "ROUTINE", []
