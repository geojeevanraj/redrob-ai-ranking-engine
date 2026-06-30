# Prompt Templates

Versioned LLM prompt **assets** (not code). Each prompt used by an engine will
live here as a separate, versioned file so prompts can evolve and be audited
independently of application logic (per the architecture's prompt-governance
note).

Sprint 0 ships no prompts — this folder establishes the home for them.

Suggested convention (future):
```
prompts/
├── jd_understanding.v1.md
├── resume_parsing.v1.md
└── reasoning_fit.v1.md
```
