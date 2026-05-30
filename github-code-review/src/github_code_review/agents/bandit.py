from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import select

from github_code_review.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

EXTENSION_MAP = {
    ".py": 0,
    ".js": 1,
    ".ts": 2,
    ".java": 3,
    ".go": 4,
    ".rb": 5,
    ".php": 6,
    ".cs": 7,
}

AGENT_NAMES = [
    "seguridad",
    "estructuras",
    "calidad",
    "performance",
    "documentacion",
]


@dataclass
class AgentWeights:
    w: list[float] = field(default_factory=lambda: [0.0] * 9)
    alpha: float = settings.bandit_alpha
    beta: float = settings.bandit_beta


@dataclass
class BanditState:
    weights: dict[str, AgentWeights] = field(default_factory=dict)
    epsilon: float = settings.bandit_epsilon
    count: int = 0

    def __post_init__(self) -> None:
        if not self.weights:
            self.weights = {name: AgentWeights() for name in AGENT_NAMES}

    async def load(self, db: AsyncSession) -> None:
        from github_code_review.database import AgentBanditState, BanditGlobalState

        rows = await db.stream(select(AgentBanditState))
        async for row in rows:
            row = row[0]
            self.weights[row.agent_name] = AgentWeights(
                w=list(row.weights or [0.0] * 9),
                alpha=row.alpha or settings.bandit_alpha,
                beta=row.beta or settings.bandit_beta,
            )

        global_row = await db.get(BanditGlobalState, 1)
        if global_row is not None:
            self.epsilon = global_row.epsilon
            self.count = global_row.count

    async def save(self, db: AsyncSession) -> None:
        from github_code_review.database import AgentBanditState, BanditGlobalState

        for name, aw in self.weights.items():
            row = await db.get(AgentBanditState, name)
            if row is None:
                row = AgentBanditState(agent_name=name)
                db.add(row)
            row.weights = aw.w
            row.alpha = aw.alpha
            row.beta = aw.beta

        global_row = await db.get(BanditGlobalState, 1)
        if global_row is None:
            global_row = BanditGlobalState(id=1)
            db.add(global_row)
        global_row.epsilon = self.epsilon
        global_row.count = self.count

        await db.commit()


def build_features(file_ext: str, lines_changed: int) -> list[float]:
    idx = EXTENSION_MAP.get(file_ext, -1)
    exts = [1.0 if i == idx else 0.0 for i in range(8)]
    exts.append(min(lines_changed / settings.max_changed_lines, 1.0))
    return exts


def should_run_agent(
    state: BanditState, agent: str, features: list[float]
) -> tuple[bool, float]:
    w = state.weights[agent]
    score = sum(wi * f for wi, f in zip(w.w, features))
    explore = random.random() < state.epsilon
    run = explore if random.random() < 0.5 else score > 0
    return run, score


def update_weights(
    state: BanditState,
    agent: str,
    features: list[float],
    score: float,
    reward: float,
) -> None:
    w = state.weights[agent]
    lr = w.alpha if reward > 0 else w.beta
    for i, f in enumerate(features):
        w.w[i] += lr * (reward - score) * f


def maybe_decay_epsilon(state: BanditState) -> None:
    state.count += 1
    if (
        state.count % settings.bandit_decay_interval == 0
        and state.epsilon > settings.bandit_epsilon_min
    ):
        state.epsilon = max(
            settings.bandit_epsilon_min, state.epsilon * settings.bandit_epsilon_decay
        )
