"""
Scrape endpoint for single URL scraping.
"""

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.models.requests import ScrapeRequest
from app.models.responses import ScrapeResponse, ScrapeData, ErrorResponse
from app.core.scraper import scrape_url, SSRFBlockedError
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/scrape", response_model=ScrapeResponse)
@limiter.limit(f"{settings.rate_limit_requests}/minute")
async def scrape(request: Request, scrape_request: ScrapeRequest):
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
        logger.info("scrape_request", url=str(scrape_request.url), formats=scrape_request.formats)

        data = await scrape_url(
            url=str(scrape_request.url),
            formats=scrape_request.formats,
            exclude_tags=scrape_request.exclude_tags,
            wait_for_selector=scrape_request.wait_for_selector,
            timeout=scrape_request.timeout,
            actions=scrape_request.actions
        )

        return ScrapeResponse(
            success=True,
            data=ScrapeData(**data)
        )

    except SSRFBlockedError as e:
        logger.warning("ssrf_blocked", url=str(scrape_request.url), error=str(e))
        return ScrapeResponse(
            success=False,
            error={
                "code": "SSRF_BLOCKED",
                "message": "URL blocked by security policy",
                "url": str(scrape_request.url)
            }
        )

    except Exception as e:
        logger.error("scrape_request_failed", url=str(scrape_request.url), error=str(e))
        return ScrapeResponse(
            success=False,
            error={
                "code": "SCRAPE_FAILED",
                "message": str(e),
                "url": str(scrape_request.url)
            }
        )
