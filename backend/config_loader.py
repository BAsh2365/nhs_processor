# backend/config_loader.py
"""
Configuration loading and merging for multi-framework support.
Loads framework JSON configs and merges optional scope overlays.
"""

import os
import json
import re
from typing import Optional

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
_FRAMEWORKS_DIR = os.path.join(_CONFIG_DIR, "frameworks")
_SCOPES_DIR = os.path.join(_CONFIG_DIR, "scopes")

# In-memory cache keyed by (framework_id, tuple(scopes))
_cache: dict = {}


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _validate_patterns(config: dict) -> None:
    """Validate that all regex patterns in the config compile without errors."""
    patterns = config.get("clinical_terms", {}).get("emergency_patterns", [])
    for pat in patterns:
        try:
            re.compile(pat)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{pat}': {e}")

    for key, pii in config.get("pii_patterns", {}).items():
        if isinstance(pii, dict) and "pattern" in pii:
            try:
                re.compile(pii["pattern"])
            except re.error as e:
                raise ValueError(f"Invalid PII regex '{key}': {e}")


def _merge_scope(base: dict, scope: dict) -> dict:
    """Merge a scope overlay into a base config by appending _additional lists."""
    ct = base.get("clinical_terms", {})

    if "red_flags_additional" in scope:
        ct["red_flags"] = ct.get("red_flags", []) + scope["red_flags_additional"]
    if "surgical_indicators_additional" in scope:
        ct["surgical_indicators"] = ct.get("surgical_indicators", []) + scope["surgical_indicators_additional"]
    if "emergency_patterns_additional" in scope:
        ct["emergency_patterns"] = ct.get("emergency_patterns", []) + scope["emergency_patterns_additional"]

    base["clinical_terms"] = ct

    if "kb_collections_additional" in scope:
        base["kb_collections"] = base.get("kb_collections", []) + scope["kb_collections_additional"]

    if "achd_considerations" in scope:
        base["achd_considerations"] = scope["achd_considerations"]

    if "fallback_signals" in scope:
        base["fallback_signals"] = scope["fallback_signals"]

    # Track active scopes
    base.setdefault("active_scopes", []).append(scope.get("id", "unknown"))

    return base


def load_framework(framework_id: str = "nhs_uk", scopes: Optional[list] = None) -> dict:
    """
    Load a framework config and optionally merge scope overlays.

    Args:
        framework_id: Framework identifier (e.g. "nhs_uk", "us_aha")
        scopes: Optional list of scope IDs to merge (e.g. ["congenital_achd"])

    Returns:
        Merged configuration dict
    """
    cache_key = (framework_id, tuple(scopes or []))
    if cache_key in _cache:
        return _cache[cache_key]

    framework_path = os.path.join(_FRAMEWORKS_DIR, f"{framework_id}.json")
    if not os.path.isfile(framework_path):
        raise FileNotFoundError(f"Framework config not found: {framework_path}")

    config = _load_json(framework_path)

    if scopes:
        for scope_id in scopes:
            scope_path = os.path.join(_SCOPES_DIR, f"{scope_id}.json")
            if not os.path.isfile(scope_path):
                raise FileNotFoundError(f"Scope config not found: {scope_path}")
            scope_data = _load_json(scope_path)
            config = _merge_scope(config, scope_data)

    _validate_patterns(config)
    _cache[cache_key] = config
    return config


def list_frameworks() -> list:
    """Return list of available framework IDs."""
    if not os.path.isdir(_FRAMEWORKS_DIR):
        return []
    return [
        f.replace(".json", "")
        for f in sorted(os.listdir(_FRAMEWORKS_DIR))
        if f.endswith(".json")
    ]


def list_scopes() -> list:
    """Return list of available scope IDs."""
    if not os.path.isdir(_SCOPES_DIR):
        return []
    return [
        f.replace(".json", "")
        for f in sorted(os.listdir(_SCOPES_DIR))
        if f.endswith(".json")
    ]
