"""Recommender package: OE + dotflows behind a swappable abstraction.

The moat is the dotflows / workflow / validated data — not the inference, and not the (licensed)
criteria. OpenEvidence is the intended engine but must be mockable and replaceable; never hardcode
a hard dependency on it (goal hard rule #5).
"""

from .base import Recommendation, Recommender, RecommendedAction
from .mock_oe import MockOpenEvidenceRecommender

__all__ = ["Recommendation", "Recommender", "RecommendedAction", "MockOpenEvidenceRecommender"]
