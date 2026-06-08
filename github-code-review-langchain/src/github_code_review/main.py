from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import BackgroundTasks, FastAPI, Request

from github_code_review.agents.bandit import BanditState
from github_code_review.agents.reviewer import review_file
from github_code_review.agents.synthesizer import synthesize
from github_code_review.database import close_db, get_session, init_db
from github_code_review.filters import is_valid_file
from github_code_review.github.client import GitHubClient
from github_code_review.models import AgentReview, PullRequestPayload, ReviewFile

logger = logging.getLogger("github_code_review")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Connecting to database…")
    await init_db()
    session = await get_session()
    try:
        async with session:
            await _bandit_state.load(session)
    finally:
        await session.close()
    logger.info(
        "Bandit state loaded — count=%d  epsilon=%.3f",
        _bandit_state.count,
        _bandit_state.epsilon,
    )
    yield
    await close_db()
    logger.info("Server stopped")


app = FastAPI(title="GitHub Code Review Agents", lifespan=lifespan)

_bandit_state: BanditState = BanditState()


@app.post("/webhook/github-review")
async def github_webhook(background_tasks: BackgroundTasks, request: Request) -> dict:
    payload = await request.json()
    action = payload.get("action", "")
    repo = payload.get("repository", {}).get("full_name", "?")
    pr_number = payload.get("number", 0)

    if action not in ("opened", "synchronize"):
        logger.info("-> Ignored action=%s  repo=%s  PR#%s", action, repo, pr_number)
        return {"status": "ignored"}

    logger.info("-> Webhook  action=%s  repo=%s  PR#%s", action, repo, pr_number)

    pr = PullRequestPayload(
        repo_owner=payload["repository"]["owner"]["login"],
        repo_name=payload["repository"]["name"],
        pr_number=pr_number,
        pr_head_sha=payload["pull_request"]["head"]["sha"],
        base_branch=payload["pull_request"]["base"]["ref"],
        head_branch=payload["pull_request"]["head"]["ref"],
    )

    background_tasks.add_task(_run_review, pr, _bandit_state)
    return {"status": "accepted", "pr_number": pr.pr_number}


async def _run_review(pr: PullRequestPayload, bandit_state: BanditState) -> None:
    repo = f"{pr.repo_owner}/{pr.repo_name}"
    logger.info("-> Starting review  %s  PR#%s", repo, pr.pr_number)
    t_start = time.monotonic()

    client = GitHubClient()
    raw_files = await client.get_pr_files(pr)
    t_files = time.monotonic()
    logger.info("-> %d files changed in PR  (%.3fs)", len(raw_files), t_files - t_start)

    filtered: list[ReviewFile] = []
    for f in raw_files:
        fname = f.get("filename", "")
        if is_valid_file(
            filename=fname,
            status=f.get("status", ""),
            additions=f.get("additions", 0),
            deletions=f.get("deletions", 0),
        ):
            content_file = await client.get_file_content(pr, fname)
            if content_file is None:
                logger.debug("  ⏭  %s — could not fetch content", fname)
                continue
            content_file.patch = f.get("patch", "")
            content_file.additions = f.get("additions", 0)
            content_file.deletions = f.get("deletions", 0)
            content_file.status = f.get("status", "")
            filtered.append(content_file)
            logger.debug("-> %s  (+%d/-%d)", fname, content_file.additions, content_file.deletions)

    if not filtered:
        logger.info("->  No reviewable files  %s  PR#%s", repo, pr.pr_number)
        return

    t_filtered = time.monotonic()
    logger.info("-> Reviewing %d file(s) with 5 agents  (fetch+filter: %.3fs)", len(filtered), t_filtered - t_files)

    session = await get_session()
    async with session:
        all_results: dict[str, dict[str, AgentReview]] = {}
        for file in filtered:
            agent_results = await review_file(file, pr, bandit_state, session)
            all_results[file.path] = agent_results
        await session.flush()

        t_reviewed = time.monotonic()
        logger.info("-> Synthesizing agent reports…")
        markdown = await synthesize(all_results)
        t_synth = time.monotonic()
        logger.info("-> Posting comment to PR#%s", pr.pr_number)
        await client.post_comment(pr, markdown)
        t_posted = time.monotonic()

        await bandit_state.save(session)

    total_issues = sum(
        len(r.issues) for fr in all_results.values() for r in fr.values()
    )
    total_time = t_posted - t_start
    agent_time = t_reviewed - t_filtered
    synth_time = t_synth - t_reviewed
    post_time = t_posted - t_synth
    logger.info(
        "-> Review complete  %s  PR#%s  —  %d files  %d issues  "
        "(total=%.3fs | agents=%.3fs | synth=%.3fs | post=%.3fs)",
        repo, pr.pr_number, len(filtered), total_issues,
        total_time, agent_time, synth_time, post_time,
    )
