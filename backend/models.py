from dataclasses import dataclass, asdict
from typing import List

@dataclass
class PatientData:
    """Anonymized patient data structure"""
    patient_id_hash: str
    processing_date: str
    document_type: str

    def to_dict(self):
        return asdict(self)

@dataclass
class ClinicalRecommendation:
    """Clinical pathway recommendation structure"""
    recommendation_type: str
    urgency: str
    reasoning: str
    confidence_level: str
    red_flags: List[str]
    suggested_timeframe: str
    evidence_basis: str

    def to_dict(self):
        return asdict(self)
