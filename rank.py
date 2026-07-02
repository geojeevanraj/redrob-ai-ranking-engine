#!/usr/bin/env python3
"""Standalone reproduce command for the Redrob AI Ranking Engine.

Usage (fully offline, CPU-only, no database, no network):
    python rank.py \\
        --candidates dataset/candidates.jsonl \\
        --job-profile dataset/job_profile.json \\
        --out submission.csv

Usage (parse a fresh JD first — requires GEMINI_API_KEY, run once):
    python rank.py --parse-jd \\
        --jd dataset/job_description.docx \\
        --job-profile dataset/job_profile.json

Constraints verified: ≤5 min · ≤16 GB RAM · CPU-only · zero LLM calls during ranking.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure stdout/stderr are UTF-8 on all platforms (including Windows cmd/ps).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Make the repo root importable (same mechanism as backend/app/__init__.py).
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_ROOT / "backend"))


def _load_engines():
    """Build the deterministic engine stack (KG, hidden skills, DNA, decision, behavioral)."""
    from app.decision.engine import DecisionIntelligenceEngine, load_decision_config
    from app.dna.engine import CandidateDNAEngine, DNAConfig, load_archetypes
    from app.hidden_skills.engine import HiddenSkillInferenceEngine
    from app.knowledge import load_seed_graph
    from app.ranking.behavioral_engine import BehavioralIntelligenceEngine, load_behavior_weights
    from app.ranking.ranking_engine import OfflineRankingEngine, load_ranking_config

    print("[rank] loading knowledge graph…", flush=True)
    graph = load_seed_graph()

    # Stub LLM/Prompt (never called in the deterministic ranking path).
    class _NoLLM:
        async def generate_json(self, *a, **kw):
            raise RuntimeError("LLM must not be called during ranking")

    class _NoPrompt:
        def get(self, *a, **kw):
            return ""

    llm = _NoLLM()
    prompt = _NoPrompt()

    decision = DecisionIntelligenceEngine(graph, llm, prompt, config=load_decision_config())
    hidden = HiddenSkillInferenceEngine(graph, llm, prompt)
    dna = CandidateDNAEngine(
        graph, llm, prompt, config=DNAConfig(archetypes=load_archetypes())
    )
    behavioral = BehavioralIntelligenceEngine(config=load_behavior_weights())
    config = load_ranking_config()
    return OfflineRankingEngine(
        decision_engine=decision,
        hidden_engine=hidden,
        dna_engine=dna,
        behavioral_engine=behavioral,
        config=config,
    )


def cmd_rank(args: argparse.Namespace) -> None:
    """Stream candidates.jsonl and produce a ranked submission CSV."""
    candidates_path = Path(args.candidates)
    job_profile_path = Path(args.job_profile)
    out_path = Path(args.out)

    if not candidates_path.exists():
        sys.exit(f"[rank] ERROR: candidates file not found: {candidates_path}")
    if not job_profile_path.exists():
        sys.exit(f"[rank] ERROR: job profile not found: {job_profile_path}")

    from app.jobs.schema import JobProfile
    from app.ranking.csv_export import write_ranking_csv
    from app.ranking.dataset_loader import stream_profiles

    print(f"[rank] loading job profile from {job_profile_path}…", flush=True)
    job = JobProfile.model_validate(json.loads(job_profile_path.read_text(encoding="utf-8")))
    print(f"[rank] job: {job.job_metadata.job_title}", flush=True)

    engine = _load_engines()

    total_lines = sum(1 for ln in candidates_path.open(encoding="utf-8") if ln.strip())
    print(f"[rank] streaming {total_lines:,} candidates…", flush=True)

    t0 = time.perf_counter()
    ranked, total, profile = engine.rank(
        stream_profiles(candidates_path),
        job,
        top_n=args.top_n,
        role_profile=args.role_profile or None,
    )
    elapsed = time.perf_counter() - t0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = write_ranking_csv(ranked, out_path)
    print(
        f"[rank] done — {total:,} processed · {len(ranked)} returned · "
        f"{elapsed:.1f}s · profile={profile}",
        flush=True,
    )
    print(f"[rank] wrote {written}", flush=True)


def cmd_parse_jd(args: argparse.Namespace) -> None:
    """One-time JD parsing via Gemini → saves job_profile.json.

    This is PRE-COMPUTATION (allowed to use the network). Run once, commit the
    resulting job_profile.json, then use --job-profile in all future rank runs.
    """
    import asyncio

    from app.config import get_settings
    from app.documents.engine import DocumentIntelligenceEngine
    from app.jobs.engine import JobIntelligenceEngine

    # DI without FastAPI — build engines directly from settings.
    from typing import cast

    from app.candidates.engine import LLMManagerLike, PromptManagerLike

    settings = get_settings()
    jd_path = Path(args.jd)
    out_path = Path(args.job_profile)

    if not jd_path.exists():
        sys.exit(f"[rank] ERROR: JD file not found: {jd_path}")

    from ai.llm.manager import LLMManager
    from ai.prompts import PromptManager

    llm = cast(LLMManagerLike, LLMManager.from_settings())
    prompts = cast(PromptManagerLike, PromptManager())
    doc_engine = DocumentIntelligenceEngine()
    job_engine = JobIntelligenceEngine(llm, prompts)

    print(f"[rank] parsing JD: {jd_path}", flush=True)
    raw = jd_path.read_bytes()
    canonical = doc_engine.process(
        content=raw,
        filename=jd_path.name,
        content_type="",
        document_type="job_description",
    )

    async def _run():
        return await job_engine.parse(canonical.clean_text)

    profile = asyncio.run(_run())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    print(f"[rank] wrote job profile to {out_path}", flush=True)
    print(f"[rank] title: {profile.job_metadata.job_title}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Redrob AI Ranking Engine — standalone reproduce command",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd")

    # Default: just run ranking (no subcommand needed for the reproduce command).
    parser.add_argument("--candidates", default="dataset/candidates.jsonl",
                        help="Path to candidates JSONL file")
    parser.add_argument("--job-profile", default="dataset/job_profile.json",
                        help="Path to pre-parsed job profile JSON")
    parser.add_argument("--out", default="submission.csv",
                        help="Output CSV path")
    parser.add_argument("--top-n", type=int, default=100,
                        help="Number of candidates to return (default: 100)")
    parser.add_argument("--role-profile", default=None,
                        help="Override role weighting profile (e.g. ai_engineer)")
    parser.add_argument("--parse-jd", action="store_true",
                        help="Parse a fresh JD via Gemini (pre-computation, requires API key)")
    parser.add_argument("--jd", default="dataset/job_description.docx",
                        help="JD file to parse (used with --parse-jd)")

    args = parser.parse_args()

    if args.parse_jd:
        cmd_parse_jd(args)
    else:
        cmd_rank(args)


if __name__ == "__main__":
    main()
