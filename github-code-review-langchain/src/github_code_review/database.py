from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from github_code_review.config import settings


class Base(DeclarativeBase):
    pass


class AgentBanditState(Base):
    __tablename__ = "agent_bandit_state"

    agent_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    weights: Mapped[list[float]] = mapped_column(
        ARRAY(Float), nullable=False, default=list
    )
    alpha: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    beta: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BanditGlobalState(Base):
    __tablename__ = "bandit_global_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    epsilon: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReviewHistory(Base):
    __tablename__ = "review_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pr_head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
_SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    return _SessionLocal()


async def init_db() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await _engine.dispose()
