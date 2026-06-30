# AI Recruitment Intelligence Platform — Sandbox (Streamlit)

A minimal, Python-only **presentation layer** for the platform. It is the
official Redrob hackathon sandbox: a hosted-friendly UI where the ranking
pipeline can be run on a small candidate sample.

> **It contains no business logic.** Every operation — job parsing, candidate
> loading, ranking, scoring, and CSV generation — is delegated to the existing
> FastAPI backend over HTTP. The sandbox only uploads files, calls endpoints,
> and displays the results.

## What it does

1. **Job Description** — *Use Official Job Description* (the local
   `dataset/job_description.docx`, used in place) **or** *Upload Custom Job
   Description* (PDF/DOCX/TXT).
2. **Candidate Dataset** — *Use Official Candidate Dataset* (the local
   `dataset/candidates.jsonl`, passed by path — no browser upload) **or**
   *Upload Custom JSONL*.
3. **Ranking Options** — Top N (default 100) and an optional role profile.
4. **Run Ranking** — calls `POST /api/v1/ranking/run` (deterministic, CPU-only,
   no LLM) and shows the Top-N table (Rank, Candidate ID, Score, Reasoning).
5. **Download** — the official 4-column submission CSV.

A **status panel** at the top shows whether the official dataset, the official
job description, and the backend are available.

## Use Official Dataset vs. Upload Custom Dataset

The official `candidates.jsonl` is ~465 MB. Pushing that through the browser is
slow and makes for a poor demo, so the sandbox prefers the local file:

| Mode | Behavior |
|------|----------|
| **Use Official Candidate Dataset** (default) | The existing local file is used **in place** — its absolute path is sent to the backend's ranking endpoint. Nothing is uploaded through the browser, copied, or read wholly into memory. Ranking starts immediately. The candidate count is optional and computed by streaming the file. |
| **Upload Custom JSONL** | The browser upload is kept for custom datasets. The bytes are written to a temp file which is then passed to the backend. |
| **Use Official Job Description** (default) | The local `dataset/job_description.docx` is read and sent to the backend for parsing — no manual drag-and-drop. |
| **Upload Custom Job Description** | Standard PDF/DOCX/TXT browser upload. |

The official file locations can be overridden with environment variables:

```bash
# macOS/Linux
export SANDBOX_OFFICIAL_DATASET=/abs/path/to/candidates.jsonl
export SANDBOX_OFFICIAL_JD=/abs/path/to/job_description.docx
# Windows (PowerShell)
$env:SANDBOX_OFFICIAL_DATASET = "C:\abs\path\candidates.jsonl"
$env:SANDBOX_OFFICIAL_JD = "C:\abs\path\job_description.docx"
```

> Because the official dataset is passed **by path**, the sandbox and backend
> must run on the **same machine** (which they do in the local/Docker sandbox).

## Backend endpoints used

| Action | Endpoint |
|--------|----------|
| Upload JD | `POST /api/v1/documents/upload` |
| Parse JD | `POST /api/v1/jobs/parse/{document_id}` |
| List jobs | `GET /api/v1/jobs` |
| Run ranking | `POST /api/v1/ranking/run` |
| Health/status | `GET /health`, `GET /api/v1/system/status` |

## Installation

From the project root (a virtual environment is recommended):

```bash
pip install -r sandbox/requirements.txt
```

## Running

**1. Start the backend** (in one terminal, from `backend/`):

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend needs its usual dependencies: PostgreSQL reachable, migrations
applied (`alembic upgrade head`), and a configured `.env`. See the root
`README.md`.

**2. Start the sandbox** (in another terminal, from the project root):

```bash
streamlit run sandbox/app.py
```

Streamlit opens at <http://localhost:8501>.

## Connecting to the backend

By default the sandbox calls `http://localhost:8000/api/v1`. To point it
elsewhere, either:

- set the environment variable before launching:
  ```bash
  # macOS/Linux
  export SANDBOX_BACKEND_URL=http://localhost:8000/api/v1
  # Windows (PowerShell)
  $env:SANDBOX_BACKEND_URL = "http://localhost:8000/api/v1"
  ```
- or edit the **API base URL** field in the sidebar and click **Check
  connection**.

> The sandbox writes the uploaded dataset to a temporary file and passes its
> path to the backend's ranking endpoint, and asks the backend to write the
> submission CSV to a temporary path which the sandbox then offers for download.
> Sandbox and backend are expected to run on the **same machine**.

## Notes / limitations

- The backend must be running and reachable before you can rank.
- For the full 100,000-candidate official dataset, prefer the backend endpoint
  directly (or a Docker reproduction) — the sandbox targets small samples per
  the hackathon's sandbox guidance.
- Folders `pages/` and `assets/` are placeholders kept for structure; the app is
  intentionally a single page.

## Structure

```
sandbox/
├── app.py                 # Streamlit entry point (orchestration UI)
├── components/
│   └── render.py          # results table + CSV serialization (presentation only)
├── utils/
│   ├── api_client.py      # thin HTTP client over backend APIs
│   └── official.py        # locate/describe the official local dataset + JD
├── .streamlit/
│   └── config.toml        # upload-size limit (1 GB)
├── pages/                 # (placeholder)
├── assets/                # (placeholder)
├── requirements.txt
└── README.md
```
