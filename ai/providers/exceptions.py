"""Provider error hierarchy.

These exceptions let the LLM manager make fallback decisions uniformly,
regardless of which concrete provider raised them. Any `ProviderError` is
considered *retriable / fallback-eligible* by the manager.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for all provider failures (fallback-eligible)."""

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        self.provider = provider
        super().__init__(message)


class ProviderTimeoutError(ProviderError):
    """The provider did not respond within the allotted time."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected the request due to quota or rate limiting."""


class ProviderUnavailableError(ProviderError):
    """The provider could not be reached (network/connection failure)."""


class InvalidResponseError(ProviderError):
    """The provider returned a malformed or unusable response."""


class UnknownProviderError(ProviderError):
    """A provider name was requested that is not registered."""
