# AI Service (`ai/`)

Interface-only package for the platform's AI capabilities. **Sprint 0 ships
contracts, not implementations.** Every module below defines abstract base
classes / protocols that future sprints will implement (Sentence Transformers
for embeddings, an LLM provider for reasoning, etc.).

## Layout

```
ai/
├── config.py            # AI-specific settings (model names, provider selection)
├── providers/           # LLM provider abstraction (assess fit, generate text)
├── embeddings/          # Embedding interface (text -> vector)
├── prompts/             # Versioned prompt templates (assets, not code)
├── parsers/             # Document/text parser interfaces (resume, JD)
├── engines/             # AI engine interfaces (job intel, candidate intel, ...)
└── inference/           # Inference orchestration interfaces (hidden skills, DNA)
```

## Principles
- **Interfaces first.** No model calls, no business logic in Sprint 0.
- **Provider-agnostic.** Swap LLM/embedding backends behind a stable contract.
- **Bounded & explainable** (per architecture): implementations must carry
  confidence + provenance — the contracts make room for it.
