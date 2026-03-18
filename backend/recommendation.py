from __future__ import annotations
import json
import os
import warnings
import re
import threading
from typing import List, Optional, Dict
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    pipeline,
)

try:
    import requests as _requests
except ImportError:
    _requests = None

# Global model cache keyed by model_id — prevents redundant loading across frameworks
_model_cache: Dict[str, object] = {}
_cache_lock = threading.Lock()

# Maximum number of cached model entries before eviction
_MAX_CACHE_ENTRIES = 4


def _evict_cache_if_needed() -> None:
    """Evict oldest cache entries and free GPU memory when cache exceeds limit."""
    while len(_model_cache) >= _MAX_CACHE_ENTRIES:
        oldest_key = next(iter(_model_cache))
        entry = _model_cache.pop(oldest_key)
        del entry
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print(f"[ModelCache] Evicted: {oldest_key}")


def _get_torch_dtype(device: str):
    """Return fp16 on CUDA, fp32 on CPU."""
    if device == "cuda":
        if torch.cuda.is_bf16_supported():
            return torch.bfloat16
        return torch.float16
    return torch.float32


class ClinicalRecommendationEngine:
    """
    Generates AI summaries and triage recommendations for cardiovascular letters.
    Uses LOCAL medical models — compliant, no external APIs.
    Supports config-driven model selection and multi-framework prompting.
    """

    def __init__(self, use_gpu: bool = None, config: Optional[dict] = None):
        """
        Initialize local medical models (lazy-loaded on first use).

        Args:
            use_gpu: If True, use GPU if available. If None, auto-detect.
            config: Framework configuration dict. Defaults to NHS UK behavior.
        """
        self.device = "cuda" if (use_gpu or (use_gpu is None and torch.cuda.is_available())) else "cpu"
        self._dtype = _get_torch_dtype(self.device)
        print(f"[ClinicalRecommendationEngine] Using device: {self.device} (dtype={self._dtype})")

        self.config = config or {}

        # Resolve model IDs from config or use defaults
        models_cfg = self.config.get("models", {})
        self._summarizer_model_id = models_cfg.get("summarization", {}).get("model_id", "facebook/bart-large-cnn")
        self._reasoning_model_id = models_cfg.get("medical_reasoning", {}).get("model_id", "microsoft/BioGPT")

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

        # Ollama configuration for Phi-3 clinical reasoning
        ollama_cfg = models_cfg.get("ollama_reasoning", {})
        self._ollama_url = ollama_cfg.get(
            "base_url",
            os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        )
        self._ollama_model = ollama_cfg.get(
            "model",
            os.environ.get("OLLAMA_MODEL", "phi3:mini")
        )
        self._ollama_timeout = int(ollama_cfg.get("timeout", 120))

        # Models will be lazy-loaded on first use
        self._summarizer = None
        self._biogpt_model = None
        self._biogpt_tokenizer = None
        self._init_error = None
        self._ollama_available = None  # None = not checked yet

    def _load_summarizer(self):
        """Load summarization model with fp16 on CUDA, cache-eviction, and OOM fallback."""
        if self._summarizer is not None:
            return
        cache_key = f"summarizer:{self._summarizer_model_id}"
        with _cache_lock:
            if cache_key in _model_cache:
                self._summarizer = _model_cache[cache_key]
                return
            _evict_cache_if_needed()
        print(f"[AI] Loading summarization model: {self._summarizer_model_id}...")
        try:
            self._summarizer = pipeline(
                "summarization",
                model=self._summarizer_model_id,
                tokenizer=AutoTokenizer.from_pretrained(
                    self._summarizer_model_id, model_max_length=1024
                ),
                device=0 if self.device == "cuda" else -1,
                torch_dtype=self._dtype,
            )
        except RuntimeError as e:
            if "CUDA" in str(e) or "out of memory" in str(e).lower():
                print("[AI] CUDA OOM loading summarizer, falling back to CPU")
                torch.cuda.empty_cache()
                self.device = "cpu"
                self._dtype = torch.float32
                self._summarizer = pipeline(
                    "summarization",
                    model=self._summarizer_model_id,
                    tokenizer=AutoTokenizer.from_pretrained(
                        self._summarizer_model_id, model_max_length=1024
                    ),
                    device=-1,
                )
            else:
                raise
        with _cache_lock:
            _model_cache[cache_key] = self._summarizer
        print(f"[AI] Summarizer loaded on {self.device}")

    def _load_biogpt(self):
        """Load medical reasoning model with fp16 on CUDA, cache-eviction, and OOM fallback."""
        if self._biogpt_model is not None:
            return
        cache_key = f"reasoning:{self._reasoning_model_id}"
        with _cache_lock:
            if cache_key in _model_cache:
                cached = _model_cache[cache_key]
                self._biogpt_tokenizer = cached["tokenizer"]
                self._biogpt_model = cached["model"]
                return
            _evict_cache_if_needed()
        print(f"[AI] Loading medical reasoning model: {self._reasoning_model_id} (this may take a minute)...")
        try:
            self._biogpt_tokenizer = AutoTokenizer.from_pretrained(self._reasoning_model_id)
            self._biogpt_model = AutoModelForCausalLM.from_pretrained(
                self._reasoning_model_id, torch_dtype=self._dtype
            )
            self._biogpt_model.to(self.device)
            self._biogpt_model.eval()
            with _cache_lock:
                _model_cache[cache_key] = {"tokenizer": self._biogpt_tokenizer, "model": self._biogpt_model}
            print(f"[AI] Medical reasoning model loaded on {self.device}")
        except RuntimeError as e:
            if "CUDA" in str(e) or "out of memory" in str(e).lower():
                print("[AI] CUDA OOM loading BioGPT, falling back to CPU")
                torch.cuda.empty_cache()
                self.device = "cpu"
                self._dtype = torch.float32
                try:
                    self._biogpt_model = AutoModelForCausalLM.from_pretrained(self._reasoning_model_id)
                    self._biogpt_model.to("cpu")
                    self._biogpt_model.eval()
                    with _cache_lock:
                        _model_cache[cache_key] = {"tokenizer": self._biogpt_tokenizer, "model": self._biogpt_model}
                    print("[AI] Medical reasoning model loaded on CPU (fallback)")
                except Exception as e2:
                    warnings.warn(f"CPU fallback also failed: {e2}. Will use rule-based fallbacks.")
                    self._biogpt_model = None
                    self._biogpt_tokenizer = None
            else:
                warnings.warn(f"Medical reasoning model loading failed: {e}. Will use rule-based fallbacks.")
                self._biogpt_model = None
                self._biogpt_tokenizer = None
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
        text = re.sub(r'</?s>|<pad>|<unk>|<mask>', ' ', text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'[▁▂▃▄▅▆▇█▉▊▋▌▍▎▏]', '', text)
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

        # Use BART directly for summarization — BioGPT (small) is a text-completion
        # model that doesn't follow summarization instructions reliably.
        # BART-large-cnn is purpose-built for abstractive summarization.
        if self._summarizer is None:
            try:
                self._load_summarizer()
            except Exception:
                return self._extractive_fallback(t, max_words)

        try:
            # BART-large-cnn has a 1024-token position embedding limit.
            # 600 words ≈ 750 subword tokens — safely under the limit.
            max_input_length = 600
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

        except RuntimeError as e:
            if "CUDA" in str(e) or "out of memory" in str(e).lower():
                torch.cuda.empty_cache()
                warnings.warn("CUDA OOM during summarization, using extractive fallback.")
            else:
                warnings.warn(f"Summarization failed: {e}. Using extractive fallback.")
            return self._extractive_fallback(t, max_words)
        except Exception as e:
            warnings.warn(f"Summarization failed: {e}. Using extractive fallback.")
            return self._extractive_fallback(t, max_words)

    def generate_recommendation(self, text: str, context_snippets: Optional[List[Dict]] = None) -> Dict:
        """
        Generate a structured clinical recommendation with urgency triage.

        Tries models in order: Ollama (Phi-3) → BioGPT → rule-based fallback.
        """
        t = (text or "").strip()
        if not t:
            return self._fallback_recommendation("")

        # 1. Try Ollama (Phi-3) — best reasoning quality
        ollama_rec = self._try_ollama_recommendation(t, context_snippets)
        if ollama_rec:
            return ollama_rec

        # 2. Try local BioGPT — limited but runs in-process
        biogpt_rec = self._try_biogpt_recommendation(t, context_snippets)
        if biogpt_rec:
            return biogpt_rec

        # 3. Rule-based fallback — always available
        return self._fallback_recommendation(t)

    # ---------- SIGNAL EXTRACTION FROM MODEL OUTPUT ----------

    # Clinical signal phrases to detect in BioGPT free-text output.
    # Grouped by severity so we can score them.
    _EMERGENCY_SIGNAL_PHRASES = [
        "immediate", "emergency", "life-threatening", "life threatening",
        "cardiogenic shock", "cardiac arrest", "aortic dissection",
        "type a dissection", "stemi", "st-elevation", "st elevation",
        "vf arrest", "vt storm", "cardiac tamponade", "haemodynamic instability",
        "hemodynamic instability", "pulmonary embolism", "acute heart failure",
        "rupture", "acute coronary", "ongoing ischemia", "ongoing ischaemia",
    ]

    _URGENT_SIGNAL_PHRASES = [
        "urgent", "expedited", "priority", "prompt",
        "nstemi", "unstable angina", "troponin", "raised troponin",
        "syncope", "presyncope", "severe stenosis", "critical stenosis",
        "severe regurgitation", "heart failure", "decompensated",
        "endocarditis", "vegetation", "embolic", "rapid deterioration",
        "worsening symptoms", "nyha class iii", "nyha class iv",
        "reduced ejection fraction", "lvef", "ef <", "ef<",
    ]

    _ROUTINE_SIGNAL_PHRASES = [
        "routine", "elective", "outpatient", "stable", "monitoring",
        "conservative", "follow-up", "follow up", "reassess",
        "non-urgent", "watchful waiting", "mild", "asymptomatic",
    ]

    def _extract_model_signals(self, model_text: str) -> dict:
        """Parse BioGPT free-text output for clinical signal phrases.

        Returns dict with keys: emergency_hits, urgent_hits, routine_hits (lists of matched phrases),
        and raw_reasoning (cleaned model text).
        """
        t = model_text.lower()
        emergency_hits = [p for p in self._EMERGENCY_SIGNAL_PHRASES if p in t]
        urgent_hits = [p for p in self._URGENT_SIGNAL_PHRASES if p in t]
        routine_hits = [p for p in self._ROUTINE_SIGNAL_PHRASES if p in t]
        return {
            "emergency_hits": emergency_hits,
            "urgent_hits": urgent_hits,
            "routine_hits": routine_hits,
            "raw_reasoning": model_text,
        }

    def _check_ollama_health(self) -> bool:
        """Check if the Ollama service is reachable."""
        if _requests is None:
            return False
        try:
            resp = _requests.get(f"{self._ollama_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def _try_ollama_recommendation(self, text: str, context_snippets: Optional[List[Dict]] = None) -> Optional[Dict]:
        """Generate clinical reasoning via Ollama (Phi-3) HTTP API.

        Phi-3 is an instruction-following model that produces structured clinical
        reasoning, unlike BioGPT which only does text completion. This method:
        1. Sends a clinical reasoning prompt to Ollama.
        2. Parses the response for urgency signals.
        3. Returns a structured recommendation dict.

        Falls back to None if Ollama is unavailable, letting the caller
        try BioGPT or rule-based fallback.
        """
        if _requests is None:
            print("[AI] 'requests' package not installed, skipping Ollama")
            return None

        # Check availability (cache result for session)
        if self._ollama_available is None:
            self._ollama_available = self._check_ollama_health()
            if self._ollama_available:
                print(f"[AI] Ollama available at {self._ollama_url}, model: {self._ollama_model}")
            else:
                print(f"[AI] Ollama not available at {self._ollama_url}, will try local models")
        if not self._ollama_available:
            return None

        try:
            # Build context from knowledge base snippets
            ctx = ""
            if context_snippets:
                tops = []
                for item in context_snippets[:3]:
                    meta = item.get("meta") or {}
                    src = meta.get("title") or meta.get("source") or "kb"
                    tops.append(f"[{src}] {item.get('text', '')[:400]}")
                ctx = "\n\nRelevant clinical guidelines:\n" + "\n---\n".join(tops)

            prompt = (
                f"{self._system_context}\n\n"
                f"Referral letter:\n{text[:1500]}\n"
                f"{ctx}\n\n"
                f"Based on the above referral letter, provide:\n"
                f"1. A brief clinical assessment of the patient's presentation\n"
                f"2. The recommended urgency level: {self._level_emergency}, {self._level_urgent}, or {self._level_routine}\n"
                f"3. Key red flags identified\n"
                f"4. Recommended next steps and timeframe\n\n"
                f"Be concise and evidence-based. {self._schema_hint_suffix}"
            )

            payload = {
                "model": self._ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 512,
                    "repeat_penalty": 1.2,
                }
            }

            resp = _requests.post(
                f"{self._ollama_url}/api/generate",
                json=payload,
                timeout=self._ollama_timeout,
            )

            if resp.status_code != 200:
                print(f"[AI] Ollama returned status {resp.status_code}")
                return None

            result = resp.json()
            reasoning_text = result.get("response", "").strip()
            reasoning_text = self._sanitize_output(reasoning_text)

            if not reasoning_text or len(reasoning_text) < 20:
                print("[AI] Ollama produced insufficient output, will try fallback")
                return None

            print(f"[AI] Ollama reasoning ({len(reasoning_text)} chars): {reasoning_text[:120]}...")

            # Extract clinical signals from the model's reasoning
            model_signals = self._extract_model_signals(reasoning_text)

            # Also run rule-based signal detection on the original text
            rule_signals = self._rule_based_signals(text)

            # Merge signals
            all_red_flags = sorted(set(
                rule_signals["red_flags"]
                + model_signals["emergency_hits"]
                + model_signals["urgent_hits"]
            ))

            # Score: combine rule-based and model-derived signals
            score = 0.0
            score += 5.0 * len(model_signals["emergency_hits"])
            score += 2.0 * len(model_signals["urgent_hits"])
            score -= 0.5 * len(model_signals["routine_hits"])
            score += 3.0 * len(rule_signals["emergency_flags"])
            score += 1.5 * len(rule_signals["urgent_flags"])

            # Determine urgency from combined score
            if score >= 5.0 or model_signals["emergency_hits"]:
                urgency = self._level_emergency
                timeframe = self._timeframes.get("emergency",
                    "Immediate escalation via local emergency protocol (ED/cardiology).")
                confidence = "high" if score >= 8.0 else "moderate"
            elif score >= 2.0 or model_signals["urgent_hits"]:
                urgency = self._level_urgent
                timeframe = self._timeframes.get("urgent",
                    "Urgent assessment within 2 weeks, aligned to NICE ACS/chest-pain pathways.")
                confidence = "moderate"
            else:
                urgency = self._level_routine
                timeframe = self._timeframes.get("routine",
                    "Routine outpatient review and non-invasive diagnostics.")
                confidence = "moderate" if model_signals["routine_hits"] else "cautious"

            # Truncate reasoning if excessively long
            if len(reasoning_text) > 800:
                reasoning_text = reasoning_text[:797] + "..."

            return {
                "recommendation_type": "CARDIOVASCULAR_TRIAGE",
                "urgency": urgency,
                "suggested_timeframe": timeframe,
                "red_flags": all_red_flags,
                "confidence_level": confidence,
                "evidence_basis": self._evidence_basis,
                "reasoning": reasoning_text,
                "model_contributed": True,
                "model_source": f"ollama/{self._ollama_model}",
            }

        except _requests.exceptions.Timeout:
            print(f"[AI] Ollama request timed out after {self._ollama_timeout}s")
            return None
        except _requests.exceptions.ConnectionError:
            print("[AI] Cannot connect to Ollama service")
            self._ollama_available = False
            return None
        except Exception as e:
            warnings.warn(f"Ollama recommendation failed: {e}")
            return None

    def _try_biogpt_recommendation(self, text: str, context_snippets: Optional[List[Dict]] = None) -> Optional[Dict]:
        """Generate recommendation using BioGPT for medical reasoning + rule-based structuring.

        BioGPT is a biomedical text-completion model — it generates clinical prose,
        not structured JSON. This method:
        1. Prompts BioGPT to produce free-text clinical reasoning about the referral.
        2. Extracts clinical signal phrases from that reasoning.
        3. Combines model signals with rule-based scoring on the original text.
        4. Builds the structured recommendation with the model's reasoning included.
        """
        try:
            self._load_biogpt()
            if self._biogpt_model is None:
                return None

            # Build context from knowledge base snippets
            ctx = ""
            if context_snippets:
                tops = []
                for item in context_snippets[:3]:
                    meta = item.get("meta") or {}
                    src = meta.get("title") or meta.get("source") or "kb"
                    tops.append(f"[{src}] {item.get('text','')[:400]}")
                ctx = "\nRelevant clinical guidelines:\n" + "\n---\n".join(tops)

            # Prompt BioGPT for free-text clinical reasoning (what it's good at)
            prompt = (
                f"Clinical referral letter for cardiovascular assessment:\n"
                f"{text[:800]}\n"
                f"{ctx}\n\n"
                f"Clinical assessment: This patient presents with"
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
                    max_length=inputs['input_ids'].shape[1] + 256,
                    num_return_sequences=1,
                    temperature=0.0,
                    do_sample=False,
                    repetition_penalty=1.3,
                    pad_token_id=self._biogpt_tokenizer.eos_token_id
                )

            # Decode only the generated tokens (strip the prompt echo)
            generated_ids = outputs[0][inputs['input_ids'].shape[1]:]
            reasoning_text = self._biogpt_tokenizer.decode(generated_ids, skip_special_tokens=True)
            reasoning_text = self._sanitize_output(reasoning_text)

            if not reasoning_text or len(reasoning_text.strip()) < 10:
                print("[AI] BioGPT produced insufficient output, will use rule-based fallback")
                return None

            print(f"[AI] BioGPT reasoning ({len(reasoning_text)} chars): {reasoning_text[:120]}...")

            # Extract clinical signals from the model's reasoning
            model_signals = self._extract_model_signals(reasoning_text)

            # Also run rule-based signal detection on the original text
            rule_signals = self._rule_based_signals(text)

            # Merge signals: model signals augment rule-based signals
            all_red_flags = sorted(set(rule_signals["red_flags"] + model_signals["emergency_hits"] + model_signals["urgent_hits"]))

            # Score: combine rule-based and model-derived signals
            score = 0.0
            score += 5.0 * len(model_signals["emergency_hits"])
            score += 2.0 * len(model_signals["urgent_hits"])
            score -= 0.5 * len(model_signals["routine_hits"])
            score += 3.0 * len(rule_signals["emergency_flags"])
            score += 1.5 * len(rule_signals["urgent_flags"])

            # Determine urgency from combined score
            if score >= 5.0 or model_signals["emergency_hits"]:
                urgency = self._level_emergency
                timeframe = self._timeframes.get("emergency",
                    "Immediate escalation via local emergency protocol (ED/cardiology).")
                confidence = "high" if score >= 8.0 else "moderate"
            elif score >= 2.0 or model_signals["urgent_hits"]:
                urgency = self._level_urgent
                timeframe = self._timeframes.get("urgent",
                    "Urgent assessment within 2 weeks, aligned to NICE ACS/chest-pain pathways.")
                confidence = "moderate"
            else:
                urgency = self._level_routine
                timeframe = self._timeframes.get("routine",
                    "Routine outpatient review and non-invasive diagnostics.")
                confidence = "moderate" if model_signals["routine_hits"] else "cautious"

            # Build the structured recommendation with model reasoning
            reasoning_summary = f"This patient presents with {reasoning_text.strip()}"
            # Truncate if excessively long
            if len(reasoning_summary) > 800:
                reasoning_summary = reasoning_summary[:797] + "..."

            return {
                "recommendation_type": "CARDIOVASCULAR_TRIAGE",
                "urgency": urgency,
                "suggested_timeframe": timeframe,
                "red_flags": all_red_flags,
                "confidence_level": confidence,
                "evidence_basis": self._evidence_basis,
                "reasoning": reasoning_summary,
                "model_contributed": True,
            }

        except RuntimeError as e:
            if "CUDA" in str(e) or "out of memory" in str(e).lower():
                torch.cuda.empty_cache()
                warnings.warn("CUDA OOM during recommendation generation, falling back to heuristic.")
            else:
                warnings.warn(f"Medical reasoning recommendation failed: {e}")
            return None
        except Exception as e:
            warnings.warn(f"Medical reasoning recommendation failed: {e}")
            return None

    def _rule_based_signals(self, text: str) -> dict:
        """Extract clinical signal categories from original referral text using keyword matching."""
        t = (text or "").lower()

        def has(*phrases):
            return any(p in t for p in phrases)

        emergency_flags = []
        urgent_flags = []
        red_flags = []

        # Emergency-level signals
        if has("aortic dissection", "tearing chest pain", "mediastinal widening"):
            emergency_flags.append("suspected aortic dissection")
        if has("haemodynamic instability", "hemodynamic instability", "hypotension", "shock", "cardiogenic shock"):
            emergency_flags.append("haemodynamic compromise")
        if has("ongoing chest pain", "rest pain", "pain at rest"):
            emergency_flags.append("ongoing/rest chest pain")
        if has("stemi", "st-elevation", "st elevation myocardial"):
            emergency_flags.append("STEMI")
        if has("cardiac arrest", "vf arrest", "vt storm"):
            emergency_flags.append("cardiac arrest/malignant arrhythmia")

        # Urgent-level signals
        if has("nstemi", "raised troponin", "elevated troponin", "myocardial infarction"):
            urgent_flags.append("possible ACS")
        if has("syncope", "presyncope", "blackout", "collapse"):
            urgent_flags.append("syncope/presyncope")
        if has("severe aortic stenosis", "critical aortic stenosis"):
            urgent_flags.append("severe aortic stenosis")
        if has("infective endocarditis", "endocarditis", "vegetation"):
            urgent_flags.append("suspected endocarditis")
        if has("urgent surgical referral", "urgent cardiothoracic referral"):
            urgent_flags.append("urgent surgical referral mentioned")
        if has("decompensated heart failure", "acute heart failure", "pulmonary oedema", "pulmonary edema"):
            urgent_flags.append("decompensated heart failure")

        red_flags = emergency_flags + urgent_flags

        # ACHD/congenital signals from config scope overlays
        fallback_signals = self.config.get("fallback_signals", {})
        for phrase in fallback_signals.get("emergency", []):
            if phrase.lower() in t:
                emergency_flags.append(f"ACHD: {phrase}")
                red_flags.append(f"ACHD: {phrase}")
        for phrase in fallback_signals.get("urgent", []):
            if phrase.lower() in t:
                urgent_flags.append(f"ACHD: {phrase}")
                red_flags.append(f"ACHD: {phrase}")

        return {
            "emergency_flags": emergency_flags,
            "urgent_flags": urgent_flags,
            "red_flags": red_flags,
        }

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
            out.append(p)
            count += w
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
            "reasoning": "Rule-based triage: model was unavailable; signals mapped to conservative escalation.",
            "model_contributed": False,
        }

    # Public alias so callers can use either name
    def fallback_recommendation(self, text: str) -> Dict:
        return self._fallback_recommendation(text)
