"""
HubSpot CRM REST API client — Private App Token authentication.
All HubSpot interactions are encapsulated here.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .hubspot_settings import get_settings

log = structlog.get_logger("hs.client")

HUBSPOT_BASE_URL = "https://api.hubapi.com"


class HubSpotAuthError(Exception):
    """Raised when HubSpot authentication fails."""


class HubSpotAPIError(Exception):
    """Raised when a HubSpot API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class HubSpotClient:
    """Async HubSpot CRM API client with Bearer token auth."""

    def __init__(self) -> None:
        settings = get_settings()
        self.access_token = settings.hubspot_access_token
        if not self.access_token:
            raise HubSpotAuthError(
                "Missing HUBSPOT_ACCESS_TOKEN in environment. Set it in your .env file."
            )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> httpx.Response:
        """Execute an authenticated request to HubSpot CRM API."""
        url = f"{HUBSPOT_BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method, url, headers=self._headers, params=params, json=json_body,
            )
        if resp.status_code == 401:
            raise HubSpotAuthError("HubSpot authentication failed: invalid or expired access token.")
        return resp

    def _raise_for_error(self, resp: httpx.Response, context: str) -> None:
        """Raise HubSpotAPIError if the response indicates failure."""
        if resp.is_success:
            return
        try:
            body = resp.json()
            message = body.get("message", str(body))
        except Exception:
            message = resp.text[:500]
        raise HubSpotAPIError(
            f"HubSpot API error ({context}, HTTP {resp.status_code}): {message}",
            status_code=resp.status_code,
        )

    # ── Search (list / filter) ────────────────────────────────────────────────

    async def search_objects(
        self,
        object_type: str,
        properties: list[str],
        filter_groups: list[dict] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search objects with optional filters. Returns flattened records."""
        body: dict[str, Any] = {
            "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
            "properties": properties,
            "limit": limit,
        }
        if filter_groups:
            body["filterGroups"] = filter_groups
        resp = await self._request("POST", f"/crm/v3/objects/{object_type}/search", json_body=body)
        self._raise_for_error(resp, f"search {object_type}")
        results = resp.json().get("results", [])
        return [{"id": r["id"], **r.get("properties", {})} for r in results]

    # ── Get single object ─────────────────────────────────────────────────────

    async def get_object(
        self,
        object_type: str,
        object_id: str,
        properties: list[str],
    ) -> dict[str, Any]:
        """Fetch a single record by id. Returns flattened properties dict."""
        params = {"properties": ",".join(properties)}
        resp = await self._request("GET", f"/crm/v3/objects/{object_type}/{object_id}", params=params)
        self._raise_for_error(resp, f"get {object_type}/{object_id}")
        r = resp.json()
        return {"id": r["id"], **r.get("properties", {})}

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_object(
        self,
        object_type: str,
        properties: dict[str, Any],
    ) -> str:
        """Create a new record. Returns the new record's id."""
        resp = await self._request("POST", f"/crm/v3/objects/{object_type}", json_body={"properties": properties})
        self._raise_for_error(resp, f"create {object_type}")
        return resp.json()["id"]

    # ── Update ────────────────────────────────────────────────────────────────

    async def update_object(
        self,
        object_type: str,
        object_id: str,
        properties: dict[str, Any],
    ) -> None:
        """Update a record by id."""
        resp = await self._request("PATCH", f"/crm/v3/objects/{object_type}/{object_id}", json_body={"properties": properties})
        self._raise_for_error(resp, f"update {object_type}/{object_id}")

    # ── Associations ──────────────────────────────────────────────────────────

    async def get_associated_ids(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        limit: int = 10,
    ) -> list[str]:
        """Fetch associated record IDs via the v4 Associations API."""
        resp = await self._request("GET", f"/crm/v4/objects/{from_type}/{from_id}/associations/{to_type}")
        self._raise_for_error(resp, f"associations {from_type}/{from_id}/{to_type}")
        results = resp.json().get("results", [])[:limit]
        return [str(r["toObjectId"]) for r in results]

    async def batch_read(
        self,
        object_type: str,
        object_ids: list[str],
        properties: list[str],
    ) -> list[dict[str, Any]]:
        """Batch read multiple records by IDs. Returns flattened list."""
        if not object_ids:
            return []
        resp = await self._request(
            "POST",
            f"/crm/v3/objects/{object_type}/batch/read",
            json_body={"inputs": [{"id": oid} for oid in object_ids], "properties": properties},
        )
        self._raise_for_error(resp, f"batch read {object_type}")
        results = resp.json().get("results", [])
        return [{"id": r["id"], **r.get("properties", {})} for r in results]


    async def create_association(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
    ) -> None:
        """Create an association between two records via v4 Associations API."""
        resp = await self._request(
            "PUT",
            f"/crm/v4/objects/{from_type}/{from_id}/associations/{to_type}/{to_id}",
            json_body=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 1}],
        )
        self._raise_for_error(resp, f"associate {from_type}/{from_id} → {to_type}/{to_id}")

    # ── Owners ───────────────────────────────────────────────────────────────

    async def get_owners(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch HubSpot owners (users/team members)."""
        resp = await self._request("GET", "/crm/v3/owners", params={"limit": limit})
        self._raise_for_error(resp, "get owners")
        return [
            {"id": o["id"], "firstName": o.get("firstName", ""), "lastName": o.get("lastName", ""), "email": o.get("email", "")}
            for o in resp.json().get("results", [])
        ]


# ── Module-level singleton ────────────────────────────────────────────────────

_client: HubSpotClient | None = None


def get_client() -> HubSpotClient:
    """Return the shared HubSpotClient instance, creating it on first call."""
    global _client
    if _client is None:
        _client = HubSpotClient()
    return _client
