"""AI Recruitment Intelligence Platform — backend application package.

Ensures the repository root is importable so the backend can use the shared
`ai` package (LLM Manager, Prompt Manager) which lives as a sibling of
`backend/`. This makes `import ai...` work for local dev, tests, and
volume-mounted containers.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
