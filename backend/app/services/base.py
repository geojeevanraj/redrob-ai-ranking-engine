"""Service layer skeleton.

Services hold business logic and orchestrate repositories. They are the only
layer API endpoints should call into. No business logic exists in Sprint 0 —
this base just establishes the dependency-injected shape.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    """Base class for application services.

    Concrete services receive an async session (and, later, repositories) via
    constructor injection.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
