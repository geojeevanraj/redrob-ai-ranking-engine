"""Hidden Skill Inference layer.

The Knowledge Graph proposes evidence-backed skill inferences; the LLM verifies
them. Output is an evidence-traceable `HiddenSkillProfile`.
"""

from app.hidden_skills.engine import HiddenSkillConfig, HiddenSkillError, HiddenSkillInferenceEngine
from app.hidden_skills.model import HiddenSkill, HiddenSkillProfile

__all__ = [
    "HiddenSkill",
    "HiddenSkillConfig",
    "HiddenSkillError",
    "HiddenSkillInferenceEngine",
    "HiddenSkillProfile",
]
