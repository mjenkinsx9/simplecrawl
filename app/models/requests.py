"""
Pydantic request models for API endpoints.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator

# Maximum limits for input validation
MAX_CRAWL_DEPTH = 50
MAX_CRAWL_PAGES = 5000
MAX_BATCH_URLS = 100
MAX_EXTRACT_URLS = 50
MAX_TIMEOUT_MS = 120000


class ScrapeRequest(BaseModel):
    """Request model for scraping a single URL."""

    url: HttpUrl = Field(..., description="URL to scrape")
    formats: List[str] = Field(
        default=["markdown"],
        description="Output formats: markdown, html, screenshot, links, metadata, media"
    )
    actions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Page actions to perform before scraping"
    )
    exclude_tags: Optional[List[str]] = Field(
        default=None,
        description="HTML tags to exclude from markdown conversion"
    )
    wait_for_selector: Optional[str] = Field(
        default=None,
        description="CSS selector to wait for before scraping"
    )
    wait_until: str = Field(
        default="domcontentloaded",
        description="Page load strategy: domcontentloaded (fast), load, or networkidle (slow but complete)"
    )
    timeout: int = Field(
        default=30000,
        ge=1000,
        le=MAX_TIMEOUT_MS,
        description=f"Timeout in milliseconds (1000-{MAX_TIMEOUT_MS})"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Custom HTTP headers (e.g., Authorization, Cookie) for authenticated requests"
    )

    @field_validator("wait_until")
    @classmethod
    def validate_wait_until(cls, v: str) -> str:
        allowed = ["domcontentloaded", "load", "networkidle", "commit"]
        if v not in allowed:
            raise ValueError(f"wait_until must be one of: {', '.join(allowed)}")
        return v


class MapRequest(BaseModel):
    """Request model for mapping a website."""
    
    url: HttpUrl = Field(..., description="Base URL to map")
    search: Optional[str] = Field(
        default=None,
        description="Search term to filter URLs"
    )


class CrawlRequest(BaseModel):
    """Request model for crawling a website."""

    url: HttpUrl = Field(..., description="Starting URL to crawl")
    limit: int = Field(
        default=100,
        ge=1,
        le=MAX_CRAWL_PAGES,
        description=f"Maximum number of pages to crawl (1-{MAX_CRAWL_PAGES})"
    )
    depth: int = Field(
        default=3,
        ge=1,
        le=MAX_CRAWL_DEPTH,
        description=f"Maximum crawl depth (1-{MAX_CRAWL_DEPTH})"
    )
    scrape_options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Options for scraping each page"
    )
    include_patterns: Optional[List[str]] = Field(
        default=None,
        description="URL patterns to include (glob patterns)"
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="URL patterns to exclude (glob patterns)"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Custom HTTP headers for authenticated requests"
    )


class ExtractRequest(BaseModel):
    """Request model for AI-powered extraction."""

    urls: List[HttpUrl] = Field(
        ...,
        min_length=1,
        max_length=MAX_EXTRACT_URLS,
        description=f"URLs to extract data from (1-{MAX_EXTRACT_URLS})"
    )
    schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON schema for structured extraction"
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Natural language extraction prompt"
    )


class BatchScrapeRequest(BaseModel):
    """Request model for batch scraping."""

    urls: List[HttpUrl] = Field(
        ...,
        min_length=1,
        max_length=MAX_BATCH_URLS,
        description=f"List of URLs to scrape (1-{MAX_BATCH_URLS})"
    )
    formats: List[str] = Field(
        default=["markdown"],
        description="Output formats for each URL"
    )


class MonitorRequest(BaseModel):
    """Request model for content monitoring."""
    
    url: HttpUrl = Field(..., description="URL to monitor")
    webhook_url: Optional[HttpUrl] = Field(
        default=None,
        description="Webhook URL for change notifications"
    )
    interval_hours: int = Field(
        default=24,
        description="Check interval in hours"
    )
