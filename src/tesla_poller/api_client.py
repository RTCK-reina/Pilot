"""Tesla Owner's API HTTP client with OAuth token management.

Implements the APIBackend protocol for future Fleet API swappability.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

# Owner's API endpoints
OWNER_AUTH_URL = "https://auth.tesla.com/oauth2/v3/token"
OWNER_API_BASE = "https://owner-api.teslamotors.com/api/1"


class APIBackend(Protocol):
    """Protocol for Tesla API backends (Owner's API, Fleet API)."""

    async def get_vehicles(self) -> list[dict[str, Any]]:
        """Lightweight vehicle list — does NOT wake the car."""
        ...

    async def get_vehicle_data(self, vin: str) -> dict[str, Any]:
        """Full vehicle data — DOES reset the car's sleep timer."""
        ...

    async def close(self) -> None: ...


class OwnerAPIClient:
    """Tesla Owner's API client with automatic token refresh and rate limiting."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        *,
        on_token_refresh: Any | None = None,
        base_url: str = OWNER_API_BASE,
        auth_url: str = OWNER_AUTH_URL,
    ):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._on_token_refresh = on_token_refresh
        self._base_url = base_url
        self._auth_url = auth_url
        self._client = httpx.AsyncClient(timeout=30.0)
        self._backoff_until: float = 0.0
        self._consecutive_errors = 0

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _refresh_access_token(self) -> None:
        """Exchange refresh token for a new access + refresh token pair."""
        logger.info("Refreshing OAuth access token")
        resp = await self._client.post(
            self._auth_url,
            json={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": "ownerapi",
                "scope": "openid email offline_access",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._consecutive_errors = 0

        if self._on_token_refresh:
            await self._on_token_refresh(self._access_token, self._refresh_token)

    async def _request(self, method: str, path: str) -> dict[str, Any]:
        """Make an API request with retry, backoff, and token refresh."""
        now = time.monotonic()
        if now < self._backoff_until:
            wait = self._backoff_until - now
            logger.debug("Rate limit backoff: waiting %.1fs", wait)
            await asyncio.sleep(wait)

        url = f"{self._base_url}{path}"

        for attempt in range(3):
            try:
                resp = await self._client.request(method, url, headers=self._headers())

                if resp.status_code == 401:
                    await self._refresh_access_token()
                    resp = await self._client.request(method, url, headers=self._headers())

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "30"))
                    self._backoff_until = time.monotonic() + retry_after
                    logger.warning("Rate limited (429). Backing off %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code == 408:
                    # Vehicle is asleep — return a marker
                    return {"state": "asleep"}

                resp.raise_for_status()
                self._consecutive_errors = 0
                return resp.json().get("response", resp.json())

            except httpx.TimeoutException:
                self._consecutive_errors += 1
                backoff = min(2**attempt * 5, 60)
                logger.warning(
                    "Timeout on attempt %d/%d. Retrying in %ds",
                    attempt + 1, 3, backoff,
                )
                await asyncio.sleep(backoff)

            except httpx.HTTPStatusError as e:
                self._consecutive_errors += 1
                if e.response.status_code >= 500:
                    backoff = min(2**attempt * 10, 120)
                    logger.warning(
                        "Server error %d on attempt %d. Retrying in %ds",
                        e.response.status_code, attempt + 1, backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise

        raise RuntimeError(f"Failed after 3 attempts: {method} {path}")

    async def get_vehicles(self) -> list[dict[str, Any]]:
        """Get vehicle list (lightweight, does not wake car)."""
        data = await self._request("GET", "/vehicles")
        if isinstance(data, list):
            return data
        return data.get("response", []) if isinstance(data, dict) else []

    async def get_vehicle_data(self, vin: str) -> dict[str, Any]:
        """Get full vehicle data (wakes car, resets sleep timer).

        Args:
            vin: Vehicle VIN or vehicle_id.
        """
        return await self._request("GET", f"/vehicles/{vin}/vehicle_data")

    async def close(self) -> None:
        await self._client.aclose()
