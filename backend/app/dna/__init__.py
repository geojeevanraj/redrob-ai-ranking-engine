"""Candidate DNA layer.

Deterministic, evidence-based professional fingerprinting. The scoring engine
computes archetype affinities from observable technical evidence; the LLM only
verifies consistency and summarizes. No personality inference.
"""

from app.dna.engine import ArchetypeRule, CandidateDNAEngine, DNAConfig, load_archetypes
from app.dna.model import ArchetypeScore, CandidateDNA

__all__ = [
    "ArchetypeRule",
    "ArchetypeScore",
    "CandidateDNA",
    "CandidateDNAEngine",
    "DNAConfig",
    "load_archetypes",
]
