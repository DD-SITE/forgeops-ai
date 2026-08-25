from __future__ import annotations

import asyncio

import httpx

from app.core.config import settings


class GitHubTool:
    def __init__(self) -> None:
        if not settings.github_token:
            raise RuntimeError("GITHUB_TOKEN is not configured.")

    async def create_issue(
        self,
        *,
        repository: str,
        title: str,
        body: str,
    ) -> dict:
        if "/" not in repository:
            raise ValueError("Repository must use owner/repository format.")

        url = f"{settings.github_api_base_url.rstrip('/')}/repos/{repository}/issues"
        headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        last_error = ""
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(3):
                response = await client.post(
                    url,
                    headers=headers,
                    json={"title": title, "body": body},
                )

                if response.status_code < 400:
                    data = response.json()
                    return {
                        "id": data.get("id"),
                        "number": data.get("number"),
                        "title": data.get("title"),
                        "url": data.get("html_url"),
                        "repository": repository,
                    }

                last_error = response.text[:500]
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break

                await asyncio.sleep(2**attempt)

        raise RuntimeError(
            f"GitHub API returned {response.status_code}: {last_error}"
        )
