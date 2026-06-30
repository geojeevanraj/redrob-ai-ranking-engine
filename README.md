# AI Recruitment Intelligence Platform

An AI-powered candidate-ranking platform that replaces keyword matching with
semantic understanding, hidden-skill inference, candidate DNA, explainable
rankings, and a recruiter copilot.

> **Status: Sprint 0 — Foundation.** This repository currently contains the
> engineering scaffold only: project structure, configuration, Docker setup,
> health/version endpoints, and interface skeletons. **No business, AI, or
> ranking logic is implemented yet.**

See the architecture and product strategy under
[`.kiro/specs/ai-recruitment-intelligence-platform/`](.kiro/specs/ai-recruitment-intelligence-platform/).

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Alembic |
| Database | PostgreSQL 16 + `pgvector` |
| AI (future) | Sentence Transformers, pluggable LLM provider (interfaces only today) |
| Infra | Docker, Docker Compose |

> **Backend-only.** This repository is a backend + offline ranking engine. The
> earlier React frontend has been removed; all functionality is exposed through
> the FastAPI HTTP API.

---

## Project Structure

```
ai recruitment/
├── backend/                 # FastAPI service
│   ├── app/
│   │   ├── api/             # Versioned routers (api/v1/...)
│   │   ├── config/          # Settings (env-driven, cached)
│   │   ├── core/            # Logging, exception handlers
│   │   ├── db/              # Async engine + session, declarative base
│   │   ├── models/          # ORM models (none yet)
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── services/        # Service layer skeleton (business logic)
│   │   ├── repositories/    # Repository pattern skeleton (persistence)
│   │   ├── middleware/      # Request logging, etc.
│   │   ├── dependencies/    # FastAPI DI providers
│   │   ├── utils/           # Generic helpers
│   │   └── main.py          # App factory + root endpoints
│   ├── alembic/             # Migration environment (no migrations yet)
│   └── tests/               # Pytest suite
├── ai/                      # AI interfaces only (providers, embeddings, engines…)
├── dataset/                 # Official Redrob dataset + submission validator
├── infra/                   # Docker, Postgres init, startup scripts
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Quick Start (Docker — recommended)

Prerequisites: Docker + Docker Compose.

```bash
# 1. Create your env file
cp .env.example .env

# 2. Start the stack (db + backend)
make up            # or: docker compose up --build
```

Or use a startup script that waits for health:

```bash
# macOS/Linux
./infra/scripts/start.sh

# Windows (PowerShell)
./infra/scripts/start.ps1
```

Then open:
- API: <http://localhost:8000>
- API docs (Swagger): <http://localhost:8000/docs>

---

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

Requires a reachable PostgreSQL with `pgvector` (or just run `db` via
`docker compose up db`). The health/version endpoints work without a DB.

---

## API Endpoints (Sprint 0)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service root + helpful links |
| GET | `/health` | Liveness probe |
| GET | `/version` | Service + API version |
| GET | `/api/v1/health` | Versioned health probe |
| GET | `/api/v1/version` | Versioned version info |

---

## Configuration

All configuration is environment-driven (see `.env.example`). The active
environment is selected via `APP_ENV` (`development` | `testing` |
`production`). Settings are validated and cached in
`backend/app/config/settings.py`.

---

## Database & Migrations

PostgreSQL runs with the `pgvector` extension enabled automatically on first
container start (`infra/postgres/init/01-extensions.sql`). Schema is managed by
Alembic — no business tables exist yet.

```bash
make migrate                 # alembic upgrade head
make revision m="add jobs"   # autogenerate a new migration
```

---

## Quality Tooling

Backend:

```bash
make lint        # ruff
make format      # isort + black + ruff --fix
make typecheck   # mypy (strict)
make test        # pytest
make check       # all of the above
```

Pre-commit hooks (black, isort, ruff, mypy):

```bash
pip install pre-commit && pre-commit install
```

---

## Coding Conventions

- **Backend**: PEP 8 via Black (100 cols), imports sorted by isort (black
  profile), linted by Ruff, fully type-annotated and checked by mypy (strict).
  Layered architecture — endpoints call **services**, services call
  **repositories**, repositories own persistence. Keep cross-cutting concerns
  (logging, errors, DI) in `core/`, `middleware/`, `dependencies/`.
- **Commits**: keep quality gates green (`make check`) before pushing.

---

## Roadmap

Sprint 0 (this) delivers the bootable foundation. Subsequent sprints implement
the AI engines (Job/Candidate Intelligence, Hidden Skill Inference, DNA,
ranking, explainability, copilot) per the design document.

---

## AI Infrastructure (Sprint 1.1)

The `ai/` package provides a reusable, provider-agnostic LLM framework that
every future AI engine builds on. **Business logic never calls a provider
directly** — it goes through the single entry point, the **LLM Manager**.

### Provider Architecture (Strategy Pattern)

```
              LLMProvider (abstract interface)
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  GeminiProvider   OllamaProvider   MockProvider   (+ future: OpenAI, Claude…)
        └───────────────┼───────────────┘
                        ▼
                   LLMManager  ← the only thing engines talk to
```

- **`LLMProvider`** (`ai/providers/base.py`) — the contract: `generate()`,
  `generate_json()`, `health_check()`.
- **`GeminiProvider`** (primary) and **`OllamaProvider`** (fallback) wrap their
  APIs via `httpx` and translate failures into a shared exception hierarchy
  (`ai/providers/exceptions.py`).
- **`LLMManager`** (`ai/llm/manager.py`) — provider selection, automatic
  fallback, bounded retries, timeout enforcement, response validation, usage
  tracking, and structured logging.

### Usage

```python
from ai.llm.manager import LLMManager

manager = LLMManager.from_settings()          # builds providers from env config

resp = await manager.generate("Summarize this role", system="You are concise.")
print(resp.text, resp.usage.total_tokens, resp.provider)

resp = await manager.generate_json(prompt, required_keys=["skills"])
data = resp.json_data                          # validated dict, never malformed

health = await manager.health()                # per-provider availability
```

### Fallback Mechanism

If the **primary** provider fails for any reason — timeout, quota/rate limit,
network failure, or an invalid/malformed response — the manager retries up to
`LLM_MAX_RETRIES` times, then automatically switches to the **fallback**
provider. Every attempt is logged and recorded in the usage tracker with a
`fallback_used` flag. If all providers fail, an `LLMManagerError` is raised.

### Configuration

| Variable | Purpose |
|----------|---------|
| `PRIMARY_LLM_PROVIDER` | Primary provider name (`gemini` \| `ollama` \| `mock`) |
| `FALLBACK_LLM_PROVIDER` | Fallback provider name |
| `LLM_TIMEOUT` | Per-request timeout (seconds) |
| `LLM_MAX_RETRIES` | Retries per provider before falling back |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini credentials + model |
| `GEMINI_TEMPERATURE` / `GEMINI_MAX_TOKENS` / `GEMINI_TIMEOUT` | Gemini tuning |
| `OLLAMA_HOST` / `OLLAMA_MODEL` / `OLLAMA_TIMEOUT` | Ollama settings |

### Adding a New Provider

No consumer or business-logic code changes are required:

1. Create `ai/providers/<name>.py` implementing `LLMProvider`
   (`generate`, `health_check`; `generate_json` is inherited).
2. Register a builder:
   ```python
   from ai.providers.registry import register_provider

   @register_provider("openai")
   def _build_openai(settings):
       return OpenAIProvider(api_key=settings.openai_api_key, ...)
   ```
3. Import it in `ai/providers/__init__.py` so the builder registers.
4. Set `PRIMARY_LLM_PROVIDER=openai` (or fallback). Done.

### Prompt System

Prompts are **never hardcoded**. They live as versioned template files under
`ai/prompts/<category>/<name>.v<N>.txt` (categories: `resume/`, `jobs/`,
`explainability/`, `copilot/`, `shared/`). The `PromptManager`
(`ai/prompts/manager.py`) handles loading, versioning (`"latest"` or a specific
int), `{{variable}}` substitution, and validation (missing/extra variables are
rejected). Double-brace syntax lets prompt bodies contain literal JSON braces.

```python
from ai.prompts import PromptManager

pm = PromptManager()                              # defaults to ai/prompts/
text = pm.get("resume/extract", candidate_name="Ada")   # renders latest version
```

### Usage Tracking & Logging

Every call records a `UsageRecord` (provider, model, input/output tokens,
estimated cost, response time, timestamp, success, fallback flag) via a
pluggable `UsageTracker` (default: in-memory). Each request also emits one
structured log line with request id, provider, model, execution time,
success/failure, fallback usage, and token counts.

### Running the AI tests

External API calls are fully mocked (httpx `MockTransport` + scripted
providers) — no real network requests.

```bash
backend\.venv\Scripts\python -m pytest ai/tests   # from the project root
```

---

## Document Processing (Sprint 1.2)

The Document Intelligence layer accepts uploaded files and converts them into a
clean, normalized **`CanonicalDocument`** — the input contract for every future
AI engine. **No AI/LLM is involved in this layer.**

### Supported Formats

| Format | Extractor | Notes |
|--------|-----------|-------|
| PDF | PyMuPDF | per-page text + page count |
| DOCX | python-docx | paragraphs + tables (page count reported as 1) |
| TXT | built-in | UTF-8 with latin-1 fallback |

New formats plug in via the extractor registry (`@register_extractor`) without
changing the engine.

### Pipeline

```
Upload → Validation → Storage → Text Extraction → Cleaning
       → Unicode/Whitespace Normalization → Header/Footer & Page-Marker Removal
       → Metadata → Language Detection → Quality Metrics → CanonicalDocument
```

- **Cleaning** (`app/documents/cleaning.py`) is a composable pipeline of generic
  processors: line-ending normalization, Unicode NFKC, page-marker removal,
  repeated header/footer removal, whitespace collapse, blank-line dedup, trim.
- **Language detection** (`langdetect`, seeded for determinism) stores a
  confidence and never translates; short/undetectable text → `unknown`.
- **Quality metrics**: text-extraction confidence, empty-page count, an
  `ocr_required` flag (detection only — no OCR implemented), and a `malformed`
  flag. Unreadable files become a `FAILED` document rather than an error.

### Storage

Raw files are written to a configurable location (`DOCUMENT_STORAGE_DIR`,
default `./var/uploads`) via the `FileStorage` abstraction (`LocalFileStorage`
today; an S3/object-store backend can be added behind the same interface).
Document metadata, status, checksum, and both raw + clean text are persisted in
the `documents` table.

### Upload API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/documents/upload` | Upload (multipart/form-data) + process a document |
| GET | `/api/v1/documents` | List processed documents |
| GET | `/api/v1/documents/{id}` | Fetch a document (includes clean text) |

Upload accepts a `file` part and an optional `document_type` form field
(generic, e.g. `resume`, `job_description`, `unknown`). The API validates the
extension, MIME, and configured maximum size, computes a **SHA-256 checksum**,
and performs **duplicate detection** — re-uploading identical content returns
the existing document with `duplicate: true` (no reprocessing).

Example:
```bash
curl -F "file=@resume.pdf" -F "document_type=resume" \
     http://localhost:8000/api/v1/documents/upload
```

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DOCUMENT_STORAGE_DIR` | `./var/uploads` | Where raw files are stored |
| `MAX_UPLOAD_SIZE_MB` | `10` | Maximum accepted upload size |
| `ALLOWED_DOCUMENT_EXTENSIONS` | `pdf,docx,txt` | Accepted file extensions |

### Architecture

```
app/documents/
├── model.py            # CanonicalDocument + metadata/quality/language (dataclasses)
├── engine.py           # DocumentIntelligenceEngine (orchestrates the pipeline)
├── extractors/         # TextExtractor interface + registry + pdf/docx/txt
├── cleaning.py         # composable generic text processors + pipeline
├── language.py         # language detection (detection only)
├── quality.py          # heuristic quality metrics
├── metadata.py         # checksum, counts, MIME, sizes
└── storage.py          # FileStorage abstraction (LocalFileStorage)
```

Persistence lives in `app/models/document.py`, `app/repositories/document.py`,
and `app/services/document_service.py`; the API in
`app/api/v1/endpoints/documents.py`.

---

## Candidate Intelligence Engine (Sprint 1.3)

Converts an uploaded resume into a validated, reusable **`CandidateProfile`** —
the structured input contract for every later AI engine (hidden skills, DNA,
ranking, …). It consumes the *clean text* produced in Sprint 1.2, so **the
original PDF is never reprocessed**, and uses the shared **LLM Manager** +
**Prompt Manager** from Sprint 1.1.

### Flow

```
DocumentRecord (clean text)  →  Prompt Manager (versioned template)
                             →  LLM Manager (Gemini → Ollama fallback, JSON mode)
                             →  schema validation (Pydantic)
                             →  technology-stack dedup + metadata
                             →  CandidateProfile (persisted, linked to document)
```

### CandidateProfile schema

Personal info, professional summary, education[], experience[] (company, role,
dates, duration, responsibilities, technologies, business impact), projects[]
(title, description, technologies, domain, impact, team size), categorized
skills (programming languages, frameworks, libraries, databases, cloud, devops,
ai_ml, tools), certifications, achievements, leadership, publications,
open source, hackathons, awards, languages known, a **deduplicated
technology_stack**, and extraction **metadata** (confidence, missing fields,
warnings, LLM provider, model, timestamp). All fields default to empty so
partial extractions still validate; gaps are reported in `metadata.missing_fields`.

### Validation, retry & fallback

- The prompt requests **strict JSON**; the LLM Manager parses/validates it and,
  on malformed output / timeout / quota / network errors, **retries** then
  **falls back to Ollama** automatically.
- The engine then validates the JSON against the `CandidateProfile` Pydantic
  schema; malformed shapes raise `CandidateExtractionError` (mapped to HTTP 422).

### Prompt

Versioned template at `ai/prompts/resume/extract_profile.v1.txt` (loaded via the
Prompt Manager). New versions drop in as `extract_profile.v2.txt`.

### API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/candidates/parse/{document_id}` | Parse a stored document into a profile |
| GET | `/api/v1/candidates` | List candidate profiles |
| GET | `/api/v1/candidates/{candidate_id}` | Fetch a full candidate profile |

```bash
# 1) upload a resume (Sprint 1.2) -> returns a document id
curl -F "file=@resume.pdf" -F "document_type=resume" \
     http://localhost:8000/api/v1/documents/upload
# 2) parse it into a structured candidate profile
curl -X POST http://localhost:8000/api/v1/candidates/parse/<document_id>
```

### Persistence

`candidate_profiles` (migration `0002`) stores the full profile as JSONB plus
promoted columns (`full_name`, `email`, `extraction_confidence`, provider,
model) and a `document_id` foreign key linking back to the source document.

### Architecture note (ai ↔ backend)

The backend uses the sibling `ai` package (LLM/Prompt managers). `app/__init__.py`
adds the repository root to `sys.path` so `import ai…` works in local dev and
tests; the engine itself depends only on small `Protocol`s, so it stays
decoupled and is tested with fakes. For containers, `docker-compose` mounts
`./ai` into the backend so it is importable at runtime.

---

## Job Intelligence Engine (Sprint 2.1)

Converts an uploaded **Job Description** into a validated, reusable
**`JobProfile`** — the structured input contract for downstream AI engines
(Knowledge Graph, Hidden Skill Inference, Decision Intelligence, Explainability).
It consumes the *clean text* produced in Sprint 1.2 (the original JD is never
reprocessed) and uses the shared LLM Manager + Prompt Manager.

> **Literal extraction only.** This engine extracts ONLY information explicitly
> present in the job description. It does **not** infer hidden requirements,
> culture, leadership, or skills — that belongs to later sprints.

### JobProfile schema

Job metadata (title, company, employment type, work mode, location, department,
industry), experience (minimum/preferred years, seniority — only if stated),
education (required/preferred), explicit `required_skills` vs `preferred_skills`,
a categorized `technical_stack` (languages, frameworks, libraries, databases,
cloud, devops, ai_ml, tools), responsibilities, explicitly-mentioned soft skills
and leadership expectations, certifications, benefits, salary, a deduplicated
`technology_stack`, and extraction `metadata` (confidence, missing fields,
warnings, provider, model, timestamp). All fields default to empty.

### Flow, validation & fallback

Same pipeline as the Candidate engine: versioned prompt → LLM Manager (strict
JSON, automatic retry + Ollama fallback) → Pydantic schema validation
(`JobExtractionError` → HTTP 422) → technology-stack dedup + metadata.

Prompt: `ai/prompts/jobs/extract_profile.v1.txt`.

### API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/jobs/parse/{document_id}` | Parse a stored JD into a job profile |
| GET | `/api/v1/jobs` | List job profiles |
| GET | `/api/v1/jobs/{job_id}` | Fetch a full job profile |

```bash
# upload a JD (document_type=job_description) then parse it
curl -F "file=@job.pdf" -F "document_type=job_description" \
     http://localhost:8000/api/v1/documents/upload
curl -X POST http://localhost:8000/api/v1/jobs/parse/<document_id>
```

### Persistence

`job_profiles` (migration `0003`) stores the full profile as JSONB plus promoted
columns (`job_title`, `company_name`, `extraction_confidence`, provider, model)
and a `document_id` foreign key linking back to the source document.

---

## Knowledge Graph Foundation (Sprint 3.1)

A generic, data-driven ontology of technologies, skills, frameworks, databases,
cloud platforms, AI concepts, tools, certifications, methodologies, roles, and
domains — reusable by every future AI engine (Hidden Skill Inference, Candidate
DNA, Decision Intelligence, …).

> **Storage only — no inference.** This layer *stores and queries* explicitly
> curated relationships. It does not infer relationships, derive hidden skills,
> or compute similarity. Inference belongs to later sprints.

### Architecture

```
app/knowledge/
├── model.py          # Node, Edge, Neighbor, NodeType, RelationshipType (Pydantic)
├── repository.py     # KnowledgeRepository (ABC) + InMemoryKnowledgeRepository
├── graph.py          # KnowledgeGraph facade (build + query + mutate)
├── validation.py     # duplicate / missing-category / invalid-ref / cyclic-alias checks
├── loader.py         # load the seed ontology
├── importers/        # JSON / YAML / CSV importers (data-driven, registry)
└── data/ontology.json  # seed dataset (~194 nodes, 75 relationships)
```

The graph is loaded once per process (cached) and injected into endpoints/engines
via `get_knowledge_graph`.

### Node & relationship types

Node types: programming_language, framework, library, database, cloud, devops,
ai, machine_learning, tool, platform, certification, methodology, architecture,
domain, soft_skill, role, industry.

Relationship types: BELONGS_TO, USES, REQUIRES, RELATED_TO, PART_OF, ALIAS_OF,
PARENT_OF, CHILD_OF, COMPLEMENTS, SIMILAR_TO, DEPENDENT_ON.

### Ontology format

A `{ "nodes": [...], "edges": [...] }` document (JSON or YAML), or a directory
with `nodes.csv` + `edges.csv`. Each node has `id`, `name`, `type`, `category`,
optional `aliases`/`synonyms`/`description`/`metadata`/`version`/`confidence`.
Each edge has `source`, `target`, `relationship`, optional
`evidence`/`metadata`/`confidence`.

```json
{
  "nodes": [
    {"id": "fastapi", "name": "FastAPI", "type": "framework", "category": "backend_framework"}
  ],
  "edges": [
    {"source": "fastapi", "target": "python", "relationship": "DEPENDENT_ON"}
  ]
}
```

### Validation

On load the graph is validated for: duplicate node ids, missing categories,
edges referencing unknown nodes, and cyclic `ALIAS_OF` chains. Any problem
raises a specific `KnowledgeError`.

### Adding new technologies

Edit `app/knowledge/data/ontology.json` (or point the loader at another
JSON/YAML/CSV source) — no Python changes needed. Add a node object and any
explicit relationship edges, then restart.

### Import process

`load_graph_from_file(path)` auto-detects the format from the extension and
returns a validated `KnowledgeGraph`; `load_seed_graph()` loads the bundled
dataset. New formats plug in via the importer registry (`get_importer`).

### API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/knowledge/nodes` | List/filter nodes (`type`, `category`, paging) |
| GET | `/api/v1/knowledge/node/{id}` | Fetch a node (falls back to alias resolution) |
| GET | `/api/v1/knowledge/node/{id}/neighbors` | Neighbors (`relationship`, `direction`) |
| GET | `/api/v1/knowledge/relationships` | List edges (optionally for a node / type) |
| GET | `/api/v1/knowledge/search` | Search nodes by name/alias/synonym |
| GET | `/api/v1/knowledge/stats` | Node/edge counts by type |

---

## Hidden Skill Inference Engine (Sprint 3.2)

Discovers skills a candidate did **not** explicitly list but that are strongly
supported by evidence in the Knowledge Graph. The guiding principle:

> **The Knowledge Graph proposes. The LLM verifies.** Every inferred skill is
> traceable to an explicit evidence chain — the engine never hallucinates.

### Architecture

```
app/hidden_skills/
├── model.py    # HiddenSkill, HiddenSkillProfile, EvidencePath, EvidenceStep
└── engine.py   # HiddenSkillInferenceEngine: propose() (deterministic) + infer() (LLM verify)
```

Persistence: `hidden_skill_profiles` (migration `0004`, JSONB + `candidate_id`
FK). Prompt: `ai/prompts/hidden_skills/verify.v1.txt`.

### Inference process

1. Read explicit skills from the `CandidateProfile` (skills + experience/project
   technologies + technology stack).
2. **Resolve aliases** through the Knowledge Graph to canonical node ids.
3. **Traverse** only allowed relationships — RELATED_TO, REQUIRES, PART_OF,
   COMPLEMENTS, USES, DEPENDENT_ON — outward from each explicit skill, with
   per-seed cycle prevention.
4. **Aggregate evidence** across multiple paths/sources per candidate skill.
5. **Score confidence** (see below) and apply guardrails.
6. Send the surviving proposals + evidence to the **LLM for verification**.
7. Keep only verified skills; return a `HiddenSkillProfile`.

The proposal stage (1–5) is **fully deterministic** — identical input always
yields identical proposals before any LLM call.

### Evidence model

Each `HiddenSkill` carries `evidence_nodes` (every node involved) and
`evidence_paths` — one path per corroborating explicit skill, each a list of
`source --relationship--> target` steps. The full chain is always returned and
persisted.

### Confidence algorithm

Activation starts at `1.0` at each explicit (seed) skill and decays each hop:
`activation = activation × edge_confidence × decay` (default decay `0.6`). For a
candidate skill reached from several seeds, the per-seed best activations are
combined with a **noisy-OR** (`1 − Π(1 − aᵢ)`), so independent corroboration
raises confidence.

### Graph traversal strategy & guardrails

- BFS from each seed up to `max_depth` (default 2), following only allowed
  relationship types; a per-seed visited set prevents cycles/loops.
- A proposal is accepted only if it is **not** a single weak thread: it needs
  either `≥ min_sources` distinct corroborating skills **or** a single strong
  direct edge (`max activation ≥ strong_single_threshold`), **and** its combined
  confidence `≥ min_confidence`.
- Only "skill-like" node types are inferred (languages, frameworks, libraries,
  databases, cloud, devops, ai/ml, tools, platforms, architecture, methodology).

All thresholds are configurable via env: `HIDDEN_SKILL_MIN_CONFIDENCE`,
`HIDDEN_SKILL_MAX_DEPTH`, `HIDDEN_SKILL_DECAY`, `HIDDEN_SKILL_MIN_SOURCES`,
`HIDDEN_SKILL_STRONG_SINGLE_THRESHOLD`.

### LLM verification flow

Proposals (skill + confidence + textual evidence paths) are sent to the LLM,
which returns `{"verifications": [{"skill_id", "verified", "reasoning"}]}`. The
LLM may only accept/reject graph-supported inferences and must not invent
evidence. Only `verified: true` skills are kept, each flagged `verified_by_llm`.

### API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/candidates/{id}/infer-skills` | Run inference + persist |
| GET | `/api/v1/candidates/{id}/hidden-skills` | Latest hidden-skill profile |

---

## AI Pipeline Developer Dashboard (Sprint 3.5)

An internal, developer-first dashboard (React + TypeScript, dark mode, no auth)
for validating every stage of the AI pipeline during development. It is **not**
the recruiter UI — it exists purely for observability. It consumes the existing
backend APIs plus one small read-only `/api/v1/system/status` endpoint.

### Pages (left sidebar)

| Page | Purpose |
|------|---------|
| **Dashboard** | Counts (documents, candidates, jobs, KG nodes), active LLM, avg API time, success rate |
| **Documents** | Upload PDF/DOCX/TXT; inspect metadata, cleaned text, quality metrics, language, checksum, status, raw JSON |
| **Candidates** | Candidate profile section-by-section (personal, education, experience, projects, skills, tech stack, metadata) + raw JSON; re-run parsing |
| **Jobs** | Structured job profile (responsibilities, required/preferred skills, tech stack, metadata) + raw JSON; re-run parsing |
| **Knowledge Graph** | Interactive graph viewer (reactflow): search, node details, neighbor exploration, relationship + alias visualization |
| **Hidden Skills** | The full inference pipeline: explicit skills → traversal → evidence paths → confidence → LLM verification → accepted skills, with per-skill confidence bars, relationship paths, reasoning, and verification status |
| **API Monitor** | Client-side trace of every request: method, path, status, duration, provider |
| **System Health** | Backend health, Gemini/Ollama availability, KG loaded, DB status, current config |
| **Settings** | Developer utilities (reload KG, clear API trace, refresh stats) + read-only config |

> **Note:** The React dashboard described in this section has been **removed**
> (the project is now backend-only). The backend endpoints it consumed — including
> `GET /api/v1/system/status` — remain available and unchanged.

### New backend endpoint

`GET /api/v1/system/status` — read-only snapshot aggregating LLM provider
availability (via the LLM Manager's health check, time-bounded), active/fallback
provider, knowledge-graph load state, database connectivity, and the current
(non-secret) configuration. Additive and read-only; it does not change pipeline
behavior.

---

## Candidate DNA Engine (Sprint 4.1)

Produces an evidence-based professional **fingerprint** — a set of archetype
affinities (Backend, Frontend, Full Stack, AI, ML, Data, DevOps, Cloud,
Platform, Security, Mobile, Research, Product Engineer, Startup Generalist,
Enterprise Specialist). It never predicts personality or psychological traits —
every archetype is traceable to observable technical evidence.

> **Deterministic scoring; the LLM only verifies + summarizes.** Scores are
> computed by configurable weighted rules and are never changed by the LLM.

### Architecture

```
app/dna/
├── model.py    # ArchetypeScore, CandidateDNA
├── engine.py   # CandidateDNAEngine: compute() (deterministic) + generate() (LLM verify)
└── data/archetypes.json  # configurable archetype rules (add new archetypes here)
```

Inputs: `CandidateProfile` + (optional) latest `HiddenSkillProfile` + Knowledge
Graph. Persistence: `candidate_dna` (migration `0005`, JSONB + `candidate_id`
FK). Prompt: `ai/prompts/dna/verify.v1.txt`.

### Scoring methodology

1. Collect candidate evidence terms: explicit skills, deduplicated technology
   stack, inferred (hidden) skills, and project/experience technologies + domains.
2. Canonicalize each term via the Knowledge Graph (alias-aware → node id +
   category), tracking provenance (which skill/project/experience it came from).
3. For each archetype rule, sum matched **keyword** weights plus matched
   **category** weights, then normalize: `score = min(1, matched / saturation)`.
4. `confidence = min(1, distinct_evidence_count / confidence_items)`.
5. Classify archetypes into **top** (`≥ top_threshold`), **emerging**
   (`emerging_threshold..top_threshold`), and **weak** (`>0..emerging`).
   Archetypes with no evidence are omitted — **no unsupported archetypes**.
6. `overall_engineering_focus` = the highest-scoring archetype.

The compute stage is fully deterministic. `generate()` then sends the computed
archetypes + evidence to the LLM, which returns per-archetype
`{consistent, reasoning}`; the engine sets `llm_verified` and the summary but
**never** alters scores.

### Evidence model

Each `ArchetypeScore` lists `supporting_skills`, `supporting_hidden_skills`,
`supporting_projects`, `supporting_experience`, and a human-readable `evidence`
list (matched technologies/categories with their weights).

### Configuration / archetype system

Archetypes live in `app/dna/data/archetypes.json` — each has an `id`, `name`,
`keywords` (term → weight), optional `categories` (KG category → weight), and a
`saturation`. **Add a new archetype by adding an entry** — no code changes.
Thresholds are env-configurable: `DNA_TOP_THRESHOLD`, `DNA_EMERGING_THRESHOLD`,
`DNA_CONFIDENCE_ITEMS`, `DNA_DEFAULT_SATURATION`.

### API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/candidates/{id}/dna` | Compute + persist DNA profile |
| GET | `/api/v1/candidates/{id}/dna` | Latest DNA profile |

---

## Decision Intelligence Engine (Sprint 5.1)

Compares one candidate (profile + hidden skills + DNA) against one job and
produces a transparent, reproducible, **evidence-backed** hiring recommendation.
Scoring is fully deterministic; the LLM may only verify consistency and explain.

> **Deterministic scores; the LLM never changes them.** Every recommendation is
> traceable to per-component evidence.

### Architecture

```
app/decision/
├── model.py    # ScoreComponent, DecisionProfile, Recommendation
├── engine.py   # DecisionIntelligenceEngine: compute() (deterministic) + generate() (LLM verify)
└── data/weights.json  # external, role-specific weighting profiles + thresholds
```

Inputs: `CandidateProfile` + latest `HiddenSkillProfile` + latest `CandidateDNA`
+ `JobProfile` + Knowledge Graph. Persistence: `decisions` (migration `0006`,
JSONB, FKs to candidate and job). Prompt: `ai/prompts/decision/verify.v1.txt`.

### Scoring methodology

Eleven deterministic sub-scores (each 0..1, with evidence):

| Component | How it's computed |
|-----------|-------------------|
| Required / Preferred Skill Match | exact + semantic (graph) coverage of job skills |
| Skill Coverage | `0.7·required + 0.3·preferred` |
| Technology Stack Match | coverage of the job's tech stack |
| Knowledge Graph Semantic Match | exact + partial coverage across all job skills via KG relationships |
| Experience Alignment | estimated candidate years vs job minimum |
| Project Relevance | candidate project technologies overlapping the job stack |
| Hidden Skill Contribution | job requirements covered *only* by inferred skills |
| DNA Compatibility | candidate DNA affinity for the role archetype |
| Education Alignment | candidate education vs job's required education |
| Career Progression | deterministic proxy from role count + seniority signals |

**Semantic matching**: a job skill not held exactly earns partial credit
(default 0.5) if the candidate has a graph neighbor linked by RELATED_TO /
SIMILAR_TO / PART_OF / DEPENDENT_ON / COMPLEMENTS / REQUIRES — and the
relationship used is recorded as evidence.

`overall_match_score = Σ (normalized_weightᵢ · scoreᵢ)`;
`overall_confidence` is the weighted average of component confidences.

### Weight configuration (role-specific)

`app/decision/data/weights.json` defines named weighting **profiles**
(`default`, `backend_engineer`, `ai_engineer`, `devops_engineer`, …), the
`role_keywords` that auto-select a profile from the job title, the
`semantic_partial_credit`, and the recommendation `thresholds`. A profile can
also be forced via the request's `weighting_profile`. Adding/retuning profiles
needs no code changes.

### Recommendation logic

`overall_match_score` maps to a recommendation via configurable thresholds:
`≥ strong_hire` → **Strong Hire**, `≥ hire` → **Hire**, `≥ consider` →
**Consider**, else **Reject** (defaults 0.8 / 0.65 / 0.45).

### Evidence model

Every `ScoreComponent` carries `matched_skills`, `missing_skills`,
`supporting_evidence`, `missing_evidence`, `graph_relationships_used`, and a
`reasoning_summary`. The decision also surfaces overall `strengths` and `gaps`.

### API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/decisions/evaluate` | Evaluate `{candidate_id, job_id, weighting_profile?}` |
| GET | `/api/v1/decisions` | List decisions (filter by candidate/job) |
| GET | `/api/v1/decisions/{id}` | Fetch a decision |

---

## Explainability Engine (Sprint 6.1)

Turns a `DecisionProfile` into a transparent, **evidence-backed** explanation and
compares two decisions. Every statement maps to evidence carried by the
decision's score components — nothing is invented.

> **Deterministic before LLM.** The explanation is built deterministically from
> the decision's own evidence. The LLM may ONLY rewrite text for readability — it
> can never change a score, a recommendation, or any evidence.

### Architecture

```
app/explainability/
├── model.py    # ExplanationProfile, Strength, Weakness, SkillGap,
│               #   ScoreExplanation, ComparisonProfile
└── engine.py   # ExplainabilityEngine: build()/compare() (deterministic)
                #   + generate()/generate_comparison() (LLM readability rewrite)
```

Persistence: `explanations` (migration `0007`, JSONB + `decision_id` FK).
Prompt: `ai/prompts/explainability/rewrite.v1.txt`.

### ExplanationProfile

- **Executive summary**, recommendation, overall match score + confidence.
- **Strengths** (components scoring ≥ 0.75): description + evidence + supporting
  skills/projects/experience.
- **Weaknesses** (components scoring < 0.4): description + missing evidence /
  skills / experience.
- **Skill gap analysis** (per missing required/preferred skill): importance,
  learning difficulty, estimated effort, expected impact on the match score, and
  adjacency evidence.
- **Score breakdown**: every component with its score, *why*, and evidence.

### Evidence mapping

Each strength/weakness/score-explanation is derived directly from a
`ScoreComponent`'s `matched_skills`, `missing_skills`, `supporting_evidence`,
`graph_relationships_used`, and `reasoning_summary`. Supporting projects and
experience are linked by intersecting a component's matched skills (canonicalized
via the Knowledge Graph) with the candidate's projects/experience technologies.

### Gap analysis

For each missing skill: **difficulty** is `low` if the candidate already holds an
adjacent skill in the graph (the adjacency is recorded as evidence), `high` for
inherently complex types (AI / ML / architecture), else `medium`; **effort** maps
from difficulty (~2 / ~6 / ~12 weeks); **expected impact** is the component weight
divided by the number of target skills (the lift from covering that one skill).

### Comparison model

`compare(A, B)` produces a per-component comparison (leader A / B / Tie),
`advantages` / `disadvantages` for each side (components leading by ≥ 0.1), the
overall `winner`, and a deterministic `reasoning` string. `generate_comparison`
additionally rewrites the reasoning for readability.

### API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/explanations/generate` | Explain a decision (`{decision_id}`) + persist |
| POST | `/api/v1/explanations/compare` | Compare two decisions (`{decision_id_a, decision_id_b}`) |
| GET | `/api/v1/explanations/{id}` | Fetch an explanation |

---

## Recruiter Dashboard (Sprint 7.1)

A polished, premium recruiter experience (React + TypeScript, **dark-mode first**,
glassmorphism, smooth animations) that showcases the AI reasoning pipeline. It
consumes only the existing backend APIs — no business logic is duplicated in the
frontend. The earlier developer pages were folded in (upload → Dashboard,
observability → Settings).

### Design system

- Ambient gradient backdrop, glass surfaces (`.surface` / `.glass`), Inter type.
- Tailwind tokens + keyframes (`fade-in`, `slide-up`, `shimmer`, `pulse-glow`).
- Custom lightweight **SVG charts** (no heavy chart deps): radar (Candidate DNA),
  confidence gauge, score ring, component score bars; plus a `reactflow`
  knowledge-graph viewer.

### Navigation & pages

| Page | What it shows |
|------|---------------|
| **Dashboard** | Hero, animated drag-and-drop upload that runs the real pipeline (upload → document → candidate → knowledge graph → hidden skills → DNA), an animated **pipeline timeline** with per-stage status + timing, live stats, and recent evaluations |
| **Candidates** | Profile cards → detail with **DNA radar**, top archetypes, hidden skills (confidence bars), latest decision (score ring + recommendation), technology stack, experience, projects |
| **Jobs** | Structured job profile with categorized technical stack, required/preferred skills, responsibilities |
| **Rankings** | Evaluate a candidate vs a job, then a **ranked list** (score rings + recommendation badges); detail with confidence gauge, top strengths/gaps, component score bars |
| **Comparison** | Side-by-side two decisions with winner highlighting, advantages, and component-by-component bars |
| **Explainability** | Executive summary, confidence gauge, strength/weakness cards, **skill-gap roadmap** (difficulty/effort/impact), and score breakdown |
| **Knowledge Graph** | Upgraded `reactflow` viewer: type-colored nodes, animated relationships, search, click-to-recenter, zoom/pan |
| **Settings** | System health (providers, DB, KG), configuration, and the API trace (observability) |

> **Note:** This recruiter dashboard has been **removed** — the project is now
> backend-only. Every backend API it consumed remains available and unchanged;
> all platform functionality is accessible through the FastAPI HTTP API.

---

## Interactive Hiring Simulator (Sprint 8.1)

Lets recruiters explore "what-if" scenarios — change hiring criteria and instantly
see how candidate rankings move, with every change explained. It turns the
platform from a static evaluator into an interactive decision-support tool.

> **No new AI reasoning, no duplicated logic, no engine changes.** The simulator
> reuses the existing deterministic `DecisionIntelligenceEngine.compute()` and
> `ExplainabilityEngine.build()` with *modified inputs*. Results are **temporary**
> — nothing is persisted and no stored evaluation is overwritten.

### Simulation architecture

A single non-persisting endpoint, `POST /api/v1/simulations/run`, orchestrates:

1. **Modify the job** — apply editable criteria to a deep copy of the stored
   `JobProfile`: move skills required↔preferred, add/remove skills, change minimum
   experience, change required education. (Engine logic untouched.)
2. **Apply bounded weights** — if the recruiter customizes component weights, the
   service builds a throwaway `DecisionConfig` with a `__simulation__` profile
   (each weight clamped to `[0, 1]`; the engine normalizes) and instantiates the
   existing engine class with that config.
3. **Recompute deterministically** — run `engine.compute()` for the baseline
   (original job) and the modified scenario for each candidate. No LLM is called,
   so simulations are fast and reproducible.
4. **Explain** — produce updated strengths/gaps/score-breakdown via
   `ExplainabilityEngine.build()` (also deterministic).

### Decision reuse

Because `compute()` and `generate()` produce identical scores (the LLM only
verifies/explains in the Decision engine), the simulator's deterministic baseline
matches what a persisted evaluation would score — so deltas are exact.

### Delta calculation

For each candidate the response includes the previous/new score, the signed
delta, previous/new rank (ranking re-sorted by new score), rank delta, the
previous/new recommendation, per-component score deltas, and the top
component-level reasons for the change.

### UI workflow

The **Simulator** page has three panels:
- **Left** — editable criteria: job picker, role weighting profile, click-to-cycle
  skills (required → preferred → removed), add-skill input, minimum-experience
  slider, and optional component-weight sliders.
- **Center** — live ranking that recomputes (debounced) on every change, with
  rank-movement arrows, score deltas, and recommendation badges; rows animate.
- **Right** — for a selected candidate: why it changed, per-component shifts
  (baseline → new), and updated strengths/gaps.

The baseline-vs-modified comparison is built into every row (was #N → #M,
old% → new%, ±delta).

### API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/simulations/run` | Recompute rankings for a what-if scenario (no persistence) |
