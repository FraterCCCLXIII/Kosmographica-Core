from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def verify_database_connection() -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SELECT 1"))


async def ensure_workspace_tables() -> None:
    from app.models.workspace import Project, Workspace

    async with engine.begin() as connection:
        await connection.run_sync(lambda sync_connection: Workspace.__table__.create(sync_connection, checkfirst=True))
        await connection.run_sync(lambda sync_connection: Project.__table__.create(sync_connection, checkfirst=True))
