"""SQLAlchemy engine, session factory, and the FastAPI dependency.

Async engine for the app (routes, agents, comms). A separate sync engine is
exposed for Alembic and load_seeds.py, which are both easier to reason about
synchronously.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.settings import settings
from utils.logger import get_logger

log = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for every model in db/models.py."""


# ── Async (application) ──────────────────────────────────────────────

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session and always closes it.

        @router.get("/leads")
        async def list_leads(db: AsyncSession = Depends(get_db)): ...
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for code outside a request (agents, schedulers).

        async with session_scope() as db:
            await crud.create_lead(db, {...})
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create any missing tables. Called on app startup.

    Alembic owns schema changes; this exists so a fresh clone with an empty
    database boots straight into a working demo without running migrations.
    """
    from db import models  # noqa: F401 - registers models on Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("database ready (%s tables)", len(Base.metadata.tables))


async def close_db() -> None:
    """Dispose the connection pool on shutdown."""
    await engine.dispose()


# ── Sync (Alembic, seed loader) ──────────────────────────────────────

sync_engine = create_engine(
    settings.sync_database_url,
    echo=False,
    pool_pre_ping=True,
    future=True,
)

SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, autoflush=False)
