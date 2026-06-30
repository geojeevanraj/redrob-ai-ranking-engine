"""SQLAlchemy declarative base.

All ORM models (added in future sprints) should inherit from `Base`. No
business tables are defined in Sprint 0 — this only establishes the metadata
registry that Alembic will target.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
