"""
Database connection and session management.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import DATABASE_URL
from models import Base
import logging

logger = logging.getLogger(__name__)

# Create async engine for SQLite
# SQLite uses aiosqlite for async operations
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,  # SQLite-specific: allow multi-threaded access
    },
    pool_pre_ping=True,  # Verify connections before using
)

# Create async session maker
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """
    Initialize database tables.
    Automatically creates all tables defined in models if they don't exist.
    This runs on application startup.
    """
    try:
        logger.info("Initializing database tables...")
        async with engine.begin() as conn:
            # Create all tables if they don't exist
            # This is safe to run multiple times - won't recreate existing tables
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables initialized successfully (created if not existed)")
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"⚠️  Failed to initialize database: {error_msg}")
        logger.warning("The application will start, but database endpoints (/sync) will not work.")
        logger.warning("Please check your DATABASE_URL in .env file")
        logger.warning("Example: DATABASE_URL=sqlite+aiosqlite:///./reservations.db")
        # Don't raise - allow app to start for endpoints that don't need database
        # Database connection will be checked when actually needed


async def close_db():
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connection closed")
