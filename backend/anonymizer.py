import re
import hashlib

# NHS number validation (Mod 11 on first 9 digits, 10th is check digit)
_NHS_RE = re.compile(r"\b(\d{3})\s?(\d{3})\s?(\d{4})\b")

def _nhs_is_valid(n: str) -> bool:
    s = re.sub(r"\s+", "", n)
    if not re.fullmatch(r"\d{10}", s):
        return False
    weights = [10,9,8,7,6,5,4,3,2]
    total = sum(int(d)*w for d, w in zip(s[:9], weights))
    check = 11 - (total % 11)
    if check == 11:
        check = 0
    if check == 10:
        return False
    return check == int(s[9])

class DataAnonymizer:
    """Handles patient data anonymization and PII redaction suitable for UK clinical docs."""

    @staticmethod
    def hash_patient_id(patient_id: str) -> str:
        """Create irreversible hash of patient identifier"""
        return hashlib.sha256(patient_id.encode("utf-8")).hexdigest()

    @staticmethod
    def redact_pii(text: str) -> str:
        """Redact common UK PII before any LLM/vectorisation step."""

        def _mask_nhs(m):
            g = "".join(m.groups())
            return "[NHS_NUMBER_REDACTED]" if _nhs_is_valid(g) else m.group(0)

        # NHS numbers with checksum
        text = _NHS_RE.sub(_mask_nhs, text)

        # UK postcodes (broad pattern, case-insensitive)
        text = re.sub(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", "[POSTCODE_REDACTED]", text, flags=re.I)

        # Phone numbers (0x... and +44... mobile/landline)
        text = re.sub(r"\b(?:\+44\s?\d{3,4}|\(?0\)?\s?\d{3,4})\s?\d{3}\s?\d{3,4}\b", "[PHONE_REDACTED]", text)

        # Emails
        text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[EMAIL_REDACTED]", text, flags=re.I)

        # DOB / dates (common UK formats)
        text = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "[DATE_REDACTED]", text)

        # Titles + likely names (simple heuristic)
        text = re.sub(r"\b(Mr|Mrs|Ms|Miss|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", "[NAME_REDACTED]", text)

        return text
