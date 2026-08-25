from __future__ import annotations

import httpx

from app.core.config import settings


class IncidentTool:
    async def search(self, query: str) -> list[dict]:
        if not settings.incident_api_url:
            return []

        headers = {"Accept": "application/json"}
        if settings.incident_api_token:
            headers["Authorization"] = f"Bearer {settings.incident_api_token}"

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                settings.incident_api_url,
                headers=headers,
                params={"q": query, "limit": 10},
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Incident API returned {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.get("incidents", []))
        return []
