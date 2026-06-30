# Deployment Guide — AI Recruitment Intelligence Platform

Production packaging for the **backend (FastAPI)** + **Streamlit sandbox**. This
is deployment only — no business logic, ranking, scoring, or APIs were changed.

## Platform

**Render** (Docker web service + managed PostgreSQL) is the chosen target: it
cleanly supports FastAPI, Streamlit, Python, and a managed database from a
single repo blueprint (`render.yaml`). Railway / Hugging Face Spaces / any
Docker host work too (see *Alternatives*).

### Why a single combined container
The backend imports the sibling `ai/` package, and the sandbox hands datasets to
the backend **by filesystem path** (and writes custom uploads to a temp file the
backend must read). Running both processes in **one container** (shared
filesystem) keeps custom uploads and the dataset-by-path handoff working without
touching any backend code. Streamlit is the **public** web port (`$PORT`); the
backend runs **internally** on `127.0.0.1:8000`.

## Deployment URL

> Filled in after you deploy with your own account:
> `https://ai-recruitment-sandbox.onrender.com`  *(example — your Render
> service URL)*. The platform builds the image and assigns the URL; this repo
> contains everything needed to produce it.

## Required environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `APP_ENV` | yes | `production` (no debug/reload) |
| `POSTGRES_HOST/PORT/USER/PASSWORD/DB` | yes | DB connection; on Render injected from the managed database (see `render.yaml`) |
| `DATABASE_URL` | optional | explicit DSN override — must use `postgresql+asyncpg://` |
| `GEMINI_API_KEY` | yes for JD parsing | secret; set in the dashboard. Ranking itself uses **no** LLM |
| `PRIMARY_LLM_PROVIDER` | no | default `gemini` |
| `FALLBACK_LLM_PROVIDER` | no | default `ollama` (not reachable in the container; harmless) |
| `GEMINI_MODEL` | no | default `gemini-2.5-flash` |
| `RANKING_DATASET_PATH` | no | default sample at `/app/dataset/sample_candidates.jsonl` |
| `RANKING_EXPORT_DIR` | no | default `/app/backend/var/rankings` |
| `SANDBOX_BACKEND_URL` | no | default `http://localhost:8000/api/v1` |
| `SANDBOX_OFFICIAL_DATASET` / `SANDBOX_OFFICIAL_JD` | no | default to the bundled sample + JD |
| `PORT` | platform-set | Streamlit binds to it; Render sets it automatically |

No secrets, paths, or URLs are hardcoded in the application — all come from env.

## Dataset handling

- The **465 MB official `candidates.jsonl` is NOT bundled** (excluded via
  `.dockerignore`).
- A **20-row sample** (`dataset/sample_candidates.jsonl`) ships in the image for
  the demo and is the default `RANKING_DATASET_PATH`.
- **Custom uploads** still work in the sandbox (JSONL + JD).
- To run the **full official dataset**, do it **locally** (below).

## Production deployment (Render)

1. Push this repository to GitHub.
2. In Render: **New + → Blueprint**, select the repo. Render reads `render.yaml`
   and provisions the Postgres database + the Docker web service.
3. Set the secret **`GEMINI_API_KEY`** on the web service (Environment tab).
4. Deploy. Render builds `infra/docker/app.prod.Dockerfile`, runs migrations on
   start, and serves the sandbox at the assigned URL.
5. Open the URL → status panel shows **Backend ✓ Connected** and **Official
   Dataset ✓ Found** (the sample). Parse the official JD, run ranking, download
   the CSV.

## Local production-like run (Docker)

```bash
cp .env.production.example .env       # set POSTGRES_PASSWORD + GEMINI_API_KEY
docker compose -f docker-compose.prod.yml up --build
# open http://localhost:8501
```

## Local development run (no Docker)

```bash
# Backend (terminal 1)
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000      # add --reload for dev

# Sandbox (terminal 2, from repo root)
streamlit run sandbox/app.py
```

## Running the FULL official dataset locally

The deployed demo uses the sample. For the real validator-approved Top-100:

```bash
# Point the backend at the full dataset (relative to backend/ working dir)
#   RANKING_DATASET_PATH=../dataset/candidates.jsonl   (in backend/.env)
# Then either use the sandbox "Use Official Candidate Dataset" option,
# or call the API directly:
curl -X POST http://localhost:8000/api/v1/ranking/run \
  -H "Content-Type: application/json" \
  -d '{"job_id":"<parsed-job-id>","export_csv":true}'

# Validate the produced CSV with the official validator:
python dataset/validate_submission.py backend/var/rankings/ranking_<job-id>.csv
```

Runtime ~3 min, peak RAM ~180 MB, CPU-only, no network during ranking.

## Alternatives

- **Railway**: create a service from `infra/docker/app.prod.Dockerfile` (root
  context), add a PostgreSQL plugin, map its variables to `POSTGRES_*`, set
  `GEMINI_API_KEY`. Railway provides `$PORT` automatically.
- **Any Docker host**: build the image (root context) and run with the env vars
  above and a reachable PostgreSQL.

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| Sandbox shows **Backend ✗ Unreachable** at first load | Backend is still starting (migrations). Wait ~20–40s and refresh. |
| **Official Job Description parse fails** | `GEMINI_API_KEY` missing/invalid, or `gemini-2.5-flash` unavailable for the key. Set a valid key. |
| **Database connection errors** on boot | `POSTGRES_*` not set / DB not ready. On Render confirm the blueprint linked the database; locally ensure `db` is healthy. |
| `DATABASE_URL` used but driver error | The DSN must be `postgresql+asyncpg://…`. Prefer the `POSTGRES_*` parts. |
| Custom upload ranking fails in a **split** (multi-container) setup | Use the **single combined container** (this image) so the backend can read the uploaded temp file. |
| Image build pulls the 465 MB dataset | Ensure `.dockerignore` is present at the build root (it excludes `dataset/candidates.jsonl`). |
| Ranking seems slow on big input | Expected for large datasets; the deployed demo uses the small sample. Run the full dataset locally. |
