"""Explainability layer.

Turns deterministic hiring decisions into transparent, evidence-backed
explanations and candidate comparisons. The LLM only improves readability.
"""

from app.explainability.engine import ExplainabilityEngine
from app.explainability.model import (
    ComparisonProfile,
    ExplanationProfile,
    SkillGap,
    Strength,
    Weakness,
)

__all__ = [
    "ComparisonProfile",
    "ExplainabilityEngine",
    "ExplanationProfile",
    "SkillGap",
    "Strength",
    "Weakness",
]
