from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from github_code_review.config import settings
from github_code_review.models import PullRequestPayload, ReviewFile

logger = logging.getLogger("github_code_review.github")


class GitHubClient:
    BASE = "https://api.github.com"
    HEADERS = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    def __init__(self) -> None:
        token = settings.github_token
        if not token:
            msg = "GITHUB_TOKEN is not set"
            raise RuntimeError(msg)
        self._headers = {**self.HEADERS, "Authorization": f"Bearer {token}"}

    async def _get_json(self, url: str) -> Any:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def get_pr_files(self, pr: PullRequestPayload) -> list[dict[str, Any]]:
        url = f"{self.BASE}/repos/{pr.repo_owner}/{pr.repo_name}/pulls/{pr.pr_number}/files"
        logger.debug("GET %s", url.split("?")[0])
        data = await self._get_json(url)
        logger.debug("  → %d files returned", len(data))
        return data

    async def get_file_content(
        self, pr: PullRequestPayload, path: str
    ) -> ReviewFile | None:
        url = (
            f"{self.BASE}/repos/{pr.repo_owner}/{pr.repo_name}"
            f"/contents/{path}?ref={pr.pr_head_sha}"
        )
        logger.debug("GET /contents/%s", path)
        try:
            data = await self._get_json(url)
            raw = data.get("content", "")
            contenido = base64.b64decode(raw).decode("utf-8")
            logger.debug("  → %d bytes", len(contenido))
            return ReviewFile(
                filename=data.get("name", ""),
                path=path,
                contenido=contenido,
            )
        except httpx.HTTPStatusError as exc:
            logger.debug("  → HTTP %s — skipping", exc.response.status_code)
            return None

    async def post_comment(self, pr: PullRequestPayload, body: str) -> None:
        url = (
            f"{self.BASE}/repos/{pr.repo_owner}/{pr.repo_name}"
            f"/issues/{pr.pr_number}/comments"
        )
        logger.debug("POST comment PR#%s (%d chars)", pr.pr_number, len(body))
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self._headers,
                json={"body": body},
            )
            resp.raise_for_status()
        logger.debug("  → comment posted")
