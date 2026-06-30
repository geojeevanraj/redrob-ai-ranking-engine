"""Job Intelligence layer.

Converts a job description (clean text from a CanonicalDocument) into a
validated, reusable `JobProfile` via the shared LLM Manager.
"""

from app.jobs.engine import JobExtractionError, JobIntelligenceEngine
from app.jobs.schema import JobProfile

__all__ = [
    "JobExtractionError",
    "JobIntelligenceEngine",
    "JobProfile",
]
