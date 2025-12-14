"""
Web search functionality using DuckDuckGo.
"""

import asyncio
from typing import List, Dict, Any, Optional

from app.core.scraper import scrape_url
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import duckduckgo_search
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logger.warning("duckduckgo_search_not_available", message="Install with: pip install duckduckgo-search")


class SearchError(Exception):
    """Raised when search fails."""
    pass


def search_web(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt"
) -> List[Dict[str, Any]]:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query string
        max_results: Maximum number of results to return
        region: Region code for search (wt-wt = worldwide)

    Returns:
        List of search results with url, title, snippet
    """
    if not DDGS_AVAILABLE:
        raise SearchError("DuckDuckGo search not available. Install with: pip install duckduckgo-search")

    logger.info("web_search_started", query=query, max_results=max_results)

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                region=region,
                max_results=max_results
            ))

        # Format results
        formatted = []
        for r in results:
            formatted.append({
                "url": r.get("href", r.get("link", "")),
                "title": r.get("title", ""),
                "snippet": r.get("body", r.get("snippet", ""))
            })

        logger.info("web_search_completed", query=query, result_count=len(formatted))
        return formatted

    except Exception as e:
        logger.error("web_search_failed", query=query, error=str(e))
        raise SearchError(f"Search failed: {str(e)}")


async def search_and_scrape(
    query: str,
    max_results: int = 5,
    formats: Optional[List[str]] = None,
    region: str = "wt-wt",
    timeout: int = 30000
) -> Dict[str, Any]:
    """
    Search the web and scrape each result.

    Args:
        query: Search query string
        max_results: Maximum number of results to scrape
        formats: Output formats for scraping (default: markdown, metadata)
        region: Region code for search
        timeout: Timeout per page in milliseconds

    Returns:
        Dictionary with query, results, and scraped content
    """
    if formats is None:
        formats = ["markdown", "metadata"]

    logger.info("search_and_scrape_started", query=query, max_results=max_results)

    # Get search results
    search_results = search_web(query, max_results, region)

    # Scrape each result
    scraped_results = []

    for result in search_results:
        url = result.get("url", "")
        if not url:
            continue

        try:
            # Scrape the URL
            data = await scrape_url(
                url=url,
                formats=formats,
                timeout=timeout
            )

            scraped_results.append({
                "url": url,
                "title": result.get("title"),
                "snippet": result.get("snippet"),
                "success": True,
                "data": data
            })

            logger.debug("search_result_scraped", url=url)

        except Exception as e:
            logger.warning("search_result_scrape_failed", url=url, error=str(e))
            scraped_results.append({
                "url": url,
                "title": result.get("title"),
                "snippet": result.get("snippet"),
                "success": False,
                "error": str(e)
            })

    logger.info("search_and_scrape_completed", query=query, scraped_count=len(scraped_results))

    return {
        "query": query,
        "result_count": len(scraped_results),
        "results": scraped_results
    }


def search_and_scrape_sync(
    query: str,
    max_results: int = 5,
    formats: Optional[List[str]] = None,
    region: str = "wt-wt",
    timeout: int = 30000
) -> Dict[str, Any]:
    """
    Synchronous wrapper for search_and_scrape (for Celery tasks).

    Args:
        query: Search query string
        max_results: Maximum number of results to scrape
        formats: Output formats for scraping
        region: Region code for search
        timeout: Timeout per page in milliseconds

    Returns:
        Dictionary with query, results, and scraped content
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(
            search_and_scrape(query, max_results, formats, region, timeout)
        )
    finally:
        loop.close()
