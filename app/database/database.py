"""
Async SQLAlchemy engine and session factory.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all ORM tables on startup (dev convenience; use Alembic for prod)."""
    from sqlalchemy import text
    async with engine.begin() as conn:
        from app.database import models  # noqa: F401 — import triggers table registration
        # Use checkfirst=True (which is already the default) but also
        # catch any integrity errors that can occur with PostgreSQL type conflicts
        try:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        except Exception as e:
            # If tables already exist, that's fine
            if "already exists" in str(e) or "duplicate key" in str(e):
                pass
            else:
                raise
