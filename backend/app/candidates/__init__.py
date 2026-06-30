"""Candidate Intelligence layer.

Converts a resume (clean text from a CanonicalDocument) into a validated,
reusable `CandidateProfile` via the shared LLM Manager.
"""

from app.candidates.engine import CandidateExtractionError, CandidateIntelligenceEngine
from app.candidates.schema import CandidateProfile

__all__ = [
    "CandidateExtractionError",
    "CandidateIntelligenceEngine",
    "CandidateProfile",
]
