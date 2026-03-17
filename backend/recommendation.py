from __future__ import annotations
import os, json, warnings, re
from typing import List, Optional, Dict
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    pipeline,
    BartForConditionalGeneration,
    BartTokenizer
)

# Global model cache keyed by model_id — prevents redundant loading across frameworks
_model_cache: Dict[str, object] = {}


class ClinicalRecommendationEngine:
    """
    Generates AI summaries and triage recommendations for cardiovascular letters.
    Uses LOCAL medical models — compliant, no external APIs.
    Supports config-driven model selection and multi-framework prompting.
    """

    def __init__(self, use_gpu: bool = None, config: Optional[dict] = None):
        """
        Initialize local medical models.

        Args:
            use_gpu: If True, use GPU if available. If None, auto-detect.
            config: Framework configuration dict. Defaults to NHS UK behavior.
        """
        self.device = "cuda" if (use_gpu or (use_gpu is None and torch.cuda.is_available())) else "cpu"
        print(f"[ClinicalRecommendationEngine] Using device: {self.device}")

        self.config = config or {}

        # Resolve model IDs from config or use defaults
        models_cfg = self.config.get("models", {})
        self._summarizer_model_id = models_cfg.get("summarization", {}).get("model_id", "facebook/bart-large-cnn")
        self._reasoning_model_id = models_cfg.get("medical_reasoning", {}).get("model_id", "microsoft/BioGPT-Large")

        # Resolve prompts from config or use defaults
        prompts = self.config.get("prompts", {})
        self._system_context = prompts.get(
            "system_context",
            "You are an NHS clinical decision-support assistant for cardiology/cardiothoracic teams, "
            "aware of the current DTAC (Digital Technology Assessment Criteria, updated Feb 2026). "
            "Provide conservative, guideline-aligned triage recommendations based on the letter. "
            "Prefer NICE CG95 (chest pain), NG185 (ACS), NG208 (valve disease), NG106 (chronic HF, updated Sep 2025), "
            "and the NHS England Adult Cardiac Surgery Service Specification (Jul 2024). Do not invent facts. "
            "Please use Exec Style for reasoning. Make sure the summary of the letter is neat and contains the main points of the letter. "
            "Use the Knowledge base PDFs to inform your recommendations. "
            "Make sure that the output is neatly formatted and easy to read."
        )
        self._summary_suffix = prompts.get("summary_suffix", "UK clinical wording, no PII. Based on NHS guidelines")
        self._schema_hint_suffix = prompts.get(
            "schema_hint_suffix",
            "Based on NHS standards for cardiology/cardiothoracic triage. "
            "Urgency must adhere to NHS and NICE guidelines for cardiovascular and thoracic conditions. "
            "Under the NHS Constitution, if your GP refers you for a condition that's not urgent, you have the right to start treatment "
            "led by a consultant within 18 weeks from when you're referred, unless you want to wait longer or waiting longer is clinically right for you."
        )

        # Resolve urgency levels from config or use defaults
        levels = self.config.get("urgency_levels", ["EMERGENCY", "URGENT", "ROUTINE"])
        self._level_emergency = levels[0]
        self._level_urgent = levels[1] if len(levels) > 1 else "URGENT"
        self._level_routine = levels[2] if len(levels) > 2 else "ROUTINE"

        # Resolve timeframes from config
        guidelines = self.config.get("guidelines", {})
        self._timeframes = guidelines.get("timeframes", {
            "emergency": "Immediate escalation via local emergency protocol (ED/cardiology).",
            "urgent": "Urgent assessment within 2 weeks, aligned to NICE ACS/chest-pain pathways.",
            "routine": "Routine outpatient review and non-invasive diagnostics."
        })
        self._evidence_basis = guidelines.get(
            "evidence_basis_text",
            "NICE CG95 (chest pain); NICE NG185 (ACS); NICE NG208 (valve disease); NICE NG106 (chronic HF, updated Sep 2025); NHS England Adult Cardiac Surgery Service Specification (Jul 2024)."
        )

        # Models will be lazy-loaded on first use
        self._summarizer = None
        self._biogpt_model = None
        self._biogpt_tokenizer = None
        self._init_error = None

        # Pre-load summarizer (lightweight)
        try:
            self._load_summarizer()
        except Exception as e:
            self._init_error = f"Model initialization warning: {e}"
            warnings.warn(self._init_error)

    def _load_summarizer(self):
        """Load summarization model (if not already loaded)"""
        if self._summarizer is None:
            cache_key = f"summarizer:{self._summarizer_model_id}"
            if cache_key in _model_cache:
                self._summarizer = _model_cache[cache_key]
                return
            print(f"[AI] Loading summarization model: {self._summarizer_model_id}...")
            self._summarizer = pipeline(
                "summarization",
                model=self._summarizer_model_id,
                device=0 if self.device == "cuda" else -1
            )
            _model_cache[cache_key] = self._summarizer
            print(f"[AI] Summarizer loaded on {self.device}")

    def _load_biogpt(self):
        """Load medical reasoning model (lazy load - heavy model)"""
        if self._biogpt_model is None:
            cache_key = f"reasoning:{self._reasoning_model_id}"
            if cache_key in _model_cache:
                cached = _model_cache[cache_key]
                self._biogpt_tokenizer = cached["tokenizer"]
                self._biogpt_model = cached["model"]
                return
            print(f"[AI] Loading medical reasoning model: {self._reasoning_model_id} (this may take a minute)...")
            try:
                self._biogpt_tokenizer = AutoTokenizer.from_pretrained(self._reasoning_model_id)
                self._biogpt_model = AutoModelForCausalLM.from_pretrained(self._reasoning_model_id)
                self._biogpt_model.to(self.device)
                self._biogpt_model.eval()
                _model_cache[cache_key] = {"tokenizer": self._biogpt_tokenizer, "model": self._biogpt_model}
                print(f"[AI] Medical reasoning model loaded on {self.device}")
            except Exception as e:
                warnings.warn(f"Medical reasoning model loading failed: {e}. Will use rule-based fallbacks.")
                self._biogpt_model = None
                self._biogpt_tokenizer = None

    def _sanitize_output(self, text: str) -> str:
        """
        Clean model output by removing XML tags, special tokens, and formatting artifacts.
        """
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'[▁▂▃▄▅▆▇█▉▊▋▌▍▎▏]', '', text)
        text = re.sub(r'</?s>|<pad>|<unk>|<mask>', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text

    # ---------- PUBLIC API ----------

    def summarize(self, text: str, max_words: int = 140, style: str = "exec") -> str:
        """
        Returns a concise surgeon-facing summary using local models with advanced prompting.
        """
        t = (text or "").strip()
        if not t:
            return ""

        style_instructions = {
            "exec": (
                f"3-5 line executive summary for a cardiothoracic surgeon. "
                f"Include: indication/reason for referral, key symptoms with duration/severity, functional capacity, "
                f"and the explicit ask. {self._summary_suffix}"
            ),
            "bullets": (
                f"Concise 3-5 bullet summary with bolded labels: Indication, Symptoms, Function, Request. "
                f"{self._summary_suffix}."
            ),
            "concise": (
                f"Short surgeon-facing paragraph (5-7 lines) highlighting indication, key symptoms, "
                f"functional capacity and the ask. {self._summary_suffix}"
            ),
        }.get(style, f"Concise, surgeon-facing summary. {self._summary_suffix}.")

        # Try BioGPT first for medical-domain summarization
        biogpt_result = self._try_biogpt_summary(t, style_instructions, max_words)
        if biogpt_result:
            return self._sanitize_output(biogpt_result)

        # Fallback to BART summarizer
        if self._summarizer is None:
            try:
                self._load_summarizer()
            except Exception:
                return self._extractive_fallback(t, max_words)

        try:
            max_input_length = 1024
            if len(t.split()) > max_input_length:
                t = " ".join(t.split()[:max_input_length])

            max_length = int(max_words * 1.5)
            min_length = max(int(max_words * 0.5), 30)

            result = self._summarizer(
                t,
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
                truncation=True
            )

            summary = result[0]['summary_text'].strip()
            summary = self._sanitize_output(summary)

            if style == "bullets" and summary:
                sentences = [s.strip() for s in summary.split('.') if s.strip()]
                if len(sentences) >= 2:
                    summary = "\u2022 " + "\n\u2022 ".join(sentences[:5])

            return summary if summary else self._extractive_fallback(t, max_words)

        except Exception as e:
            warnings.warn(f"Summarization failed: {e}. Using extractive fallback.")
            return self._extractive_fallback(t, max_words)

    def _try_biogpt_summary(self, text: str, style_instructions: str, max_words: int) -> Optional[str]:
        """Attempt to use medical reasoning model for summarization with advanced prompting"""
        try:
            self._load_biogpt()
            if self._biogpt_model is None:
                return None

            prompt = (
                f"{self._system_context} "
                f"{style_instructions} Use Exec style writing. Do not invent facts.\n\n"
                f"Clinical letter:\n{text[:800]}\n\n"
                f"Summary:"
            )

            inputs = self._biogpt_tokenizer(
                prompt,
                return_tensors="pt",
                max_length=1024,
                truncation=True
            ).to(self.device)

            with torch.no_grad():
                outputs = self._biogpt_model.generate(
                    **inputs,
                    max_length=inputs['input_ids'].shape[1] + int(max_words * 2),
                    num_return_sequences=1,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=self._biogpt_tokenizer.eos_token_id
                )

            generated = self._biogpt_tokenizer.decode(outputs[0], skip_special_tokens=True)

            if "Summary:" in generated:
                summary = generated.split("Summary:")[-1].strip()
            else:
                summary = generated.strip()

            summary = self._sanitize_output(summary)

            words = summary.split()
            if len(words) > max_words * 1.5:
                summary = " ".join(words[:int(max_words * 1.5)])

            return summary if summary and len(summary) > 20 else None

        except Exception as e:
            warnings.warn(f"Medical reasoning summary failed: {e}")
            return None

    def generate_recommendation(self, text: str, context_snippets: Optional[List[Dict]] = None) -> Dict:
        """
        Generate a structured clinical recommendation with urgency triage.
        """
        t = (text or "").strip()
        if not t:
            return self._fallback_recommendation("")

        biogpt_rec = self._try_biogpt_recommendation(t, context_snippets)
        if biogpt_rec:
            return biogpt_rec

        return self._fallback_recommendation(t)

    def _try_biogpt_recommendation(self, text: str, context_snippets: Optional[List[Dict]] = None) -> Optional[Dict]:
        """Generate recommendation using medical reasoning model with advanced prompting"""
        try:
            self._load_biogpt()
            if self._biogpt_model is None:
                return None

            ctx = ""
            if context_snippets:
                tops = []
                for item in context_snippets[:3]:
                    meta = item.get("meta") or {}
                    src = meta.get("title") or meta.get("source") or "kb"
                    tops.append(f"[{src}] {item.get('text','')[:400]}")
                ctx = "\n\nKB context:\n" + "\n---\n".join(tops)

            # Build urgency level description from config
            urgency_desc = (
                f"Main Urgency levels are: {self._level_emergency} (immediate action), "
                f"{self._level_urgent} (urgent assessment), {self._level_routine} (standard outpatient review). "
            )

            schema_hint = (
                f"Return STRICT JSON with keys: recommendation_type, urgency, suggested_timeframe, "
                f"red_flags, confidence_level, evidence_basis, reasoning. {self._schema_hint_suffix} "
                f"{urgency_desc}"
                f"Choose the most appropriate urgency based on the letter content and clinical guidelines. "
                f"Make the output VERY neat."
            )

            prompt = (
                f"{self._system_context}\n\n"
                f"Letter text:\n{text[:1000]}\n"
                f"{ctx}\n\n"
                f"{schema_hint}\n"
                f"Return STRICT JSON only.\n\n"
                f"JSON Output:"
            )

            inputs = self._biogpt_tokenizer(
                prompt,
                return_tensors="pt",
                max_length=1024,
                truncation=True
            ).to(self.device)

            with torch.no_grad():
                outputs = self._biogpt_model.generate(
                    **inputs,
                    max_length=inputs['input_ids'].shape[1] + 600,
                    num_return_sequences=1,
                    temperature=0.0,
                    do_sample=False,
                    pad_token_id=self._biogpt_tokenizer.eos_token_id
                )

            response = self._biogpt_tokenizer.decode(outputs[0], skip_special_tokens=True)
            response = self._sanitize_output(response)

            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            valid_levels = {self._level_emergency, self._level_urgent, self._level_routine}

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                rec = json.loads(json_str)

                if isinstance(rec, dict) and rec.get("urgency") in valid_levels:
                    rec.setdefault("recommendation_type", "CARDIOVASCULAR_TRIAGE")
                    rec.setdefault("suggested_timeframe", "")
                    rec.setdefault("red_flags", [])
                    rec.setdefault("confidence_level", "moderate")
                    rec.setdefault("evidence_basis", self._evidence_basis)
                    rec.setdefault("reasoning", "")

                    for key, value in rec.items():
                        if isinstance(value, str):
                            rec[key] = self._sanitize_output(value)
                        elif isinstance(value, list):
                            rec[key] = [self._sanitize_output(str(v)) if isinstance(v, str) else v for v in value]

                    return rec

            return None

        except Exception as e:
            warnings.warn(f"Medical reasoning recommendation failed: {e}")
            return None

    def _format_kb_context(self, snippets: List[Dict]) -> str:
        """Format knowledge base snippets for context"""
        contexts = []
        for item in snippets[:3]:
            meta = item.get("meta") or {}
            src = meta.get("title", "guideline")
            text = item.get("text", "")[:300]
            contexts.append(f"[{src}]: {text}")
        return " | ".join(contexts)

    # ---------- FALLBACKS ----------

    def _extractive_fallback(self, text: str, max_words: int) -> str:
        """Extractive summary: first sentences up to max_words"""
        import re
        clean = " ".join(text.split())
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

    def _fallback_recommendation(self, text: str) -> Dict:
        """
        Conservative, offline triage with safety bias.
        Maps common phrases to urgency/timeframe.
        Supports ACHD signals when congenital scope is active.
        """
        t = (text or "").lower()
        signals: List[str] = []

        def has(*phrases): return any(p in t for p in phrases)

        # Standard cardiovascular signals
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

        # ACHD/congenital signals (from scope overlay)
        fallback_signals = self.config.get("fallback_signals", {})
        achd_emergency_phrases = fallback_signals.get("emergency", [])
        achd_urgent_phrases = fallback_signals.get("urgent", [])

        achd_emerg_hit = False
        achd_urgent_hit = False
        for phrase in achd_emergency_phrases:
            if phrase.lower() in t:
                signals.append(f"ACHD: {phrase}")
                achd_emerg_hit = True
        for phrase in achd_urgent_phrases:
            if phrase.lower() in t:
                signals.append(f"ACHD: {phrase}")
                achd_urgent_hit = True

        urgency = self._level_routine
        timeframe = self._timeframes.get("routine", "Routine outpatient review and non-invasive diagnostics.")

        if achd_emerg_hit or any(s in signals for s in ["suspected aortic dissection", "haemodynamic concern", "ongoing/rest chest pain"]):
            urgency = self._level_emergency
            timeframe = self._timeframes.get("emergency", "Immediate escalation via local emergency protocol (ED/cardiology).")
        elif achd_urgent_hit or any(s in signals for s in ["possible ACS", "syncope/presyncope"]):
            urgency = self._level_urgent
            timeframe = self._timeframes.get("urgent", "Urgent assessment within 2 weeks, aligned to NICE ACS/chest-pain pathways.")
        elif any(s in signals for s in ["urgent surgical referral mentioned", "possible severe aortic stenosis", "suspected endocarditis"]):
            urgency = self._level_urgent
            timeframe = "Discuss promptly with cardiology; consider surgical team triage if confirmed."

        return {
            "recommendation_type": "CARDIOVASCULAR_TRIAGE",
            "urgency": urgency,
            "suggested_timeframe": timeframe,
            "red_flags": signals,
            "confidence_level": "cautious",
            "evidence_basis": self._evidence_basis,
            "reasoning": "Heuristic offline triage used because model output was unavailable or invalid; signals mapped to conservative escalation."
        }

    # Public alias so callers can use either name
    def fallback_recommendation(self, text: str) -> Dict:
        return self._fallback_recommendation(text)
