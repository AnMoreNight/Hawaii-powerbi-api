"""
Database connection and session management.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
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
        "timeout": 30.0,  # Increase timeout for better reliability
    },
    pool_pre_ping=True,  # Verify connections before using
    pool_size=1,  # Use single connection for SQLite to avoid isolation issues
    max_overflow=0,
)

# Enable WAL mode for SQLite (Write-Ahead Logging)
# This ensures better concurrency and immediate visibility of writes
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL mode and other SQLite optimizations."""
    cursor = dbapi_conn.cursor()
    # Enable WAL mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL")
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys=ON")
    # Set synchronous mode to NORMAL (good balance between safety and performance)
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Set busy timeout
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()
    logger.info("SQLite WAL mode enabled and optimizations applied")

# Create async session maker
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
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
            # Enable WAL mode explicitly during initialization
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
            
            # Create all tables if they don't exist
            # This is safe to run multiple times - won't recreate existing tables
            await conn.run_sync(Base.metadata.create_all)
            
            # Checkpoint WAL to ensure everything is written
            await conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            
        logger.info("✅ Database tables initialized successfully (created if not existed)")
        logger.info("✅ SQLite WAL mode enabled for better concurrency")
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
