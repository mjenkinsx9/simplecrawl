"""
Search endpoint for web search + scrape functionality.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.core.search import search_and_scrape, SearchError
from app.models.responses import SearchScrapeResponse, SearchResult, ScrapeData
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class SearchScrapeRequest(BaseModel):
    """Request model for search + scrape."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query string"
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of results to scrape (1-20)"
    )
    formats: List[str] = Field(
        default=["markdown", "metadata"],
        description="Output formats for scraping"
    )
    region: str = Field(
        default="wt-wt",
        description="Search region code (wt-wt = worldwide)"
    )
    timeout: int = Field(
        default=30000,
        ge=5000,
        le=120000,
        description="Timeout per page in milliseconds"
    )


@router.post("/search", response_model=SearchScrapeResponse)
@limiter.limit(f"{settings.rate_limit_requests}/minute")
async def search_scrape(request: Request, search_request: SearchScrapeRequest):
    """
    Search the web and scrape each result.

    This endpoint performs a web search using DuckDuckGo and then
    scrapes each result page to extract content in the requested formats.

    Example:
    ```json
    {
      "query": "python web scraping tutorial",
      "max_results": 5,
      "formats": ["markdown", "metadata"]
    }
    ```

    Returns search results with scraped content including:
    - markdown: Clean, LLM-ready markdown
    - metadata: Page metadata (title, description, etc.)
    - quality_score: Content quality rating (0.0-1.0)
    """
    try:
        logger.info(
            "search_scrape_request",
            query=search_request.query,
            max_results=search_request.max_results
        )

        result = await search_and_scrape(
            query=search_request.query,
            max_results=search_request.max_results,
            formats=search_request.formats,
            region=search_request.region,
            timeout=search_request.timeout
        )

        # Convert results to response model
        search_results = []
        for r in result.get("results", []):
            scrape_data = None
            if r.get("success") and r.get("data"):
                scrape_data = ScrapeData(**r["data"])

            search_results.append(SearchResult(
                url=r["url"],
                title=r.get("title"),
                snippet=r.get("snippet"),
                success=r.get("success", False),
                data=scrape_data,
                error=r.get("error")
            ))

        return SearchScrapeResponse(
            success=True,
            query=search_request.query,
            result_count=len(search_results),
            results=search_results
        )

    except SearchError as e:
        logger.error("search_failed", query=search_request.query, error=str(e))
        return SearchScrapeResponse(
            success=False,
            query=search_request.query,
            result_count=0,
            error={
                "code": "SEARCH_FAILED",
                "message": str(e)
            }
        )

    except Exception as e:
        logger.error("search_scrape_failed", query=search_request.query, error=str(e))
        return SearchScrapeResponse(
            success=False,
            query=search_request.query,
            result_count=0,
            error={
                "code": "SEARCH_SCRAPE_FAILED",
                "message": str(e)
            }
        )
