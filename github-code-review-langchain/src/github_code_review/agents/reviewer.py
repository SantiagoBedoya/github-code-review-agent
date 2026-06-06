from __future__ import annotations

import logging
import os

from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from github_code_review.agents.bandit import (
    BanditState,
    build_features,
    maybe_decay_epsilon,
    should_run_agent,
    update_weights,
)
from sqlalchemy.ext.asyncio import AsyncSession

from github_code_review.agents.prompts import AGENT_PROMPTS
from github_code_review.config import settings
from github_code_review.database import ReviewHistory
from github_code_review.models import AgentReview, Issue, PullRequestPayload, Severidad, ReviewFile

logger = logging.getLogger("github_code_review.agents")

_COT_AGENTS: set[str] = {"seguridad", "estructuras"}


_AGENT_LABELS = {
    "seguridad": "🔒 Seguridad",
    "estructuras": "🏗️ Estructuras",
    "calidad": "✨ Calidad",
    "performance": "⚡ Performance",
    "documentacion": "📖 Documentación",
}


def _get_llm() -> ChatOpenAI:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
    )


class _AgentIssue(BaseModel):
    severidad: str = ""
    linea: str = ""
    descripcion: str = ""
    sugerencia: str = ""


class _AgentResponse(BaseModel):
    path: str = ""
    issues: list[_AgentIssue] = Field(default_factory=list)
    resumen: str = ""


_SEVERITY_MAP: dict[str, Severidad] = {
    "critica": "crítica",
    "crítica": "crítica",
    "critical": "crítica",
    "alta": "alta",
    "high": "alta",
    "media": "media",
    "medium": "media",
    "baja": "baja",
    "low": "baja",
}


def _normalize_severity(s: str) -> Severidad:
    return _SEVERITY_MAP.get(s.lower(), "media")


async def review_file(
    file: ReviewFile,
    pr: PullRequestPayload,
    state: BanditState,
    db: AsyncSession,
) -> dict[str, AgentReview]:
    path = file.path
    ext = "." + path.rsplit(".", 1)[-1]
    patch_lines = file.patch.count("\n")
    features = build_features(ext, patch_lines)

    results: dict[str, AgentReview] = {}
    user_message = f"Archivo:\n{path}\n\nContenido:\n{file.contenido}\n\nDiff del PR:\n{file.patch}"

    for agent_name, system_prompt in AGENT_PROMPTS.items():
        run, score = should_run_agent(state, agent_name, features)
        label = _AGENT_LABELS.get(agent_name, agent_name)

        if not run:
            logger.debug("  ⏭  %-22s  score=%.2f", label, score)
            results[agent_name] = AgentReview(
                path=path,
                resumen=f"__SKIPPED__ (score: {score:.2f})",
            )
            db.add(
                ReviewHistory(
                    repo_owner=pr.repo_owner,
                    repo_name=pr.repo_name,
                    pr_number=pr.pr_number,
                    pr_head_sha=pr.pr_head_sha,
                    file_path=path,
                    agent_name=agent_name,
                    score=score,
                    reward=None,
                )
            )
            continue

        logger.info("  🤖 %s  analyzing %s…", label, path)

        try:
            parser = PydanticOutputParser(pydantic_object=_AgentResponse)
            llm = _get_llm()
            if agent_name in _COT_AGENTS:
                sys_msg = system_prompt
            else:
                sys_msg = system_prompt + "\n\n" + parser.get_format_instructions()
            raw = await llm.ainvoke(
                [
                    ("system", sys_msg),
                    ("human", user_message),
                ]
            )
            parsed: _AgentResponse = parser.invoke(raw)
            review = AgentReview(
                path=parsed.path or path,
                issues=[
                    Issue(
                        severidad=_normalize_severity(i.severidad),
                        linea=i.linea,
                        descripcion=i.descripcion,
                        sugerencia=i.sugerencia,
                    )
                    for i in parsed.issues
                ],
                resumen=parsed.resumen,
            )
            results[agent_name] = review

            reward = 1.0 if len(review.issues) > 0 else -0.5
            update_weights(state, agent_name, features, score, reward)

            db.add(
                ReviewHistory(
                    repo_owner=pr.repo_owner,
                    repo_name=pr.repo_name,
                    pr_number=pr.pr_number,
                    pr_head_sha=pr.pr_head_sha,
                    file_path=path,
                    agent_name=agent_name,
                    score=score,
                    reward=reward,
                )
            )

            n = len(review.issues)
            if n:
                logger.info("    → %d issue(s) found", n)
            else:
                logger.info("    ✅ No issues found")

        except Exception as exc:
            logger.warning("    ⚠️  Error: %s", exc)
            results[agent_name] = AgentReview(
                path=path,
                resumen=f"Error: {exc}",
            )
            db.add(
                ReviewHistory(
                    repo_owner=pr.repo_owner,
                    repo_name=pr.repo_name,
                    pr_number=pr.pr_number,
                    pr_head_sha=pr.pr_head_sha,
                    file_path=path,
                    agent_name=agent_name,
                    score=score,
                    reward=None,
                )
            )

    maybe_decay_epsilon(state)
    return results
