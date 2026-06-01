"""Canonical JSON and text hashing utilities.

Reused verbatim from the sibling ClinClaw/EMEX project (proven pattern: deterministic
canonical-JSON hashing for provenance and trace chaining).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_json(value: Any) -> str:
    return hash_text(canonical_json(value))
