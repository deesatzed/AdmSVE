"""OE prose ingestion (steps 5-6): parse OpenEvidence's PROSE answer (NO JSON).

OE dotflows live inside OpenEvidence and are triggered there (e.g. `.ed_xxx`); OE returns natural
clinical prose. This module maps that prose into the Recommendation shape the engine consumes,
PRESERVES the raw prose verbatim (hashed) for audit, and flags `needs_review` when it cannot parse
confidently — it never fabricates structure.
"""

from .parser import ParsedOeOutput, parse_oe_prose

__all__ = ["ParsedOeOutput", "parse_oe_prose"]
