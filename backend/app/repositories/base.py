"""Repository pattern skeleton.

Repositories encapsulate persistence access so the service layer never touches
the ORM/session directly. This generic base provides the shape future
concrete repositories will follow. No queries are implemented in Sprint 0.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """Base class for all repositories.

    Concrete repositories bind a specific ORM model and implement the data
    access methods they need (get/list/create/update/delete).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # Concrete CRUD methods are added per-model in future sprints, e.g.:
    #   async def get(self, id_: UUID) -> ModelT | None: ...
    #   async def list(self, ...) -> Sequence[ModelT]: ...
    #   async def add(self, entity: ModelT) -> ModelT: ...
