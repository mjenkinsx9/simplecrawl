"""
Map endpoint for discovering URLs on a website.
"""

from fastapi import APIRouter

from app.models.requests import MapRequest
from app.models.responses import MapResponse, LinkInfo
from app.core.mapper import map_website
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/map", response_model=MapResponse)
async def map_site(request: MapRequest):
    """
    Map a website by discovering all URLs.
    
    This endpoint:
    1. Tries to fetch and parse `sitemap.xml`
    2. Falls back to crawling the homepage if no sitemap
    3. Optionally filters results by search term
    
    Example:
    ```json
    {
      "url": "https://example.com",
      "search": "documentation"
    }
    ```
    
    Returns a list of discovered URLs with metadata, sorted by relevance if search is provided.
    """
    try:
        logger.info("map_request", url=str(request.url), search=request.search)
        
        links = await map_website(
            url=str(request.url),
            search=request.search
        )
        
        # Convert to LinkInfo objects
        link_infos = [LinkInfo(**link) for link in links]
        
        return MapResponse(
            success=True,
            links=link_infos
        )
    
    except Exception as e:
        logger.error("map_request_failed", url=str(request.url), error=str(e))
        return MapResponse(
            success=False,
            error={
                "code": "MAP_FAILED",
                "message": str(e),
                "url": str(request.url)
            }
        )
