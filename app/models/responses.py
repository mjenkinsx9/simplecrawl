"""
Pydantic response models for API endpoints.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class MediaItem(BaseModel):
    """Model for media file information."""
    
    url: str = Field(..., description="Original media URL")
    filename: str = Field(..., description="Local filename")
    type: str = Field(..., description="MIME type")
    size: int = Field(..., description="File size in bytes")


class DocumentImage(BaseModel):
    """Model for images extracted from documents (PDF/DOCX)."""

    page: Optional[int] = Field(None, description="Page number (for PDFs)")
    index: Optional[int] = Field(None, description="Image index on page")
    format: str = Field(..., description="Image format (png, jpeg, etc.)")
    data: str = Field(..., description="Base64-encoded image data")
    width: Optional[int] = Field(None, description="Image width in pixels")
    height: Optional[int] = Field(None, description="Image height in pixels")
    content_type: Optional[str] = Field(None, description="MIME content type")


class ScrapeData(BaseModel):
    """Model for scraped page data or parsed document."""

    markdown: Optional[str] = None
    html: Optional[str] = None
    text: Optional[str] = Field(None, description="Plain text content (for documents)")
    screenshot: Optional[str] = None
    links: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    media: Optional[List[MediaItem]] = None
    # Quality metadata from smart extraction
    quality_score: Optional[float] = Field(None, description="Content quality score 0.0-1.0")
    extraction_method: Optional[str] = Field(None, description="Method used: trafilatura, markdownify, pdf_parser, or docx_parser")
    # Document-specific fields
    document_type: Optional[str] = Field(None, description="Document type if URL was a document: pdf, docx")
    images: Optional[List[DocumentImage]] = Field(None, description="Images extracted from document")


class ScrapeResponse(BaseModel):
    """Response model for scrape endpoint."""
    
    success: bool = Field(..., description="Whether the request succeeded")
    data: Optional[ScrapeData] = None
    error: Optional[Dict[str, Any]] = None


class LinkInfo(BaseModel):
    """Model for link information."""
    
    url: str = Field(..., description="URL")
    title: Optional[str] = Field(None, description="Page title")
    description: Optional[str] = Field(None, description="Page description")


class MapResponse(BaseModel):
    """Response model for map endpoint."""
    
    success: bool = Field(..., description="Whether the request succeeded")
    links: Optional[List[LinkInfo]] = None
    error: Optional[Dict[str, Any]] = None


class JobResponse(BaseModel):
    """Response model for job submission."""
    
    success: bool = Field(..., description="Whether the request succeeded")
    id: Optional[str] = Field(None, description="Job ID")
    status_url: Optional[str] = Field(None, description="URL to check job status")
    error: Optional[Dict[str, Any]] = None


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    
    status: str = Field(..., description="Job status: pending, running, completed, failed")
    total: int = Field(..., description="Total number of items")
    completed: int = Field(..., description="Number of completed items")
    failed: int = Field(..., description="Number of failed items")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Job results")
    created_at: Optional[datetime] = Field(None, description="Job creation time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    error: Optional[str] = Field(None, description="Error message if failed")


class ExtractResponse(BaseModel):
    """Response model for extract endpoint."""
    
    success: bool = Field(..., description="Whether the request succeeded")
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class MonitorResponse(BaseModel):
    """Response model for monitor endpoint."""
    
    success: bool = Field(..., description="Whether the request succeeded")
    monitor_id: Optional[str] = None
    next_check: Optional[datetime] = None
    error: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = Field(default=False)
    error: Dict[str, Any] = Field(..., description="Error details")


class SearchResult(BaseModel):
    """Model for a single search result."""

    url: str = Field(..., description="URL of the search result")
    title: Optional[str] = Field(None, description="Page title from search")
    snippet: Optional[str] = Field(None, description="Search result snippet")
    success: bool = Field(..., description="Whether scraping succeeded")
    data: Optional[ScrapeData] = Field(None, description="Scraped content")
    error: Optional[str] = Field(None, description="Error message if scraping failed")


class SearchScrapeResponse(BaseModel):
    """Response model for search+scrape endpoint."""

    success: bool = Field(..., description="Whether the request succeeded")
    query: str = Field(..., description="The search query used")
    result_count: int = Field(..., description="Number of results returned")
    results: Optional[List[SearchResult]] = Field(None, description="Search results with scraped content")
    error: Optional[Dict[str, Any]] = None
