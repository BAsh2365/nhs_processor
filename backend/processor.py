# backend/processor.py - UPDATED

import os
from typing import Optional, Dict, List
from .anonymizer import Anonymizer
from .pdf_processor import PDFProcessor
from .recommendation import ClinicalRecommendationEngine
from .risk_assessor import CardiovascularRiskAssessor
try:
    from . import kb_chroma as kb
except ImportError:
    import kb_chroma as kb

class MedicalDocumentProcessor:
    """
    Main processor for NHS medical documents
    Uses local models - NHS compliant, no external APIs
    """
    
    def __init__(self, user_id: str = "DEFAULT_USER", use_gpu: bool = None):
        """
        Initialize the processor with local models only
        
        Args:
            user_id: Identifier for audit logging
            use_gpu: Whether to use GPU (None = auto-detect)
        """
        self.user_id = user_id
        self.anonymizer = Anonymizer()
        
        # Initialize local model engine (no API key needed!)
        print("[NHS-AI] Initializing local medical models...")
        self.engine = ClinicalRecommendationEngine(use_gpu=use_gpu)
        
        # Initialize risk assessor
        self.risk_assessor = CardiovascularRiskAssessor()
        
        print("[NHS-AI] Processor ready with local models")
    
    def process_document(self, pdf_path: str) -> Dict:
        """
        Process a medical referral document
        
        Args:
            pdf_path: Path to the PDF document
            
        Returns:
            Dictionary containing processed results
        """
        try:
            # 1. Extract text from PDF
            print(f"[NHS-AI] Extracting text from: {pdf_path}")
            text = PDFProcessor.extract_text_from_pdf(pdf_path)
            
            if not text or len(text.strip()) < 50:
                raise ValueError("Insufficient text extracted from PDF")
            
            print(f"[NHS-AI] Extracted {len(text)} characters")
            
            # 2. Anonymize the text
            print("[NHS-AI] Anonymizing patient data...")
            anonymized_text, patient_hash = self.anonymizer.anonymize(text)
            
            # 3. Query knowledge base for relevant context
            print("[NHS-AI] Querying knowledge base...")
            kb_results = kb.query(anonymized_text, k=3)
            
            # 4. Risk assessment
            print("[NHS-AI] Assessing clinical risk...")
            urgency, red_flags = self.risk_assessor.assess_urgency(anonymized_text)
            
            # 5. Generate clinical summary
            print("[NHS-AI] Generating clinical summary...")
            summary = self.engine.summarize(
                anonymized_text, 
                max_words=150, 
                style="exec"
            )
            
            # 6. Generate recommendation
            print("[NHS-AI] Generating clinical recommendation...")
            recommendation = self.engine.generate_recommendation(
                anonymized_text,
                context_snippets=kb_results
            )
            
            # 7. Combine results
            result = {
                "status": "success",
                "patient_id_hash": patient_hash,
                "summary": summary,
                "risk_assessment": {
                    "urgency": urgency,
                    "red_flags": red_flags
                },
                "recommendation": recommendation,
                "knowledge_base_refs": len(kb_results),
                "text_length": len(text),
                "processing_notes": [
                    "Processed using local NHS-compliant models",
                    "No external API calls made",
                    "Patient data anonymized before processing"
                ]
            }
            
            # Audit log (only hash, no PII)
            print(f"[AUDIT] Processed document for patient hash: {patient_hash[:16]}...")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Processing failed: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "status": "error",
                "error": str(e),
                "details": "Document processing failed"
            }
    
    def process_text(self, text: str) -> Dict:
        """
        Process raw text (for testing or text file uploads)
        
        Args:
            text: Raw medical text
            
        Returns:
            Dictionary containing processed results
        """
        try:
            if not text or len(text.strip()) < 50:
                raise ValueError("Insufficient text provided")
            
            # Anonymize
            anonymized_text, patient_hash = self.anonymizer.anonymize(text)
            
            # Query KB
            kb_results = kb.query(anonymized_text, k=3)
            
            # Risk assessment
            urgency, red_flags = self.risk_assessor.assess_urgency(anonymized_text)
            
            # Generate summary
            summary = self.engine.summarize(anonymized_text, max_words=150)
            
            # Generate recommendation
            recommendation = self.engine.generate_recommendation(
                anonymized_text,
                context_snippets=kb_results
            )
            
            result = {
                "status": "success",
                "patient_id_hash": patient_hash,
                "summary": summary,
                "risk_assessment": {
                    "urgency": urgency,
                    "red_flags": red_flags
                },
                "recommendation": recommendation,
                "knowledge_base_refs": len(kb_results)
            }
            
            print(f"[AUDIT] Processed text for patient hash: {patient_hash[:16]}...")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Text processing failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }