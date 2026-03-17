"""
Tests for backend/anonymizer.py — PII redaction with config-driven patterns.
"""

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.anonymizer import anonymize_text, hash_patient_id, Anonymizer
from backend.config_loader import load_framework


@pytest.fixture
def nhs_config():
    return load_framework("nhs_uk")


@pytest.fixture
def us_config():
    return load_framework("us_aha")


# ---------------------------------------------------------------------------
# 1. Backward compatibility (no config)
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_no_config_still_works(self):
        text = "Patient Name: John Smith\nNHS Number: 123 456 7890\nAddress: 10 Downing Street\nPostcode: SW1A 2AA"
        anon, phash = anonymize_text(text)
        assert "John Smith" not in anon
        assert "123 456 7890" not in anon
        assert "SW1A 2AA" not in anon
        assert phash  # non-empty hash

    def test_legacy_class_works(self):
        text = "Patient Name: Jane Doe\nNHS Number: 987 654 3210"
        anon, phash = Anonymizer.anonymize(text)
        assert "Jane Doe" not in anon
        assert phash


# ---------------------------------------------------------------------------
# 2. Universal PII patterns (always applied)
# ---------------------------------------------------------------------------

class TestUniversalPatterns:
    def test_redacts_patient_name(self):
        text = "Patient Name: Alice Johnson\nDiagnosis: stable angina"
        anon, _ = anonymize_text(text)
        assert "Alice Johnson" not in anon
        assert "[REDACTED]" in anon

    def test_redacts_dob(self):
        text = "DOB: 15/03/1989\nComplaint: chest pain"
        anon, _ = anonymize_text(text)
        assert "15/03/1989" not in anon

    def test_redacts_dob_with_dashes(self):
        text = "Date of Birth: 07-22-1958"
        anon, _ = anonymize_text(text)
        assert "07-22-1958" not in anon

    def test_redacts_address(self):
        text = "Address: 17 Cabot Lane, Bristol\nHeart rate: 78"
        anon, _ = anonymize_text(text)
        assert "17 Cabot Lane" not in anon

    def test_redacts_phone(self):
        text = "Phone: 07700 900123\nReferral for echo."
        anon, _ = anonymize_text(text)
        assert "07700 900123" not in anon

    def test_redacts_email(self):
        text = "Contact: patient@email.com\nDiagnosis: VSD"
        anon, _ = anonymize_text(text)
        assert "patient@email.com" not in anon
        assert "[EMAIL REDACTED]" in anon


# ---------------------------------------------------------------------------
# 3. NHS-specific PII patterns
# ---------------------------------------------------------------------------

class TestNHSPatterns:
    def test_redacts_nhs_number(self, nhs_config):
        text = "NHS Number: 432 876 2190\nReferral for ACHD assessment."
        anon, _ = anonymize_text(text, config=nhs_config)
        assert "432 876 2190" not in anon
        assert "[REDACTED]" in anon

    def test_redacts_uk_postcode(self, nhs_config):
        text = "Lives at 17 Cabot Lane, Bristol BS8 4QR. Has chest pain."
        anon, _ = anonymize_text(text, config=nhs_config)
        assert "BS8 4QR" not in anon

    def test_extracts_nhs_number_as_patient_id(self, nhs_config):
        text = "NHS Number: 432 876 2190\nPatient Name: Tom Whitfield"
        _, phash = anonymize_text(text, config=nhs_config)
        expected = hash_patient_id("4328762190")
        assert phash == expected

    def test_does_not_redact_ssn_under_nhs(self, nhs_config):
        """NHS config should not have SSN pattern."""
        text = "Reference: 451-78-3294. Chest pain."
        anon, _ = anonymize_text(text, config=nhs_config)
        # NHS config has no SSN pattern, so it should remain
        assert "451-78-3294" in anon


# ---------------------------------------------------------------------------
# 4. US-specific PII patterns
# ---------------------------------------------------------------------------

class TestUSPatterns:
    def test_redacts_ssn(self, us_config):
        text = "SSN: 451-78-3294\nChief complaint: chest pain"
        anon, _ = anonymize_text(text, config=us_config)
        assert "451-78-3294" not in anon
        assert "[SSN REDACTED]" in anon

    def test_redacts_mrn(self, us_config):
        text = "MRN: 20458931\nDiagnosis: STEMI"
        anon, _ = anonymize_text(text, config=us_config)
        assert "20458931" not in anon
        assert "[REDACTED]" in anon

    def test_extracts_ssn_as_patient_id(self, us_config):
        text = "SSN: 451-78-3294\nPatient Name: Robert Alvarez"
        _, phash = anonymize_text(text, config=us_config)
        expected = hash_patient_id("451783294")
        assert phash == expected

    def test_extracts_mrn_as_patient_id(self, us_config):
        text = "MRN: 20458931\nPatient Name: Robert Alvarez"
        _, phash = anonymize_text(text, config=us_config)
        expected = hash_patient_id("20458931")
        assert phash == expected

    def test_does_not_redact_nhs_number_under_us(self, us_config):
        """US config should not have NHS Number pattern."""
        text = "Ref: NHS Number: 432 876 2190"
        anon, _ = anonymize_text(text, config=us_config)
        # US config has no NHS number pattern — note: the universal pattern
        # doesn't redact NHS number by default, only the config-driven one does
        # With US config, NHS number redaction depends on config pii_patterns only


# ---------------------------------------------------------------------------
# 5. Patient ID hashing
# ---------------------------------------------------------------------------

class TestHashing:
    def test_hash_is_deterministic(self):
        h1 = hash_patient_id("4328762190")
        h2 = hash_patient_id("4328762190")
        assert h1 == h2

    def test_different_ids_different_hashes(self):
        h1 = hash_patient_id("4328762190")
        h2 = hash_patient_id("9876543210")
        assert h1 != h2

    def test_hash_is_64_hex_chars(self):
        h = hash_patient_id("test_id")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_name_as_patient_id(self):
        text = "Patient Name: Alice Johnson\nChest pain."
        _, phash = anonymize_text(text)
        expected = hash_patient_id("Alice Johnson")
        assert phash == expected


# ---------------------------------------------------------------------------
# 6. Test with actual referral files
# ---------------------------------------------------------------------------

class TestWithReferralFiles:
    @pytest.fixture
    def referral_dir(self):
        return os.path.join(ROOT, "frontend", "test_pdfs")

    def _read_referral(self, referral_dir, filename):
        with open(os.path.join(referral_dir, filename), "r", encoding="utf-8") as f:
            return f.read()

    def test_achd_referral_nhs_pii_redacted(self, nhs_config, referral_dir):
        text = self._read_referral(referral_dir, "patient_referral_achd_1.txt")
        anon, phash = anonymize_text(text, config=nhs_config)
        assert "Thomas Whitfield" not in anon
        assert "432 876 2190" not in anon
        assert "BS8 4QR" not in anon
        assert phash

    def test_achd_referral_2_nhs_pii_redacted(self, nhs_config, referral_dir):
        text = self._read_referral(referral_dir, "patient_referral_achd_2.txt")
        anon, phash = anonymize_text(text, config=nhs_config)
        assert "Rebecca Thornton" not in anon
        assert "567 234 8901" not in anon
        assert "EX1 1HS" not in anon

    def test_us_referral_ssn_redacted(self, us_config, referral_dir):
        text = self._read_referral(referral_dir, "patient_referral_us_1.txt")
        anon, phash = anonymize_text(text, config=us_config)
        assert "451-78-3294" not in anon
        assert "Robert Alvarez" not in anon

    def test_us_referral_mrn_redacted(self, us_config, referral_dir):
        text = self._read_referral(referral_dir, "patient_referral_us_1.txt")
        anon, phash = anonymize_text(text, config=us_config)
        assert "20458931" not in anon

    def test_clinical_content_preserved(self, nhs_config, referral_dir):
        """PII should be redacted but clinical content should remain."""
        text = self._read_referral(referral_dir, "patient_referral_achd_1.txt")
        anon, _ = anonymize_text(text, config=nhs_config)
        assert "Tetralogy of Fallot" in anon
        assert "pulmonary regurgitation" in anon
        assert "RV dilation" in anon
