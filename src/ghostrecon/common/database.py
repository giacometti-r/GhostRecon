from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from ghostrecon.common.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


@dataclass(frozen=True)
class SchemaReadiness:
    ready: bool
    reason: str | None = None
    missing_tables: tuple[str, ...] = ()
    error: str | None = None


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        resolved = settings or get_settings()
        _engine = create_async_engine(str(resolved.database_url), pool_pre_ping=True)
    return _engine


def get_session_factory(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(settings), expire_on_commit=False, autoflush=False
        )
    return _session_factory


@asynccontextmanager
async def session_scope(settings: Settings | None = None) -> AsyncIterator[AsyncSession]:
    factory = get_session_factory(settings)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_database_schema_ready(settings: Settings | None = None) -> SchemaReadiness:
    from ghostrecon.models import db as _db_models  # noqa: F401

    expected_tables = set(Base.metadata.tables) | {"alembic_version"}
    try:
        engine = get_engine(settings)
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    """
                )
            )
            existing_tables = {str(row[0]) for row in result}
    except Exception as exc:
        return SchemaReadiness(
            ready=False,
            reason="database schema readiness check failed",
            error=str(exc),
        )

    missing_tables = tuple(sorted(expected_tables - existing_tables))
    if missing_tables:
        return SchemaReadiness(
            ready=False,
            reason="database schema is not migrated",
            missing_tables=missing_tables,
        )
    return SchemaReadiness(ready=True)
