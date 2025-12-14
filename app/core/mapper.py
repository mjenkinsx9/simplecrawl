"""
Site mapping functionality for discovering URLs on a website.
"""

import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

# Use defusedxml to prevent XXE attacks
import defusedxml.ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from app.core.browser import browser_pool
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def map_website(url: str, search: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Map a website by discovering all URLs.
    
    Args:
        url: Base URL to map
        search: Optional search term to filter URLs
    
    Returns:
        List of discovered links with metadata
    """
    logger.info("map_started", url=url, search=search)
    
    parsed_url = urlparse(url)
    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Try to get sitemap first
    sitemap_urls = await try_sitemap(base_domain)
    
    # If no sitemap or few URLs, crawl the homepage
    if len(sitemap_urls) < 5:
        homepage_urls = await extract_urls_from_page(url)
        sitemap_urls.extend(homepage_urls)
    
    # Deduplicate
    unique_urls = list({link["url"]: link for link in sitemap_urls}.values())
    
    # Filter by search term if provided
    if search:
        search_lower = search.lower()
        unique_urls = [
            link for link in unique_urls
            if search_lower in link["url"].lower() or
               (link.get("title") and search_lower in link["title"].lower())
        ]
        # Sort by relevance (simple: search term in URL gets priority)
        unique_urls.sort(key=lambda x: search_lower in x["url"].lower(), reverse=True)
    
    logger.info("map_completed", url=url, link_count=len(unique_urls))
    return unique_urls


async def try_sitemap(base_url: str) -> List[Dict[str, Any]]:
    """
    Try to fetch and parse sitemap.xml.
    
    Args:
        base_url: Base URL of the website
    
    Returns:
        List of URLs from sitemap
    """
    sitemap_urls = [
        f"{base_url}/sitemap.xml",
        f"{base_url}/sitemap_index.xml",
        f"{base_url}/sitemap-index.xml"
    ]
    
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for sitemap_url in sitemap_urls:
            try:
                response = await client.get(sitemap_url)
                if response.status_code == 200:
                    return parse_sitemap(response.text)
            except Exception as e:
                logger.debug("sitemap_fetch_failed", url=sitemap_url, error=str(e))
    
    return []


def parse_sitemap(xml_content: str) -> List[Dict[str, Any]]:
    """
    Parse sitemap XML and extract URLs.
    
    Args:
        xml_content: Sitemap XML content
    
    Returns:
        List of URL dictionaries
    """
    try:
        root = ET.fromstring(xml_content)
        
        # Handle different sitemap namespaces
        namespaces = {
            'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
            'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'
        }
        
        urls = []
        
        # Try to find <url> elements
        for url_elem in root.findall('.//sm:url', namespaces) or root.findall('.//ns:url', namespaces) or root.findall('.//url'):
            loc = url_elem.find('.//sm:loc', namespaces) or url_elem.find('.//ns:loc', namespaces) or url_elem.find('.//loc')
            if loc is not None and loc.text:
                urls.append({
                    "url": loc.text.strip(),
                    "title": None,
                    "description": None
                })
        
        return urls
    except Exception as e:
        logger.warning("sitemap_parse_failed", error=str(e))
        return []


async def extract_urls_from_page(url: str) -> List[Dict[str, Any]]:
    """
    Extract all URLs from a page using Playwright.
    
    Args:
        url: Page URL
    
    Returns:
        List of URL dictionaries with metadata
    """
    try:
        async with browser_pool.get_page() as page:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Extract links with metadata
            links = await page.evaluate("""
                () => {
                    const anchors = Array.from(document.querySelectorAll('a[href]'));
                    return anchors.map(a => ({
                        url: a.href,
                        title: a.textContent?.trim() || a.title || null,
                        description: a.getAttribute('aria-label') || null
                    })).filter(link => link.url && !link.url.startsWith('#'));
                }
            """)
            
            # Deduplicate by URL
            unique_links = list({link["url"]: link for link in links}.values())
            
            return unique_links
    
    except Exception as e:
        logger.error("extract_urls_failed", url=url, error=str(e))
        return []
