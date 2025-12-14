"""
SQLAlchemy database models for SimpleCrawl.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, Boolean, JSON, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


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


def init_db(database_url: str) -> None:
    """
    Initialize the database and create all tables.
    
    Args:
        database_url: SQLAlchemy database URL
    """
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)


def get_session(database_url: str) -> Session:
    """
    Get a database session.
    
    Args:
        database_url: SQLAlchemy database URL
    
    Returns:
        Database session
    """
    engine = create_engine(database_url, echo=False)
    return Session(engine)
