# backend/processor.py

from typing import Optional, Dict, List
from .anonymizer import Anonymizer, anonymize_text
from .clinical_extractor import ClinicalDataExtractor
from .pdf_processor import PDFProcessor
from .recommendation import ClinicalRecommendationEngine
from .risk_assessor import CardiovascularRiskAssessor
from .config_loader import load_framework
from .logger import NHSComplianceLogger
try:
    from . import kb_chroma as kb
except ImportError:
    import kb_chroma as kb


class MedicalDocumentProcessor:
    """
    Main processor for medical documents.
    Uses local models — compliant, no external APIs.
    Supports multi-framework configuration.
    """

    def __init__(self, user_id: str = "DEFAULT_USER", use_gpu: bool = None,
                 framework_id: str = "nhs_uk", scopes: Optional[List[str]] = None):
        """
        Initialize the processor with local models only.

        Args:
            user_id: Identifier for audit logging
            use_gpu: Whether to use GPU (None = auto-detect)
            framework_id: Framework config to load (default: nhs_uk)
            scopes: Optional scope overlays (e.g. ["congenital_achd"])
        """
        self.user_id = user_id
        self.framework_id = framework_id
        self.scopes = scopes or []
        self._logger = NHSComplianceLogger()

        # Load merged config
        self.config = load_framework(framework_id, scopes=self.scopes)
        framework_name = self.config.get("name", framework_id)
        print(f"[AI] Loading framework: {framework_name}")
        if self.scopes:
            print(f"[AI] Active scopes: {', '.join(self.scopes)}")

        self.anonymizer = Anonymizer(config=self.config)
        self.clinical_extractor = ClinicalDataExtractor()

        # Initialize local model engine
        print("[AI] Initializing local medical models...")
        self.engine = ClinicalRecommendationEngine(use_gpu=use_gpu, config=self.config)

        # Initialize risk assessor
        self.risk_assessor = CardiovascularRiskAssessor(config=self.config)

        # Resolve KB collections from config
        self._kb_collections = self.config.get("kb_collections", ["nhs_kb"])

        # Resolve embedding model from config
        self._embed_model_id = self.config.get("models", {}).get("embeddings", {}).get("model_id")

        print(f"[AI] Processor ready ({framework_name})")

    def process_document(self, pdf_path: str) -> Dict:
        """
        Process a medical referral document.
        """
        try:
            print(f"[AI] Extracting text from: {pdf_path}")
            text = PDFProcessor.extract_text_from_pdf(pdf_path)

            if not text or len(text.strip()) < 50:
                raise ValueError("Insufficient text extracted from PDF")

            print(f"[AI] Extracted {len(text)} characters")

            # Extract structured clinical data BEFORE anonymization
            # (demographics, vitals, blood tests, medications, scores)
            print("[AI] Extracting structured clinical data...")
            clinical_data = self.clinical_extractor.extract_all(text)

            # Anonymize
            print("[AI] Anonymizing patient data...")
            anonymized_text, patient_hash = anonymize_text(text, config=self.config)

            # Query knowledge base across configured collections
            print("[AI] Querying knowledge base...")
            kb_results = kb.query(
                anonymized_text, k=3,
                collections=self._kb_collections,
                embed_model_id=self._embed_model_id
            )

            # Risk assessment
            print("[AI] Assessing clinical risk...")
            urgency, red_flags = self.risk_assessor.assess_urgency(anonymized_text)

            # Generate clinical summary
            print("[AI] Generating clinical summary...")
            summary = self.engine.summarize(
                anonymized_text,
                max_words=150,
                style="exec"
            )

            # Generate recommendation
            print("[AI] Generating clinical recommendation...")
            recommendation = self.engine.generate_recommendation(
                anonymized_text,
                context_snippets=kb_results
            )

            framework_name = self.config.get("name", self.framework_id)
            result = {
                "status": "success",
                "patient_id_hash": patient_hash,
                "summary": summary,
                "clinical_data": clinical_data,
                "risk_assessment": {
                    "urgency": urgency,
                    "red_flags": red_flags
                },
                "recommendation": recommendation,
                "knowledge_base_refs": len(kb_results),
                "text_length": len(text),
                "framework": framework_name,
                "processing_notes": [
                    f"Processed using {framework_name} framework with local models",
                    "No external API calls made",
                    "Patient data anonymized before processing"
                ]
            }

            self._logger.log_access(
                action="DOCUMENT_PROCESSED",
                patient_id_hash=patient_hash,
                user_id=self.user_id,
                details=f"framework={framework_name}, text_len={len(text)}"
            )
            self._logger.log_recommendation(
                patient_id_hash=patient_hash,
                recommendation=recommendation
            )
            print(f"[AUDIT] Processed document for patient hash: {patient_hash[:16]}...")
            return result

        except Exception as e:
            print(f"[ERROR] Processing failed: {e}")
            import traceback
            traceback.print_exc()
            self._logger.log_error(
                where="process_document",
                patient_id_hash="unknown",
                error=str(e)
            )

            return {
                "status": "error",
                "error": "An internal error has occurred.",
                "details": "Document processing failed"
            }

    def process_text(self, text: str) -> Dict:
        """
        Process raw text (for testing or text file uploads).
        """
        try:
            if not text or len(text.strip()) < 50:
                raise ValueError("Insufficient text provided")

            clinical_data = self.clinical_extractor.extract_all(text)
            anonymized_text, patient_hash = anonymize_text(text, config=self.config)

            kb_results = kb.query(
                anonymized_text, k=3,
                collections=self._kb_collections,
                embed_model_id=self._embed_model_id
            )

            urgency, red_flags = self.risk_assessor.assess_urgency(anonymized_text)
            summary = self.engine.summarize(anonymized_text, max_words=150)
            recommendation = self.engine.generate_recommendation(
                anonymized_text,
                context_snippets=kb_results
            )

            framework_name = self.config.get("name", self.framework_id)
            result = {
                "status": "success",
                "patient_id_hash": patient_hash,
                "summary": summary,
                "clinical_data": clinical_data,
                "risk_assessment": {
                    "urgency": urgency,
                    "red_flags": red_flags
                },
                "recommendation": recommendation,
                "knowledge_base_refs": len(kb_results),
                "framework": framework_name
            }

            self._logger.log_access(
                action="TEXT_PROCESSED",
                patient_id_hash=patient_hash,
                user_id=self.user_id,
                details=f"framework={framework_name}"
            )
            self._logger.log_recommendation(
                patient_id_hash=patient_hash,
                recommendation=recommendation
            )
            print(f"[AUDIT] Processed text for patient hash: {patient_hash[:16]}...")
            return result

        except Exception as e:
            print(f"[ERROR] Text processing failed: {e}")
            self._logger.log_error(
                where="process_text",
                patient_id_hash="unknown",
                error=str(e)
            )
            return {
                "status": "error",
                "error": "An internal error has occurred."
            }
