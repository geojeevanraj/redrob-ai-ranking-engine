# Redrob AI Ranking Engine

> **Redrob Hackathon submission** — Intelligent Candidate Discovery & Ranking Challenge.
>
> A knowledge-graph-augmented, fully deterministic offline ranking engine that
> scores 100,000 candidates against a job description in under 3 minutes on a
> consumer CPU, with zero LLM calls during ranking and full evidence-backed
> explainability.

[![Tests](https://img.shields.io/badge/tests-199%20passed-brightgreen)](#testing)
[![Runtime](https://img.shields.io/badge/100k%20candidates-~189s-blue)](#benchmark)
[![Memory](https://img.shields.io/badge/peak%20RAM-176%20MB-blue)](#benchmark)
[![CPU Only](https://img.shields.io/badge/compute-CPU%20only-orange)](#benchmark)
[![LLM Free](https://img.shields.io/badge/ranking-0%20LLM%20calls-green)](#compliance)

---

## Problem Statement

Traditional ATS systems filter resumes by keyword matching — they miss candidates
who have the skills but express them differently, and they rank keyword-stuffers
above genuine experts. This platform replaces keyword matching with:

- **Semantic understanding** via a Knowledge Graph (alias resolution, skill
  relationships, graph traversal)
- **Latent skill discovery** — inferring skills not explicitly listed from graph
  evidence
- **Behavioral signals** — 7 engagement dimensions from the Redrob platform
- **Explainable, traceable scores** — every rank is fully decomposable into its
  contributing evidence

---

## Key Features

| Feature | Description |
|---------|-------------|
| Knowledge Graph | 194-node skill ontology, 75 relationships, alias resolution |
| Hidden Skill Inference | Graph BFS from explicit skills → inferred latent skills |
| Candidate DNA | Archetype fingerprinting (AI Engineer, Backend, DevOps, …) |
| Decision Intelligence | 11-component weighted scoring, role-profile aware |
| Behavioral Intelligence | 7 engagement signals from `redrob_signals` |
| Offline Ranking | Streams 100k candidates, O(N) bounded heap, zero LLM |
| Explainability | Evidence-backed reasoning for every score |
| Streamlit Sandbox | Browser UI for demo and small-sample validation |
| FastAPI Backend | Async REST API, full test suite, Alembic migrations |

---

## Architecture

```
Job Description (DOCX/PDF/TXT)
        │
        ▼  [one-time, pre-computation]
Job Intelligence Engine (LLM parse → JobProfile)
        │
        ▼
╔══════════════════════════════════════════════════╗
║           OFFLINE RANKING PIPELINE               ║
║  (CPU-only · no LLM · no network · O(N) memory)  ║
╠══════════════════════════════════════════════════╣
║  Stream candidates.jsonl (100k rows, 1 at a time)║
║          │                                        ║
║          ▼                                        ║
║  Behavioral Intelligence Engine                   ║
║  (7 engagement signals → 0..1 score)             ║
║          │                                        ║
║          ▼                                        ║
║  Hidden Skill Inference (KG graph BFS propose)    ║
║  (no LLM verify in ranking path)                 ║
║          │                                        ║
║          ▼                                        ║
║  Candidate DNA Engine (compute)                   ║
║  (archetype affinities from skills + KG)         ║
║          │                                        ║
║          ▼                                        ║
║  Decision Intelligence Engine (compute)           ║
║  (11 weighted components → overall score)        ║
║          │                                        ║
║          ▼                                        ║
║  Bounded min-heap  top-N (default 100)            ║
╚══════════════════════════════════════════════════╝
        │
        ▼
  CSV Export  →  submission.csv  (candidate_id, rank, score, reasoning)
```

All ranking components use deterministic `compute()` / `propose()` methods only.
LLM functions (`generate()`, `infer()`) are **never called** during ranking.

---

## Ranking Pipeline Components

### Knowledge Graph
A custom 194-node ontology covering programming languages, frameworks, libraries,
databases, cloud platforms, AI/ML concepts, tools, certifications, methodologies,
roles, and domains. The graph handles alias resolution (`ReactJS` → `react`),
semantic relationships (`fastapi DEPENDENT_ON python`), and BFS traversal for
hidden-skill inference.

### Hidden Skill Inference
BFS from each explicit candidate skill through allowed relationship types
(RELATED_TO, REQUIRES, PART_OF, COMPLEMENTS, USES, DEPENDENT_ON). Evidence
is aggregated via noisy-OR across multiple paths; proposals passing guardrails
are accepted deterministically. In the ranking path, the deterministic
`propose()` is used (not the LLM `infer()` verify step).

### Candidate DNA Engine
Scores 8+ archetype affinities (AI Engineer, Backend Engineer, Data Engineer,
DevOps, etc.) from the candidate's skill evidence and KG category membership.
Role-profile weights in the Decision Engine are aligned to these archetypes.

### Decision Intelligence Engine (11 components)
| Component | Description |
|-----------|-------------|
| Required Skill Match | Fraction of JD required skills matched (exact + semantic) |
| Preferred Skill Match | Fraction of preferred skills matched |
| Skill Coverage Score | Weighted blend (required 70%, preferred 30%) |
| Technology Stack Match | Match against JD tech stack |
| Experience Alignment | Candidate years vs JD minimum |
| Project Relevance | Overlap of project technologies with JD stack |
| Hidden Skill Contribution | KG-inferred skills covering JD gaps |
| DNA Compatibility | Archetype affinity for the detected role profile |
| Education Alignment | Degree/field against JD requirements |
| Career Progression | Role count + seniority signals |
| Knowledge Graph Semantic Match | Semantic coverage via graph relationships |
| Behavioral Match *(+1)* | Overall behavioral signal score |

All weights are externalized in `backend/app/ranking/data/behavior_weights.json`
and `backend/app/decision/data/weights.json`. Nothing is hardcoded.

### Behavioral Intelligence Engine (7 signals)
| Signal | Sources |
|--------|---------|
| Availability | `open_to_work_flag`, `notice_period_days`, `last_active_date` |
| Responsiveness | `recruiter_response_rate`, `avg_response_time_hours`, `interview_completion_rate` |
| Recruiter Interest | `profile_views_received_30d`, `saved_by_recruiters_30d`, `search_appearance_30d` |
| Credibility | `verified_email`, `verified_phone`, `profile_completeness_score`, `linkedin_connected` |
| Technical Activity | `github_activity_score`, `skill_assessment_scores` |
| Learning Signal | `recent_activity`, `assessment_participation`, `profile_completeness_score` |
| Compensation Compatibility | `expected_salary_range_inr_lpa`, `willing_to_relocate`, `preferred_work_mode` |

---

## Benchmark

Verified on the official Redrob dataset (100,000 candidates):

| Metric | Result | Constraint |
|--------|--------|------------|
| Total candidates | 100,000 | — |
| Runtime | ~189 s (~3.1 min) | ≤ 5 min ✅ |
| Peak RAM | 176 MB | ≤ 16 GB ✅ |
| LLM calls during ranking | 0 | None allowed ✅ |
| GPU | None | CPU only ✅ |
| Network during ranking | None | Offline ✅ |
| Validator | **Submission is valid** | Format ✅ |
| Disk (intermediate state) | < 10 MB | ≤ 5 GB ✅ |

---

## Repository Structure

```
redrob-ai-ranking-engine/
├── rank.py                        # Single reproduce command (standalone CLI)
├── submission_metadata.yaml       # Hackathon portal metadata
├── backend/
│   ├── app/
│   │   ├── ranking/               # Offline ranking engine (Sprint 9.1)
│   │   │   ├── ranking_engine.py  # Bounded heap, compute-only pipeline
│   │   │   ├── behavioral_engine.py
│   │   │   ├── dataset_loader.py  # Streaming JSONL, O(1) memory
│   │   │   ├── csv_export.py      # Deterministic reasoning + CSV
│   │   │   └── data/             # behavior_weights.json, ranking_config.json
│   │   ├── decision/              # Decision Intelligence Engine
│   │   ├── hidden_skills/         # Hidden Skill Inference Engine
│   │   ├── dna/                   # Candidate DNA Engine
│   │   ├── knowledge/             # Knowledge Graph (194 nodes / 75 edges)
│   │   ├── candidates/            # Candidate Intelligence (LLM parse)
│   │   ├── jobs/                  # Job Intelligence Engine
│   │   ├── explainability/        # Explainability Engine
│   │   └── services/              # Hiring Simulator + other services
│   ├── alembic/versions/          # 7 DB migrations (0001–0007)
│   └── tests/                     # 199 tests across 31 files
├── ai/                            # Shared LLM infrastructure
│   ├── providers/                 # Gemini, Ollama (Strategy pattern)
│   ├── llm/                       # LLMManager (retry, fallback, usage tracking)
│   └── prompts/                   # Versioned prompt templates
├── sandbox/                       # Streamlit sandbox (presentation layer only)
│   ├── app.py
│   ├── utils/api_client.py
│   └── .streamlit/config.toml    # 1 GB upload limit
├── dataset/
│   ├── candidates.jsonl           # Official dataset (100k, NOT in repo >100MB)
│   ├── job_description.docx       # Official JD
│   ├── job_profile.json           # Pre-parsed JobProfile (rank.py input)
│   ├── sample_candidates.jsonl    # 500-row sample (in repo, used by sandbox)
│   ├── validate_submission.py     # Official validator
│   └── submission_spec.docx       # Official spec
├── infra/
│   ├── docker/app.prod.Dockerfile # Combined prod image (backend + sandbox)
│   └── docker/start-prod.sh       # Dual-venv startup script
├── render.yaml                    # Render Blueprint (web service + managed DB)
├── docker-compose.prod.yml        # Local production-like stack
├── DEPLOYMENT.md                  # Full deployment guide
├── Makefile                       # Developer task runner
└── .env.example                   # Environment variable template
```

---

## Quick Start — Reproduce the Submission

### Prerequisites
- Python 3.12
- PostgreSQL (for the full backend) **or** skip it (rank.py runs standalone)
- Gemini API key (for JD parsing only; skip if using pre-parsed `job_profile.json`)

### Option A: Single reproduce command (no database, no server)

```bash
# 1. Clone and install
git clone https://github.com/geojeevanraj/redrob-ai-ranking-engine.git
cd redrob-ai-ranking-engine
pip install -r backend/requirements.txt

# 2. Place the official dataset
cp /path/to/candidates.jsonl dataset/candidates.jsonl

# 3. Rank (uses pre-parsed job_profile.json — no LLM, no network, no DB)
python rank.py \
  --candidates dataset/candidates.jsonl \
  --job-profile dataset/job_profile.json \
  --out submission.csv

# 4. Validate
python dataset/validate_submission.py submission.csv
# → Submission is valid.
```

**Expected output:** `submission.csv` with 100 rows, runtime ~3 min, peak RAM ~180 MB.

### Option B: Full backend (with database and API)

```bash
# 1. Clone and install
git clone https://github.com/geojeevanraj/redrob-ai-ranking-engine.git
cd redrob-ai-ranking-engine
pip install -r backend/requirements.txt

# 2. Configure (copy and fill in DB + Gemini key)
cp .env.example backend/.env

# 3. Run migrations
cd backend && alembic upgrade head

# 4. Start the backend
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 5. Upload and parse the JD (one-time, uses Gemini)
curl -F "file=@dataset/job_description.docx" -F "document_type=job_description" \
     http://localhost:8000/api/v1/documents/upload
# → returns {"document":{"id":"<doc_id>", ...}}

curl -X POST http://localhost:8000/api/v1/jobs/parse/<doc_id>
# → returns {"id":"<job_id>", ...}

# 6. Run ranking (fully offline from this point)
curl -X POST http://localhost:8000/api/v1/ranking/run \
     -H "Content-Type: application/json" \
     -d '{"job_id":"<job_id>","export_csv":true}'
```

---

## Running the Streamlit Sandbox

```bash
# Install sandbox deps (in a separate venv to avoid starlette conflict)
pip install -r sandbox/requirements.txt

# Start the backend (terminal 1)
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000

# Start the sandbox (terminal 2, from repo root)
streamlit run sandbox/app.py
```

Open `http://localhost:8501`. The sandbox defaults to the official JD and the
bundled 500-row sample. Use "Upload Custom JSONL" for larger datasets.

---

## Deployment (Render)

See [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions.

**One-click deploy to Render:**
1. Fork this repo and push to GitHub.
2. Render → **New + → Blueprint** → select repo (reads `render.yaml`).
3. Set `GEMINI_API_KEY` in the environment tab.
4. Deploy — Render provisions a managed PostgreSQL + Docker web service.

Live sandbox: `https://ai-recruitment-sandbox.onrender.com/`

---

## Testing

```bash
cd backend
pytest                     # 199 tests, all pass
ruff check .               # lint clean
black --check .            # format clean
mypy app                   # type-check clean (121 files)
```

```bash
# Official submission validator
python dataset/validate_submission.py dataset/team_submission.csv
# → Submission is valid.
```

---

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|---------|
| `GEMINI_API_KEY` | JD parsing (pre-computation only) | For JD parse step |
| `POSTGRES_*` | Database connection | Full backend only |
| `PRIMARY_LLM_PROVIDER` | `gemini` \| `ollama` \| `mock` | No (defaults to `gemini`) |
| `RANKING_DATASET_PATH` | Path to `candidates.jsonl` | No (passed per-request) |
| `SANDBOX_BACKEND_URL` | Sandbox → backend URL | No (defaults to localhost) |

---

## Compliance

| Rule | Status |
|------|--------|
| No hosted LLM during ranking | ✅ 0 LLM calls in ranking loop |
| CPU only | ✅ Pure Python, no GPU libs |
| Runtime ≤ 5 min | ✅ ~189 s on a consumer CPU |
| Memory ≤ 16 GB | ✅ ~176 MB peak |
| Network off during ranking | ✅ Fully offline |
| Validator passes | ✅ "Submission is valid." |
| Score non-increasing | ✅ Enforced by heap + sort |
| Tie-break: candidate_id ascending | ✅ Enforced |

---

## Future Improvements

- Expand the KG ontology to cover more AI/ML skill terms (NLP, speech recognition, GANs, LoRA, etc.) — improving hidden-skill coverage on the official dataset.
- Add a learning-to-rank layer (LightGBM/XGBoost) trained on the ground-truth relevance tiers for higher NDCG.
- Implement honeypot detection (flag candidates with inconsistent tenure/skill claims).
- Expand behavioral signal weighting based on domain-specific recruiter feedback.

