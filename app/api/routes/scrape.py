"""
Scrape endpoint for single URL scraping.
"""

from fastapi import APIRouter, HTTPException

from app.models.requests import ScrapeRequest
from app.models.responses import ScrapeResponse, ScrapeData, ErrorResponse
from app.core.scraper import scrape_url
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequest):
    """
    Scrape a single URL and return content in requested formats.
    
    Supported formats:
    - `markdown`: Clean, LLM-ready markdown
    - `html`: Raw HTML content
    - `screenshot`: Full-page PNG screenshot (base64 encoded)
    - `links`: All URLs found on the page
    - `metadata`: Page metadata (title, description, OG tags, etc.)
    - `media`: Downloaded media files (images)
    
    Example:
    ```json
    {
      "url": "https://example.com",
      "formats": ["markdown", "metadata"],
      "exclude_tags": ["nav", "footer"],
      "timeout": 30000
    }
    ```
    """
    try:
        logger.info("scrape_request", url=str(request.url), formats=request.formats)
        
        data = await scrape_url(
            url=str(request.url),
            formats=request.formats,
            exclude_tags=request.exclude_tags,
            wait_for_selector=request.wait_for_selector,
            timeout=request.timeout,
            actions=request.actions
        )
        
        return ScrapeResponse(
            success=True,
            data=ScrapeData(**data)
        )
    
    except Exception as e:
        logger.error("scrape_request_failed", url=str(request.url), error=str(e))
        return ScrapeResponse(
            success=False,
            error={
                "code": "SCRAPE_FAILED",
                "message": str(e),
                "url": str(request.url)
            }
        )
