"""File storage abstraction.

Keeps uploaded raw files out of the database. The location is configurable.
A local-filesystem implementation ships now; an S3/object-store implementation
can be added later behind the same `FileStorage` interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class FileStorage(ABC):
    """Contract for persisting raw document bytes."""

    @abstractmethod
    def save(self, *, document_id: str, extension: str, content: bytes) -> str:
        """Persist content and return a storage path/key."""

    @abstractmethod
    def read(self, path: str) -> bytes:
        """Read previously stored content."""


class LocalFileStorage(FileStorage):
    """Stores files under a configurable base directory."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, *, document_id: str, extension: str, content: bytes) -> str:
        path = self.base_dir / f"{document_id}.{extension}"
        path.write_bytes(content)
        return str(path)

    def read(self, path: str) -> bytes:
        return Path(path).read_bytes()
