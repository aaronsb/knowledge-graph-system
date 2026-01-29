"""HTTP API client for the Knowledge Graph."""

import logging
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)


class KnowledgeGraphClient:
    """Async HTTP client for the Knowledge Graph API with OAuth support."""

    def __init__(self, api_url: str, client_id: str, client_secret: str):
        self.api_url = api_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret

        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None
        self._token_expires: float = 0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.api_url, timeout=30.0)
        return self._client

    async def _get_token(self) -> str:
        """Get OAuth token, refreshing if needed."""
        if self._token and time.time() < self._token_expires:
            return self._token

        client = await self._get_client()
        response = await client.post(
            "/auth/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 3600) - 60
        log.debug("Obtained OAuth token")
        return self._token

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        """Make authenticated GET request to API."""
        token = await self._get_token()
        client = await self._get_client()
        response = await client.get(
            path,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json: dict = None, data: dict = None, files: dict = None) -> dict:
        """Make authenticated POST request to API."""
        token = await self._get_token()
        client = await self._get_client()
        response = await client.post(
            path,
            json=json,
            data=data,
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()

    async def get_bytes(self, path: str, params: Optional[dict] = None, timeout: float = 60.0) -> bytes:
        """Make authenticated GET request returning raw bytes.

        Used for fetching binary content like images from the API.
        Uses a longer default timeout since binary transfers can be large.
        """
        token = await self._get_token()
        client = await self._get_client()
        response = await client.get(
            path,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.content

    async def get_epoch(self) -> int:
        """Fetch the current graph epoch (change counter).

        Returns the graph_change_counter value, which changes when
        the graph is modified. Used for cache invalidation.

        Returns:
            Integer epoch value, or -1 on error (forces cache invalidation).
        """
        try:
            data = await self.get("/database/epoch")
            return data.get("epoch", -1)
        except Exception as e:
            log.warning(f"Failed to fetch graph epoch: {e}")
            return -1

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
