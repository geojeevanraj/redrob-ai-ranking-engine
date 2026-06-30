"""ORM models package.

Models inherit from `app.db.base.Base` and are imported here so Alembic
autogenerate can discover them.
"""

from app.models.candidate import CandidateProfileRecord
from app.models.decision import DecisionRecord
from app.models.dna import CandidateDNARecord
from app.models.document import DocumentRecord
from app.models.explanation import ExplanationRecord
from app.models.hidden_skill import HiddenSkillProfileRecord
from app.models.job import JobProfileRecord

__all__ = [
    "CandidateDNARecord",
    "CandidateProfileRecord",
    "DecisionRecord",
    "DocumentRecord",
    "ExplanationRecord",
    "HiddenSkillProfileRecord",
    "JobProfileRecord",
]
