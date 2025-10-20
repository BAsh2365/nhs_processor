# backend/recommendation.py
from __future__ import annotations
import os, json
from typing import List, Optional, Dict

# LLM is optional
try:
    import anthropic
except Exception:
    anthropic = None


class ClinicalRecommendationEngine:
    """
    Generates AI summaries and triage recommendations for cardiovascular letters.
    Uses Anthropic Claude when ANTHROPIC_API_KEY is set; otherwise falls back to
    a conservative, heuristic recommendation and an extractive summary.
    """

    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client = None
        self._init_error = None
        if self.anthropic_api_key and anthropic:
            try:
                # If your httpx/httpcore are old, upgrade them as we discussed.
                self._client = anthropic.Anthropic(api_key=self.anthropic_api_key)
            except Exception as e:
                # Do not crash app; we’ll use fallbacks.
                self._init_error = f"Anthropic init failed: {e}"
                self._client = None

    # ---------- PUBLIC API ----------

    def summarize(self, text: str, max_words: int = 140, style: str = "exec") -> str:
        """
        Returns a concise surgeon-facing summary. Uses Claude if available; otherwise extractive fallback.
        style: "exec" | "bullets" | "concise"
        """
        t = (text or "").strip()
        if not t:
            return ""

        style_instructions = {
            "exec": (
                "Write a 2–4 line executive summary for a cardiothoracic surgeon. "
                "Include: indication/reason for referral, key symptoms with duration/severity, functional capacity, "
                "and the explicit ask. UK clinical wording, no PII."
            ),
            "bullets": (
                "Write a concise 3–5 bullet summary with bolded labels: Indication, Symptoms, Function, Request. "
                "UK clinical wording, no PII."
            ),
            "concise": (
                "Write a short surgeon-facing paragraph (5–7 lines) highlighting indication, key symptoms, "
                "functional capacity and the ask. UK clinical wording, no PII."
            ),
        }.get(style, "Write a concise, surgeon-facing summary. UK clinical wording, no PII.")

        if self._client:
            try:
                system = (
                    "You are an NHS decision-support assistant for cardiology/cardiothoracic teams. "
                    f"{style_instructions} Max {max_words} words. Do not invent facts."
                )
                msg = self._client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=400,
                    temperature=0.1,
                    system=system,
                    messages=[{"role": "user", "content": t}],
                )
                out = (msg.content[0].text or "").strip()
                if out:
                    return out
            except Exception:
                pass  # fallback below

        # Extractive fallback: first sentences up to ~max_words
        import re
        clean = " ".join(t.split())
        parts = [p.strip() for p in re.split(r'(?<=[\.\?\!])\s+', clean) if len(p.strip()) > 3]
        if not parts:
            return clean[: max_words * 6]
        out, count = [], 0
        for p in parts:
            w = len(p.split())
            if count + w > max_words:
                break
            out.append(p); count += w
        return " ".join(out) if out else clean[: max_words * 6]

    def generate_recommendation(self, text: str, context_snippets: Optional[List[Dict]] = None) -> Dict:
        """
        Returns a dict with keys:
          - recommendation_type, urgency, suggested_timeframe, red_flags, confidence_level,
            evidence_basis, reasoning
        Urgency ∈ {EMERGENCY, URGENT, ROUTINE}
        Uses Claude if available; otherwise heuristic fallback.
        """
        t = (text or "").strip()
        if not t:
            return self._fallback_recommendation(t)

        if self._client:
            try:
                schema_hint = (
                    "Return STRICT JSON with keys: recommendation_type, urgency, suggested_timeframe, "
                    "red_flags, confidence_level, evidence_basis, reasoning. "
                    "Urgency must be one of: EMERGENCY, URGENT, ROUTINE."
                )
                ctx = ""
                if context_snippets:
                    tops = []
                    for item in context_snippets[:3]:
                        meta = item.get("meta") or {}
                        src = meta.get("title") or meta.get("source") or "kb"
                        tops.append(f"[{src}] {item.get('text','')[:400]}")
                    ctx = "\n\nKB context:\n" + "\n---\n".join(tops)

                system = (
                    "You are an NHS DTAC-aware assistant for cardiology/cardiothoracic teams. "
                    "Provide conservative, guideline-aligned triage recommendations based on the letter. "
                    "Prefer NICE CG95 (chest pain), NG185 (ACS), NG208 (valve disease), and the NHS England "
                    "Adult Cardiac Surgery Service Specification. Do not invent facts."
                )
                user = f"Letter text:\n{t}\n{ctx}\n\n{schema_hint}\nReturn STRICT JSON only."
                msg = self._client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=600,
                    temperature=0.0,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                raw = (msg.content[0].text or "").strip()
                rec = json.loads(raw)
                if not isinstance(rec, dict) or not rec.get("urgency"):
                    raise ValueError("LLM returned unusable JSON")
                return rec
            except Exception:
                return self._fallback_recommendation(t)

        return self._fallback_recommendation(t)

    # ---------- FALLBACKS ----------

    def _fallback_recommendation(self, text: str) -> Dict:
        """
        Conservative, offline triage with safety bias.
        Maps common phrases to urgency/timeframe consistent with NICE CG95/NG185/NG208.
        """
        t = (text or "").lower()
        signals: List[str] = []

        def has(*phrases): return any(p in t for p in phrases)

        if has("urgent surgical referral", "urgent cardiothoracic referral"):
            signals.append("urgent surgical referral mentioned")
        if has("syncope", "presyncope", "blackout", "collapse"):
            signals.append("syncope/presyncope")
        if has("ongoing chest pain", "rest pain", "pain at rest"):
            signals.append("ongoing/rest chest pain")
        if has("stemi", "nstemi", "raised troponin", "elevated troponin", "myocardial infarction"):
            signals.append("possible ACS")
        if has("severe aortic stenosis", "critical aortic stenosis"):
            signals.append("possible severe aortic stenosis")
        if has("haemodynamic instability", "hypotension", "shock"):
            signals.append("haemodynamic concern")
        if has("infective endocarditis", "endocarditis", "vegetation"):
            signals.append("suspected endocarditis")
        if has("aortic dissection", "tearing chest pain", "mediastinal widening"):
            signals.append("suspected aortic dissection")

        urgency = "ROUTINE"
        timeframe = "Routine outpatient review and non-invasive diagnostics."

        if any(s in signals for s in ["suspected aortic dissection", "haemodynamic concern", "ongoing/rest chest pain"]):
            urgency = "EMERGENCY"
            timeframe = "Immediate escalation via local emergency protocol (ED/cardiology)."
        elif any(s in signals for s in ["possible ACS", "syncope/presyncope"]):
            urgency = "URGENT"
            timeframe = "Urgent assessment within 2 weeks, aligned to NICE ACS/chest-pain pathways."
        elif any(s in signals for s in ["urgent surgical referral mentioned", "possible severe aortic stenosis", "suspected endocarditis"]):
            urgency = "URGENT"
            timeframe = "Discuss promptly with cardiology; consider surgical team triage if confirmed."

        return {
            "recommendation_type": "CARDIOVASCULAR_TRIAGE",
            "urgency": urgency,
            "suggested_timeframe": timeframe,
            "red_flags": signals,
            "confidence_level": "cautious",
            "evidence_basis": "NICE CG95 (chest pain); NICE NG185 (ACS); NICE NG208 (valve disease); NHS England Adult Cardiac Surgery Service Specification.",
            "reasoning": "Heuristic offline triage used because model output was unavailable or invalid; signals mapped to conservative escalation."
        }

    # Public alias so callers can use either name
    def fallback_recommendation(self, text: str) -> Dict:
        return self._fallback_recommendation(text)

