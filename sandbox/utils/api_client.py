"""Thin HTTP client over the existing backend API.

The sandbox is a *presentation layer only*. This client makes plain HTTP calls
to the already-running FastAPI backend and performs NO ranking, parsing, or
scoring of its own. Every meaningful operation is delegated to an existing
endpoint:

    * POST /api/v1/documents/upload      — upload a JD (PDF/DOCX/TXT)
    * POST /api/v1/jobs/parse/{doc_id}   — parse the JD into a JobProfile
    * GET  /api/v1/jobs                  — list already-parsed jobs
    * POST /api/v1/ranking/run           — run the offline ranking engine
    * GET  /api/v1/system/status         — health / KG / DB / LLM status
"""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_TIMEOUT = 600  # ranking 100k can take a few minutes


class BackendError(Exception):
    """Raised when a backend call fails; message is safe to show to users."""


class BackendClient:
    """Minimal, dependency-light client for the backend REST API."""

    def __init__(self, base_url: str) -> None:
        # Normalize to ".../api/v1" with no trailing slash.
        self.base_url = base_url.rstrip("/")

    # ── Health ──────────────────────────────────────────────
    def health(self) -> bool:
        """Return True if the backend root health probe responds 200."""
        root = self.base_url.rsplit("/api/", 1)[0]
        try:
            r = requests.get(f"{root}/health", timeout=10)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def system_status(self) -> dict[str, Any]:
        return self._get("/system/status")

    # ── Jobs ────────────────────────────────────────────────
    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._get("/jobs", params={"limit": limit})

    def upload_document(
        self, *, filename: str, content: bytes, content_type: str, document_type: str
    ) -> dict[str, Any]:
        files = {"file": (filename, content, content_type or "application/octet-stream")}
        data = {"document_type": document_type}
        return self._post("/documents/upload", files=files, data=data, timeout=120)

    def parse_job(self, document_id: str) -> dict[str, Any]:
        return self._post(f"/jobs/parse/{document_id}", timeout=120)

    # ── Ranking ─────────────────────────────────────────────
    def run_ranking(
        self,
        *,
        job_id: str,
        dataset_path: str,
        top_n: int,
        role_profile: str | None,
        export_csv: bool,
        csv_path: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": job_id,
            "dataset_path": dataset_path,
            "top_n": top_n,
            "export_csv": export_csv,
        }
        if role_profile:
            payload["role_profile"] = role_profile
        if csv_path:
            payload["csv_path"] = csv_path
        return self._post("/ranking/run", json=payload, timeout=DEFAULT_TIMEOUT)

    # ── HTTP plumbing ───────────────────────────────────────
    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        try:
            r = requests.get(f"{self.base_url}{path}", params=params, timeout=30)
        except requests.RequestException as exc:
            raise BackendError(f"Could not reach the backend: {exc}") from exc
        return self._handle(r)

    def _post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: int = 60,
    ) -> Any:
        try:
            r = requests.post(
                f"{self.base_url}{path}", json=json, files=files, data=data, timeout=timeout
            )
        except requests.RequestException as exc:
            raise BackendError(f"Could not reach the backend: {exc}") from exc
        return self._handle(r)

    @staticmethod
    def _handle(r: requests.Response) -> Any:
        if r.status_code >= 400:
            detail = ""
            try:
                body = r.json()
                detail = body.get("detail") or body.get("message") or str(body)
            except ValueError:
                detail = r.text[:300]
            raise BackendError(f"Backend returned {r.status_code}: {detail}")
        try:
            return r.json()
        except ValueError as exc:
            raise BackendError("Backend returned a non-JSON response.") from exc
