"""
SQLAlchemy database models for SimpleCrawl.
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Generator

from sqlalchemy import String, Integer, Text, DateTime, Boolean, JSON, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy.pool import QueuePool


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Global engine cache for connection pooling
_engine_cache: dict = {}


class CrawlJob(Base):
    """Model for crawl jobs."""
    
    __tablename__ = "crawl_jobs"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    total: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class BatchJob(Base):
    """Model for batch scraping jobs."""
    
    __tablename__ = "batch_jobs"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    total: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Monitor(Base):
    """Model for content change monitoring."""
    
    __tablename__ = "monitors"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_check: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def get_engine(database_url: str):
    """
    Get or create a database engine with connection pooling.

    Uses a global cache to ensure only one engine is created per database URL.

    Args:
        database_url: SQLAlchemy database URL

    Returns:
        SQLAlchemy engine
    """
    if database_url not in _engine_cache:
        # Configure connection pooling
        # SQLite doesn't support connection pooling the same way
        if database_url.startswith("sqlite"):
            _engine_cache[database_url] = create_engine(
                database_url,
                echo=False,
                connect_args={"check_same_thread": False}
            )
        else:
            _engine_cache[database_url] = create_engine(
                database_url,
                echo=False,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600
            )
    return _engine_cache[database_url]


def init_db(database_url: str) -> None:
    """
    Initialize the database and create all tables.

    Args:
        database_url: SQLAlchemy database URL
    """
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)


def get_session(database_url: str) -> Session:
    """
    Get a database session.

    Uses the cached engine for connection pooling.

    Args:
        database_url: SQLAlchemy database URL

    Returns:
        Database session
    """
    engine = get_engine(database_url)
    return Session(engine)


@contextmanager
def get_session_context(database_url: str) -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic cleanup.

    Usage:
        with get_session_context(url) as db:
            db.query(...)

    Args:
        database_url: SQLAlchemy database URL

    Yields:
        Database session
    """
    session = get_session(database_url)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
