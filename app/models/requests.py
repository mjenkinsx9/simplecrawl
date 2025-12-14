"""
Pydantic request models for API endpoints.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


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
    timeout: int = Field(
        default=30000,
        description="Timeout in milliseconds"
    )


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
        description="Maximum number of pages to crawl"
    )
    depth: int = Field(
        default=3,
        description="Maximum crawl depth"
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


class ExtractRequest(BaseModel):
    """Request model for AI-powered extraction."""
    
    urls: List[HttpUrl] = Field(..., description="URLs to extract data from")
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
    
    urls: List[HttpUrl] = Field(..., description="List of URLs to scrape")
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
