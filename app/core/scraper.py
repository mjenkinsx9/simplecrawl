"""
Core scraping functionality using Playwright.

Also handles document parsing (PDF, DOCX) via direct download.
"""

import asyncio
import base64
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

from app.config import settings
from app.core.browser import browser_pool
from app.core.actions import execute_actions
from app.utils.markdown import html_to_markdown, html_to_markdown_smart
from app.utils.media import extract_media
from app.utils.logger import get_logger
from app.utils.url_validator import validate_url
from app.utils.documents import (
    is_document_url,
    parse_document_url,
    DocumentParseError,
    DOCUMENT_EXTENSIONS
)

logger = get_logger(__name__)


class SSRFBlockedError(Exception):
    """Raised when a URL is blocked due to SSRF protection."""
    pass


class DocumentError(Exception):
    """Raised when document parsing fails."""
    pass


async def scrape_url(
    url: str,
    formats: List[str],
    exclude_tags: Optional[List[str]] = None,
    wait_for_selector: Optional[str] = None,
    timeout: int = 30000,
    actions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Scrape a single URL and return data in requested formats.

    Automatically detects and handles documents (PDF, DOCX) differently from web pages.

    Args:
        url: URL to scrape
        formats: List of output formats (markdown, html, screenshot, links, metadata, media)
        exclude_tags: HTML tags to exclude from markdown
        wait_for_selector: CSS selector to wait for
        timeout: Timeout in milliseconds
        actions: Page actions to execute (only for web pages)

    Returns:
        Dictionary with scraped data
    """
    logger.info("scrape_started", url=url, formats=formats)

    # Validate URL to prevent SSRF attacks
    is_valid, error = validate_url(url)
    if not is_valid:
        logger.warning("ssrf_blocked", url=url, reason=error)
        raise SSRFBlockedError(f"URL blocked by SSRF protection: {error}")

    # Check if URL is a document by extension first (fast path)
    is_doc, doc_type = is_document_url(url)

    # If not obvious from extension, do a HEAD request to check content-type
    if not is_doc:
        is_doc, doc_type = await _check_content_type(url, timeout)

    # Handle documents differently - use direct parsing instead of browser
    if is_doc:
        logger.info("document_detected", url=url, type=doc_type)
        try:
            return await parse_document_url(url, formats, timeout)
        except DocumentParseError as e:
            logger.error("document_parse_failed", url=url, error=str(e))
            raise DocumentError(f"Failed to parse document: {str(e)}")

    result = {}

    try:
        async with browser_pool.get_page() as page:
            # Navigate to URL
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            
            # Wait for specific selector if provided
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=timeout)
            
            # Execute page actions if provided
            if actions:
                await execute_actions(page, actions)
            
            # Get HTML content
            html_content = await page.content()

            # Extract markdown with smart extraction
            if "markdown" in formats:
                smart_result = html_to_markdown_smart(html_content, exclude_tags)
                result["markdown"] = smart_result["markdown"]
                result["quality_score"] = smart_result["quality_score"]
                result["extraction_method"] = smart_result["method"]

            # Get raw HTML
            if "html" in formats:
                result["html"] = html_content
            
            # Take screenshot
            if "screenshot" in formats:
                screenshot_bytes = await page.screenshot(full_page=True, type="png")
                result["screenshot"] = base64.b64encode(screenshot_bytes).decode()
            
            # Extract links
            if "links" in formats:
                result["links"] = await extract_links(page, url)
            
            # Extract metadata
            if "metadata" in formats:
                result["metadata"] = await extract_metadata(page, url)
            
            # Extract media
            if "media" in formats:
                import os
                job_media_dir = os.path.join(settings.media_storage_dir, "scrape")
                result["media"] = await extract_media(page, url, job_media_dir)
            
            logger.info("scrape_completed", url=url)
            return result
    
    except PlaywrightTimeout as e:
        logger.error("scrape_timeout", url=url, error=str(e))
        raise Exception(f"Timeout while scraping {url}: {str(e)}")
    except Exception as e:
        logger.error("scrape_failed", url=url, error=str(e))
        raise


async def extract_links(page: Page, base_url: str) -> List[str]:
    """
    Extract all links from a page.
    
    Args:
        page: Playwright page
        base_url: Base URL for resolving relative links
    
    Returns:
        List of absolute URLs
    """
    links = await page.evaluate("""
        () => {
            const anchors = Array.from(document.querySelectorAll('a[href]'));
            return anchors.map(a => a.href).filter(href => href && !href.startsWith('#'));
        }
    """)
    
    # Convert to absolute URLs and deduplicate
    absolute_links = []
    seen = set()
    
    for link in links:
        absolute_link = urljoin(base_url, link)
        if absolute_link not in seen:
            seen.add(absolute_link)
            absolute_links.append(absolute_link)
    
    return absolute_links


async def extract_metadata(page: Page, url: str) -> Dict[str, Any]:
    """
    Extract page metadata.
    
    Args:
        page: Playwright page
        url: Page URL
    
    Returns:
        Dictionary with metadata
    """
    metadata = await page.evaluate("""
        () => {
            const getMeta = (name) => {
                const meta = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
                return meta ? meta.content : null;
            };
            
            return {
                title: document.title || null,
                description: getMeta('description') || getMeta('og:description'),
                language: document.documentElement.lang || 'en',
                keywords: getMeta('keywords'),
                author: getMeta('author'),
                ogTitle: getMeta('og:title'),
                ogDescription: getMeta('og:description'),
                ogImage: getMeta('og:image'),
                ogUrl: getMeta('og:url'),
                ogType: getMeta('og:type'),
                ogSiteName: getMeta('og:site_name'),
                twitterCard: getMeta('twitter:card'),
                twitterTitle: getMeta('twitter:title'),
                twitterDescription: getMeta('twitter:description'),
                twitterImage: getMeta('twitter:image')
            };
        }
    """)
    
    # Add source URL and status code
    metadata["sourceURL"] = url
    metadata["statusCode"] = 200  # If we got here, it's 200
    
    return metadata


def batch_scrape_urls(job_id: str, urls: List[str], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape multiple URLs in batch (synchronous wrapper for Celery).
    
    Args:
        job_id: Job identifier
        urls: List of URLs to scrape
        config: Scrape configuration
    
    Returns:
        Batch results
    """
    logger.info("batch_scrape_started", job_id=job_id, url_count=len(urls))
    
    # Run async scraping
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        results = loop.run_until_complete(_batch_scrape_async(urls, config))
        logger.info("batch_scrape_completed", job_id=job_id)
        return {"results": results}
    finally:
        loop.close()


async def _batch_scrape_async(urls: List[str], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Async implementation of batch scraping.
    
    Args:
        urls: List of URLs to scrape
        config: Scrape configuration
    
    Returns:
        List of scrape results
    """
    formats = config.get("formats", ["markdown"])
    exclude_tags = config.get("exclude_tags")
    timeout = config.get("timeout", 30000)
    
    # Scrape URLs concurrently with limit
    semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
    
    async def scrape_with_semaphore(url: str) -> Dict[str, Any]:
        async with semaphore:
            try:
                data = await scrape_url(url, formats, exclude_tags, timeout=timeout)
                return {"url": url, "success": True, "data": data}
            except Exception as e:
                logger.error("batch_scrape_url_failed", url=url, error=str(e))
                return {"url": url, "success": False, "error": str(e)}
    
    tasks = [scrape_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks)

    return results


async def _check_content_type(url: str, timeout: int = 30000) -> tuple:
    """
    Check URL content-type via HEAD request to detect documents.

    Args:
        url: URL to check
        timeout: Timeout in milliseconds

    Returns:
        Tuple of (is_document, document_type)
    """
    try:
        timeout_seconds = timeout / 1000
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.head(url, follow_redirects=True)
            content_type = response.headers.get('content-type', '')
            return is_document_url(url, content_type)
    except Exception as e:
        # If HEAD request fails, just return False and let scraper try normally
        logger.debug("content_type_check_failed", url=url, error=str(e))
        return False, None
