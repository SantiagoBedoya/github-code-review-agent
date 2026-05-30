from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Severidad = Literal["crítica", "alta", "media", "baja"]


class Issue(BaseModel):
    linea: str = ""
    descripcion: str
    sugerencia: str = ""
    severidad: Severidad = "media"


class AgentReview(BaseModel):
    path: str
    issues: list[Issue] = []
    resumen: str = ""


class AgentOutput(BaseModel):
    agent: str
    review: AgentReview
    skipped: bool = False
    score: float = 0.0


class ReviewFile(BaseModel):
    filename: str
    path: str
    contenido: str
    patch: str = ""
    additions: int = 0
    deletions: int = 0
    status: str = ""


class PullRequestPayload(BaseModel):
    repo_owner: str
    repo_name: str
    pr_number: int
    pr_head_sha: str
    base_branch: str
    head_branch: str


class WebhookPayload(BaseModel):
    action: str
    repository: dict
    pull_request: dict
    number: int


class ReviewResult(BaseModel):
    path: str
    analisis: dict[str, AgentReview] = Field(default_factory=dict)
