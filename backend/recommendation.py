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

class ClinicalRecommendationEngine:
    """
    Generates AI summaries and triage recommendations for cardiovascular letters.
    Uses LOCAL medical models (BioGPT + BART) - NHS compliant, no external APIs.
    Maintains advanced prompting and reasoning from original Claude implementation.
    """

    def __init__(self, use_gpu: bool = None):
        """
        Initialize local medical models.
        
        Args:
            use_gpu: If True, use GPU if available. If None, auto-detect.
        """
        self.device = "cuda" if (use_gpu or (use_gpu is None and torch.cuda.is_available())) else "cpu"
        print(f"[ClinicalRecommendationEngine] Using device: {self.device}")
        
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
        """Load BART summarization model (if not already loaded)"""
        if self._summarizer is None:
            print("[NHS-AI] Loading BART summarization model...")
            model_name = "facebook/bart-large-cnn"
            self._summarizer = pipeline(
                "summarization",
                model=model_name,
                device=0 if self.device == "cuda" else -1
            )
            print(f"[NHS-AI] BART loaded on {self.device}")

    def _load_biogpt(self):
        """Load BioGPT model for medical reasoning (lazy load - heavy model)"""
        if self._biogpt_model is None:
            print("[NHS-AI] Loading BioGPT medical model (this may take a minute)...")
            model_name = "microsoft/BioGPT-Large"
            try:
                self._biogpt_tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._biogpt_model = AutoModelForCausalLM.from_pretrained(model_name)
                self._biogpt_model.to(self.device)
                self._biogpt_model.eval()
                print(f"[NHS-AI] BioGPT loaded on {self.device}")
            except Exception as e:
                warnings.warn(f"BioGPT loading failed: {e}. Will use rule-based fallbacks.")
                self._biogpt_model = None
                self._biogpt_tokenizer = None

    def _sanitize_output(self, text: str) -> str:
        """
        Clean model output by removing XML tags, special tokens, and formatting artifacts.
        
        Args:
            text: Raw model output
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove XML/HTML-like tags (e.g., </FREETEXT>, </TITLE>, <...>)
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove special tokens and unicode artifacts
        text = re.sub(r'[▁▂▃▄▅▆▇█▉▊▋▌▍▎▏]', '', text)
        
        # Remove BPE tokens like </s>, <s>, <pad>
        text = re.sub(r'</?s>|<pad>|<unk>|<mask>', '', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text

    # ---------- PUBLIC API ----------

    def summarize(self, text: str, max_words: int = 140, style: str = "exec") -> str:
        """
        Returns a concise surgeon-facing summary using local models with advanced prompting.
        
        Args:
            text: Input clinical text
            max_words: Target word count
            style: "exec" | "bullets" | "concise"
        
        Returns:
            Clinical summary string following original style instructions
        """
        t = (text or "").strip()
        if not t:
            return ""

        # Original style instructions from Claude version
        style_instructions = {
            "exec": (
                "3–5 line executive summary for a cardiothoracic surgeon. "
                "Include: indication/reason for referral, key symptoms with duration/severity, functional capacity, "
                "and the explicit ask. UK clinical wording, no PII. Based on NHS guidelines"
                "and the explicit ask. UK clinical wording, no PII. Based on NHS guidelines"
            ),
            "bullets": (
                "Concise 3–5 bullet summary with bolded labels: Indication, Symptoms, Function, Request. "
                "UK clinical wording, no PII. Based on NHS guidelines."
            ),
            "concise": (
                "Short surgeon-facing paragraph (5–7 lines) highlighting indication, key symptoms, "
                "functional capacity and the ask. UK clinical wording, no PII. Based on NHS guidelines"
            ),
        }.get(style, "Concise, surgeon-facing summary. UK clinical wording, no PII.")

        # Try BioGPT first for medical-domain summarization
        biogpt_result = self._try_biogpt_summary(t, style_instructions, max_words)
        if biogpt_result:
            # SANITIZE the output before returning
            return self._sanitize_output(biogpt_result)

        # Fallback to BART summarizer
        if self._summarizer is None:
            try:
                self._load_summarizer()
            except Exception:
                return self._extractive_fallback(t, max_words)

        try:
            # Truncate if needed (BART optimal: 400-1024 tokens)
            max_input_length = 1024
            if len(t.split()) > max_input_length:
                t = " ".join(t.split()[:max_input_length])
            
            # Generate summary with context
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
            
            # SANITIZE the output
            summary = self._sanitize_output(summary)
            
            # Post-process to match style
            if style == "bullets" and summary:
                # Format as bullets if possible
                sentences = [s.strip() for s in summary.split('.') if s.strip()]
                if len(sentences) >= 2:
                    summary = "• " + "\n• ".join(sentences[:5])
            
            return summary if summary else self._extractive_fallback(t, max_words)
            
        except Exception as e:
            warnings.warn(f"Summarization failed: {e}. Using extractive fallback.")
            return self._extractive_fallback(t, max_words)

    def _try_biogpt_summary(self, text: str, style_instructions: str, max_words: int) -> Optional[str]:
        """Attempt to use BioGPT for medical summarization with advanced prompting"""
        try:
            self._load_biogpt()
            if self._biogpt_model is None:
                return None
            
            # Advanced prompt mimicking original Claude instructions
            prompt = (
                f"You are an NHS decision-support assistant for cardiology/cardiothoracic teams. "
                f"{style_instructions} Use Exec style writing. Do not invent facts. "
                f"You are knowledgeable about cardiovascular and cardiothoracic surgeries within NHS standards.\n\n"
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
            
            # Extract only the summary part (after "Summary:")
            if "Summary:" in generated:
                summary = generated.split("Summary:")[-1].strip()
            else:
                summary = generated.strip()
            
            # Clean up the output
            summary = self._sanitize_output(summary)
            
            # Trim to reasonable length
            words = summary.split()
            if len(words) > max_words * 1.5:
                summary = " ".join(words[:int(max_words * 1.5)])
            
            return summary if summary and len(summary) > 20 else None
            
        except Exception as e:
            warnings.warn(f"BioGPT summary failed: {e}")
            return None

    def generate_recommendation(self, text: str, context_snippets: Optional[List[Dict]] = None) -> Dict:
        """
        Generate a structured clinical recommendation with urgency triage.
        
        Args:
            text: Clinical letter text
            context_snippets: Optional KB results for context
        
        Returns:
            Dict with recommendation_type, urgency, timeframe, red_flags, etc.
        """
        t = (text or "").strip()
        if not t:
            return self._fallback_recommendation("")
        
        # Try BioGPT recommendation with advanced prompting
        biogpt_rec = self._try_biogpt_recommendation(t, context_snippets)
        if biogpt_rec:
            return biogpt_rec
        
        # Fallback to rule-based
        return self._fallback_recommendation(t)

    def _try_biogpt_recommendation(self, text: str, context_snippets: Optional[List[Dict]] = None) -> Optional[Dict]:
        """Generate recommendation using BioGPT with original advanced prompting"""
        try:
            self._load_biogpt()
            if self._biogpt_model is None:
                return None
            
            # Format KB context like original
            ctx = ""
            if context_snippets:
                tops = []
                for item in context_snippets[:3]:
                    meta = item.get("meta") or {}
                    src = meta.get("title") or meta.get("source") or "kb"
                    tops.append(f"[{src}] {item.get('text','')[:400]}")
                ctx = "\n\nKB context:\n" + "\n---\n".join(tops)
            
            # Original schema hint
            schema_hint = (
                "Return STRICT JSON with keys: recommendation_type, urgency, suggested_timeframe, "
                "red_flags, confidence_level, evidence_basis, reasoning. Based on NHS standards for cardiology/cardiothoracic triage. "
                "Urgency must adhere to NHS and NICE guidelines for cardiovascular and thoracic conditions. "
                "Under the NHS Constitution, if your GP refers you for a condition that's not urgent, you have the right to start treatment "
                "led by a consultant within 18 weeks from when you're referred, unless you want to wait longer or waiting longer is clinically right for you. "
                "Main Urgency levels are: EMERGENCY (immediate action), URGENT (within 2-4 weeks), ROUTINE (standard outpatient review/recommendations to GP). "
                "Choose the most appropriate urgency based on the letter content and NHS guidelines as well as all other statistical knowledge and nuance of the patient's history. "
                "Make the output VERY neat."
            )
            
            # Original system-style instructions embedded in prompt
            system_context = (
                "You are an NHS DTAC-aware assistant for cardiology/cardiothoracic teams. "
                "Provide conservative, guideline-aligned triage recommendations based on the letter. "
                "Prefer NICE CG95 (chest pain), NG185 (ACS), NG208 (valve disease), and the NHS England "
                "Adult Cardiac Surgery Service Specification. Do not invent facts. "
                "Please use Exec Style for reasoning. Make sure the summary of the letter is neat and contains the main points of the letter. "
                "Use the Knowledge base PDFs to inform your recommendations. Make sure that it adheres to DTAC guidelines. "
                "Make sure that the output is neatly formatted and easy to read."
            )
            
            # Construct full prompt
            prompt = (
                f"{system_context}\n\n"
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
                    temperature=0.0,  # Deterministic like original
                    do_sample=False,
                    pad_token_id=self._biogpt_tokenizer.eos_token_id
                )
            
            response = self._biogpt_tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # SANITIZE the response
            response = self._sanitize_output(response)
            
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                rec = json.loads(json_str)
                
                # Validate structure
                if isinstance(rec, dict) and rec.get("urgency") in ["EMERGENCY", "URGENT", "ROUTINE"]:
                    # Ensure all required fields exist
                    rec.setdefault("recommendation_type", "CARDIOVASCULAR_TRIAGE")
                    rec.setdefault("suggested_timeframe", "")
                    rec.setdefault("red_flags", [])
                    rec.setdefault("confidence_level", "moderate")
                    rec.setdefault("evidence_basis", "NICE guidelines and NHS standards")
                    rec.setdefault("reasoning", "")
                    
                    # Sanitize all string fields
                    for key, value in rec.items():
                        if isinstance(value, str):
                            rec[key] = self._sanitize_output(value)
                        elif isinstance(value, list):
                            rec[key] = [self._sanitize_output(str(v)) if isinstance(v, str) else v for v in value]
                    
                    return rec
            
            return None
            
        except Exception as e:
            warnings.warn(f"BioGPT recommendation failed: {e}")
            return None

    def _format_kb_context(self, snippets: List[Dict]) -> str:
        """Format knowledge base snippets for context (original format)"""
        contexts = []
        for item in snippets[:3]:
            meta = item.get("meta") or {}
            src = meta.get("title", "guideline")
            text = item.get("text", "")[:300]
            contexts.append(f"[{src}]: {text}")
        return " | ".join(contexts)

    # ---------- FALLBACKS ----------

    def _extractive_fallback(self, text: str, max_words: int) -> str:
        """Extractive summary: first sentences up to max_words (original logic)"""
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
        Maps common phrases to urgency/timeframe consistent with NICE CG95/NG185/NG208.
        Original logic preserved.
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