# backend/anonymizer.py - FIXED

import re
import hashlib
from typing import Tuple

def anonymize_text(text: str) -> Tuple[str, str]:
    """
    Anonymize patient identifiable information in text
    
    Args:
        text: Input text containing patient information
        
    Returns:
        Tuple of (anonymized_text, patient_id_hash)
    """
    anonymized = text
    patient_id = "UNKNOWN"
    
    # Try multiple patterns to extract patient ID
    
    # Pattern 1: NHS Number
    nhs_match = re.search(r'NHS\s*Number:?\s*(\d{3}\s*\d{3}\s*\d{4})', text, re.IGNORECASE)
    if nhs_match:
        patient_id = nhs_match.group(1).replace(' ', '')
        print(f"[Anonymizer] Found NHS Number: {patient_id[:3]}***{patient_id[-3:]}")
    
    # Pattern 2: Patient Name
    if patient_id == "UNKNOWN":
        name_patterns = [
            r'Patient\s*Name:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'Patient:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'Name:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                patient_id = name_match.group(1).strip()
                print(f"[Anonymizer] Found Name: {patient_id}")
                break
    
    # Pattern 3: Use first line if still unknown
    if patient_id == "UNKNOWN":
        first_lines = text.split('\n')[:5]
        for line in first_lines:
            line = line.strip()
            if len(line) > 10 and len(line) < 100:
                # Use first substantial line as ID
                patient_id = line[:50]  # Limit length
                print(f"[Anonymizer] Using first line as ID: {patient_id[:20]}...")
                break
    
    # Anonymize the text by replacing identifiable information
    # Replace NHS numbers
    anonymized = re.sub(r'NHS\s*Number:?\s*\d{3}\s*\d{3}\s*\d{4}', 'NHS Number: [REDACTED]', anonymized, flags=re.IGNORECASE)
    
    # Replace names (common patterns)
    anonymized = re.sub(r'Patient\s*Name:?\s*[A-Z][a-z]+\s+[A-Z][a-z]+', 'Patient Name: [REDACTED]', anonymized, flags=re.IGNORECASE)
    anonymized = re.sub(r'Name:?\s*[A-Z][a-z]+\s+[A-Z][a-z]+', 'Name: [REDACTED]', anonymized, flags=re.IGNORECASE)
    
    # Replace dates of birth
    anonymized = re.sub(r'DOB:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', 'DOB: [REDACTED]', anonymized, flags=re.IGNORECASE)
    anonymized = re.sub(r'Date of Birth:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', 'Date of Birth: [REDACTED]', anonymized, flags=re.IGNORECASE)
    
    # Replace addresses (basic pattern)
    anonymized = re.sub(r'Address:?\s*[^\n]+', 'Address: [REDACTED]', anonymized, flags=re.IGNORECASE)
    
    # Replace phone numbers
    anonymized = re.sub(r'(?:Phone|Tel|Mobile):?\s*[\d\s()-]+', 'Phone: [REDACTED]', anonymized, flags=re.IGNORECASE)
    
    # Replace email addresses
    anonymized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL REDACTED]', anonymized)
    
    # Replace postcodes (UK format)
    anonymized = re.sub(r'\b[A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2}\b', '[POSTCODE REDACTED]', anonymized, flags=re.IGNORECASE)
    
    # Hash the patient ID for logging
    patient_hash = hash_patient_id(patient_id)
    
    print(f"[Anonymizer] Anonymization complete. Patient hash: {patient_hash[:16]}...")
    
    return anonymized, patient_hash


def hash_patient_id(patient_id: str) -> str:
    """
    Create SHA-256 hash of patient ID for audit logging
    
    Args:
        patient_id: Patient identifier
        
    Returns:
        SHA-256 hash as hex string
    """
    return hashlib.sha256(patient_id.encode()).hexdigest()


# Legacy class for backwards compatibility
class Anonymizer:
    """Legacy class wrapper for anonymization functions"""
    
    @staticmethod
    def anonymize(text: str) -> Tuple[str, str]:
        """Legacy method - calls anonymize_text"""
        return anonymize_text(text)
    
    @staticmethod
    def hash_id(patient_id: str) -> str:
        """Legacy method - calls hash_patient_id"""
        return hash_patient_id(patient_id)