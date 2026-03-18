import os
import json
from datetime import datetime
from typing import Any, Optional

class NHSComplianceLogger:
    """Audit logging to support DTAC (traceability, tamper-evidence via append-only daily files)."""

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(__file__), 'audit_logs')
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, f"audit_{datetime.now().strftime('%Y%m%d')}.log")

    def _write(self, payload: dict) -> None:
        # Minimal append-only log (infra should lock down perms / rotate / hash externally)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def log_access(self, action: str, patient_id_hash: str, user_id: str, details: str = "") -> None:
        self._write({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "patient_id_hash": patient_id_hash,
            "user_id": user_id,
            "details": details
        })

    def log_recommendation(self, patient_id_hash: str, recommendation: Any) -> None:
        self._write({
            "timestamp": datetime.now().isoformat(),
            "action": "CLINICAL_RECOMMENDATION",
            "patient_id_hash": patient_id_hash,
            "recommendation": recommendation
        })

    def log_error(self, where: str, patient_id_hash: str, error: str) -> None:
        self._write({
            "timestamp": datetime.now().isoformat(),
            "action": "ERROR",
            "component": where,
            "patient_id_hash": patient_id_hash,
            "error": error
        })
