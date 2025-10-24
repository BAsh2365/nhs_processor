# backend/processor.py
from typing import Dict, Optional, List, Union, IO
from datetime import datetime

from .anonymizer import DataAnonymizer
from .pdf_processor import PDFProcessor
from .recommendation import ClinicalRecommendationEngine
from .logger import NHSComplianceLogger
from .models import PatientData, ClinicalRecommendation  # keep import even if not used directly


class MedicalDocumentProcessor:
    """
    PDF (bytes/IO) -> text extraction (+OCR if available) -> PII redaction -> normalization
    -> AI summary (Claude if available, else extractive) -> recommendation (Claude or fallback)
    -> structured result for the frontend.
    """

    def __init__(self, api_key: Optional[str] = None, user_id: str = "SYSTEM"):
        self.anonymizer = DataAnonymizer()
        self.pdf_processor = PDFProcessor()
        self.engine = ClinicalRecommendationEngine(anthropic_api_key=api_key)
        self.logger = NHSComplianceLogger()
        self.user_id = user_id

    def _normalize_text(self, text: str) -> str:
        text = (text or "").replace("\x00", " ").strip()
        return " ".join(text.split())

    def process_document(self, file_obj: IO[bytes], patient_identifier: str) -> Dict[str, Union[bool, Dict, str, List]]:
        processing_date = datetime.now().isoformat()
        patient_id_hash = self.anonymizer.hash_patient_id(patient_identifier)

        # Access log
        self.logger.log_access(
            action="DOCUMENT_UPLOAD",
            patient_id_hash=patient_id_hash,
            user_id=self.user_id,
            details="processor=MedicalDocumentProcessor"
        )

        # Patient metadata (dict so it's JSON-serialisable)
        patient_meta: Dict[str, str] = {
            "patient_id_hash": patient_id_hash,
            "processing_date": processing_date,
            "document_type": "CLINICAL_DOCUMENT",
        }

        try:
            # 1) Extract text (prefer OCR if your PDFProcessor supports it)
            try:
                extracted = self.pdf_processor.extract_text_from_uploaded_file(file_obj, use_ocr=True)  # type: ignore
            except TypeError:
                extracted = self.pdf_processor.extract_text_from_uploaded_file(file_obj)

            full_text = extracted or ""
            # 2) Redact & normalize
            redacted = self.anonymizer.redact_pii(full_text)
            normalized_text = self._normalize_text(redacted)

            # 3) AI summary (Claude if key set; else extractive fallback)
            text_for_ai = normalized_text or full_text or ""
            try:
                ai_summary = self.engine.summarize(text_for_ai, max_words=140, style="exec") if text_for_ai else ""
            except Exception as e:
                self.logger.log_error("SummaryEngine", patient_id_hash, f"summary failed: {e}")
                ai_summary = ""

            # ALWAYS define normalized_excerpt for the UI
            normalized_excerpt = ai_summary or (normalized_text or full_text or "")

            # 4) Optional KB retrieval (never fail if KB is offline)
            kb_hits: List[Dict] = []
            try:
                from . import kb_chroma as kb
                if hasattr(kb, "query"):
                    kb_hits = kb.query("cardiac surgery referral criteria and ACS triage", k=3) or []
            except Exception as e:
                self.logger.log_error("KB", patient_id_hash, f"kb retrieval failed: {e}")
                kb_hits = []

            # 5) Recommendation (Claude if available; else safe heuristic)
            try:
                recommendation: Dict = self.engine.generate_recommendation(
                    text_for_ai or normalized_excerpt, context_snippets=kb_hits
                )
            except Exception as e:
                self.logger.log_error("RecEngine", patient_id_hash, f"recommendation failed: {e}")
                recommendation = self.engine.fallback_recommendation(text_for_ai or normalized_excerpt)

            # 6) Return structured result
            result: Dict[str, Union[bool, Dict, str, List]] = {
                "success": True,
                "normalized_excerpt": normalized_excerpt,   # shown as “Letter summary”
                "patient_data": patient_meta,
                "recommendation": recommendation,
            }
            return result

        except Exception as exc:
            # Any unexpected pipeline error — log and return a clear message
            self.logger.log_error("MedicalDocumentProcessor", patient_id_hash, str(exc))
            return {
                "success": False,
                "error": "An internal error occurred.",
                "patient_data": patient_meta
            }
