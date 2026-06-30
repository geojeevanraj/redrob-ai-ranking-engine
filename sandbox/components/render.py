"""Presentation helpers for ranking results.

These functions ONLY format values already computed by the backend ranking
engine (rank, score, reasoning). No ranking, sorting, or scoring happens here.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pandas as pd
import streamlit as st


def render_results(result: dict[str, Any]) -> None:
    """Render the ranking summary metrics and the Top-N table."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Candidates processed", f"{result.get('total_candidates', 0):,}")
    col2.metric("Returned", result.get("returned", 0))
    col3.metric("Weighting profile", result.get("weighting_profile", "—"))
    col4.metric("Engine time (s)", result.get("elapsed_seconds", "—"))

    rows = result.get("top", [])
    if not rows:
        st.warning("The ranking returned no candidates.")
        return

    table = [
        {
            "Rank": r.get("rank"),
            "Candidate ID": r.get("candidate_id"),
            "Score": f"{r.get('score', 0):.4f}",
            "Reasoning": r.get("reasoning", ""),
        }
        for r in rows
    ]
    df = pd.DataFrame(table)
    st.dataframe(df, use_container_width=True, hide_index=True)


def results_to_csv(result: dict[str, Any]) -> str:
    """Serialize the backend-computed Top-N into the official 4-column CSV.

    This mirrors the backend's CSV format exactly (candidate_id, rank, score
    with 4 decimals, reasoning). It is a pure serialization of values the
    backend already produced — no business logic.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])
    for r in result.get("top", []):
        writer.writerow(
            [r.get("candidate_id"), r.get("rank"), f"{r.get('score', 0):.4f}", r.get("reasoning", "")]
        )
    return buf.getvalue()
