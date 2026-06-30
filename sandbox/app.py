"""AI Recruitment Intelligence Platform — Official Sandbox (Streamlit).

A thin, Python-only presentation layer over the existing FastAPI backend. It
orchestrates existing endpoints (document upload, job parsing, offline ranking,
CSV generation) and renders the results. It contains NO ranking, scoring,
parsing, or business logic of its own — everything is delegated to the backend.

Workflow (Sprint 10.3): the official local dataset / job description are used
**in place** by default (their path is passed straight to the backend — no
browser upload). A custom upload remains available when needed.

Run:  streamlit run sandbox/app.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

# Make the project root importable so `sandbox.*` packages resolve when the
# app is launched via `streamlit run sandbox/app.py`.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sandbox.components.render import render_results, results_to_csv  # noqa: E402
from sandbox.utils.api_client import BackendClient, BackendError  # noqa: E402
from sandbox.utils.official import (  # noqa: E402
    count_jsonl_lines,
    human_size,
    official_dataset_path,
    official_jd_path,
)

DEFAULT_BACKEND = os.environ.get("SANDBOX_BACKEND_URL", "http://localhost:8000/api/v1")
ROLE_PROFILES = ["(auto)", "default", "backend_engineer", "ai_engineer", "devops_engineer"]
JD_EXTENSIONS = ["pdf", "docx", "txt"]
JD_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}

st.set_page_config(page_title="AI Recruitment Intelligence Platform", layout="wide")


# ── Session state ───────────────────────────────────────────
def _init_state() -> None:
    st.session_state.setdefault("job_id", None)
    st.session_state.setdefault("job_label", None)
    st.session_state.setdefault("dataset_path", None)
    st.session_state.setdefault("dataset_label", None)
    st.session_state.setdefault("dataset_count", None)
    st.session_state.setdefault("result", None)


def _client() -> BackendClient:
    return BackendClient(st.session_state.get("backend_url", DEFAULT_BACKEND))


# ── Sidebar: backend connection ─────────────────────────────
def sidebar() -> None:
    st.sidebar.header("Backend")
    st.session_state["backend_url"] = st.sidebar.text_input(
        "API base URL", value=st.session_state.get("backend_url", DEFAULT_BACKEND)
    )
    if st.sidebar.button("Check connection"):
        if _client().health():
            st.sidebar.success("Backend is reachable.")
        else:
            st.sidebar.error("Backend is not reachable. Is it running on the URL above?")
    st.sidebar.caption(
        "The sandbox only calls existing backend APIs. Start the backend first:\n\n"
        "`uvicorn app.main:app` (from `backend/`)"
    )


# ── Status panel ────────────────────────────────────────────
def status_panel(backend_ok: bool) -> None:
    ds = official_dataset_path()
    jd = official_jd_path()
    col1, col2, col3 = st.columns(3)
    with col1:
        if ds.exists():
            st.success("Official Dataset ✓ Found")
        else:
            st.error("Official Dataset ✗ Missing")
        st.caption(str(ds))
    with col2:
        if jd.exists():
            st.success("Official Job Description ✓ Found")
        else:
            st.error("Official Job Description ✗ Missing")
        st.caption(str(jd))
    with col3:
        if backend_ok:
            st.success("Backend ✓ Connected")
        else:
            st.error("Backend ✗ Unreachable")
        st.caption(st.session_state.get("backend_url", DEFAULT_BACKEND))


# ── Section 1: Job ──────────────────────────────────────────
def section_job() -> None:
    st.subheader("1 · Job Description")
    mode = st.radio(
        "Job source",
        ["Use Official Job Description", "Upload Custom Job Description"],
        horizontal=True,
        key="job_mode",
    )
    client = _client()

    if mode == "Use Official Job Description":
        jd = official_jd_path()
        if not jd.exists():
            st.error(f"Official job description not found at: {jd}")
            return
        st.markdown(f"**Detected:** `{jd.name}`")
        st.caption(f"Location: {jd}  ·  Size: {human_size(jd.stat().st_size)}")
        if st.button("Parse official job description"):
            try:
                with st.spinner("Parsing the official job description on the backend…"):
                    content = jd.read_bytes()
                    doc = client.upload_document(
                        filename=jd.name,
                        content=content,
                        content_type=JD_MIME.get(jd.suffix.lower(), ""),
                        document_type="job_description",
                    )
                    job = client.parse_job(doc["document"]["id"])
                _store_job(job)
                st.success(f"Parsed job: {st.session_state['job_label']}")
            except BackendError as exc:
                st.error(str(exc))
    else:
        uploaded = st.file_uploader("Upload a JD (PDF, DOCX, or TXT)", type=JD_EXTENSIONS)
        if uploaded is not None and st.button("Upload & parse job description"):
            try:
                with st.spinner("Uploading and parsing the job description…"):
                    doc = client.upload_document(
                        filename=uploaded.name,
                        content=uploaded.getvalue(),
                        content_type=uploaded.type or "",
                        document_type="job_description",
                    )
                    job = client.parse_job(doc["document"]["id"])
                _store_job(job)
                st.success(f"Parsed job: {st.session_state['job_label']}")
            except BackendError as exc:
                st.error(str(exc))

    if st.session_state.get("job_id"):
        st.caption(f"Active job: **{st.session_state['job_label']}**")


def _store_job(job: dict) -> None:
    st.session_state["job_id"] = job["id"]
    title = job.get("job_title") or job.get("profile", {}).get("job_metadata", {}).get(
        "job_title"
    )
    st.session_state["job_label"] = f"{title or 'Untitled'}  ·  {job['id']}"


# ── Section 2: Candidate dataset ────────────────────────────
def section_dataset() -> None:
    st.subheader("2 · Candidate Dataset")
    mode = st.radio(
        "Dataset source",
        ["Use Official Candidate Dataset", "Upload Custom JSONL"],
        horizontal=True,
        key="dataset_mode",
    )

    if mode == "Use Official Candidate Dataset":
        ds = official_dataset_path()
        if not ds.exists():
            st.error(f"Official dataset not found at: {ds}")
            st.session_state["dataset_path"] = None
            return
        size = ds.stat().st_size
        st.markdown(f"**Detected:** `{ds.name}`")
        st.caption(f"Location: {ds}  ·  Size: {human_size(size)}")

        # Pass the existing path straight to the backend — no upload / copy / temp.
        st.session_state["dataset_path"] = str(ds)
        st.session_state["dataset_label"] = ds.name

        # Candidate count is optional and computed by streaming (cached per file).
        cache_key = f"{ds}:{ds.stat().st_mtime_ns}"
        if st.session_state.get("dataset_count_key") != cache_key:
            if st.button("Count candidates (optional)"):
                with st.spinner("Counting candidates (streaming, no full load)…"):
                    st.session_state["dataset_count"] = count_jsonl_lines(ds)
                    st.session_state["dataset_count_key"] = cache_key
        if (
            st.session_state.get("dataset_count_key") == cache_key
            and st.session_state.get("dataset_count") is not None
        ):
            st.success(f"Detected **{st.session_state['dataset_count']:,}** candidate(s).")
        else:
            st.info("Candidate count not computed (optional for large files).")
    else:
        uploaded = st.file_uploader("Upload candidates (JSONL)", type=["jsonl"])
        if uploaded is None:
            return
        data = uploaded.getvalue()
        count = sum(1 for line in data.splitlines() if line.strip())
        if count == 0:
            st.error("The uploaded file is empty — no candidate rows detected.")
            st.session_state["dataset_path"] = None
            return
        tmp_dir = Path(tempfile.gettempdir()) / "redrob_sandbox"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        dataset_path = tmp_dir / "candidates.jsonl"
        dataset_path.write_bytes(data)
        st.session_state["dataset_path"] = str(dataset_path)
        st.session_state["dataset_label"] = uploaded.name
        st.session_state["dataset_count"] = count
        st.success(f"Detected **{count:,}** candidate(s).")
        if count > 100:
            st.warning(
                "For a responsive sandbox run, we recommend **≤ 100 candidates**. "
                "Larger datasets work but take longer."
            )

    if st.session_state.get("dataset_path"):
        st.caption(f"Active dataset: **{st.session_state.get('dataset_label')}**")


# ── Section 3: Ranking options + run ────────────────────────
def section_ranking() -> None:
    st.subheader("3 · Ranking Options")
    col1, col2 = st.columns(2)
    top_n = col1.number_input("Top N", min_value=1, max_value=100, value=100, step=1)
    role = col2.selectbox("Role profile", ROLE_PROFILES, index=0)
    role_profile = None if role == "(auto)" else role

    ready = bool(st.session_state.get("job_id")) and bool(st.session_state.get("dataset_path"))
    if not ready:
        st.info("Select/parse a job and choose a candidate dataset to enable ranking.")

    if st.button("Run Ranking", type="primary", disabled=not ready):
        client = _client()
        tmp_dir = Path(tempfile.gettempdir()) / "redrob_sandbox"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        csv_path = str(tmp_dir / "submission.csv")
        try:
            with st.spinner("Running the offline ranking engine on the backend…"):
                result = client.run_ranking(
                    job_id=st.session_state["job_id"],
                    dataset_path=st.session_state["dataset_path"],
                    top_n=int(top_n),
                    role_profile=role_profile,
                    export_csv=True,
                    csv_path=csv_path,
                )
            st.session_state["result"] = result
            st.session_state["server_csv_path"] = csv_path
        except BackendError as exc:
            st.session_state["result"] = None
            st.error(f"Ranking failed: {exc}")


# ── Section 4: Results ──────────────────────────────────────
def section_results() -> None:
    result = st.session_state.get("result")
    if not result:
        return
    st.subheader("4 · Results")
    render_results(result)

    csv_text: str | None = None
    server_csv = st.session_state.get("server_csv_path")
    if server_csv and Path(server_csv).exists():
        try:
            csv_text = Path(server_csv).read_text(encoding="utf-8")
        except OSError:
            csv_text = None
    if csv_text is None:
        csv_text = results_to_csv(result)

    st.download_button(
        "⬇ Download submission CSV",
        data=csv_text,
        file_name="submission.csv",
        mime="text/csv",
    )


# ── Main ────────────────────────────────────────────────────
def main() -> None:
    _init_state()
    st.title("AI Recruitment Intelligence Platform")
    st.caption("Official sandbox — a thin Streamlit layer over the existing backend APIs.")
    sidebar()

    backend_ok = _client().health()
    status_panel(backend_ok)
    st.divider()

    if not backend_ok:
        st.error(
            "The backend is not reachable. Start it first "
            "(`uvicorn app.main:app` from `backend/`), then set the API base URL in the sidebar."
        )
        return

    section_job()
    st.divider()
    section_dataset()
    st.divider()
    section_ranking()
    st.divider()
    section_results()


if __name__ == "__main__":
    main()
