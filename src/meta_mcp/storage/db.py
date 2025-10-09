"""Database utilities for async SQLAlchemy usage."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..config import get_settings
from .models import Base


_engine: AsyncEngine | None = None
_SessionFactory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return singleton async engine."""

    global _engine, _SessionFactory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False, future=True)
        _SessionFactory = async_sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = get_engine()
    assert _SessionFactory is not None  # for type checkers, set when engine is built
    return _SessionFactory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a transactional scope for database work."""

    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:  # pragma: no cover - defensive rollback path
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_models() -> None:
    """Create database tables if they do not exist (development only)."""

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = ["get_engine", "session_scope", "init_models", "get_session_factory"]
