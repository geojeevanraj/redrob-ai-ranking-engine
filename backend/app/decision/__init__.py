"""Decision Intelligence layer.

Deterministic, evidence-backed candidate-vs-job hiring recommendations with
configurable, role-aware weighting. The LLM only verifies + explains.
"""

from app.decision.engine import DecisionConfig, DecisionIntelligenceEngine, load_decision_config
from app.decision.model import DecisionProfile, Recommendation, ScoreComponent

__all__ = [
    "DecisionConfig",
    "DecisionIntelligenceEngine",
    "DecisionProfile",
    "Recommendation",
    "ScoreComponent",
    "load_decision_config",
]
