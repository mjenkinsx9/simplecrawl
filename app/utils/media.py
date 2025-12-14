"""
Media extraction and downloading utilities.
"""

import os
import hashlib
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import mimetypes

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Page

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def extract_media(page: Page, base_url: str, storage_dir: str) -> List[Dict[str, Any]]:
    """
    Extract and download media files from a page.
    
    Args:
        page: Playwright page
        base_url: Base URL for resolving relative URLs
        storage_dir: Directory to save media files
    
    Returns:
        List of media file information
    """
    logger.info("media_extraction_started", url=base_url)
    
    # Get page HTML
    html = await page.content()
    soup = BeautifulSoup(html, 'lxml')
    
    # Extract image URLs
    media_urls = []
    
    # From <img> tags
    for img in soup.find_all('img'):
        src = img.get('src')
        if src:
            media_urls.append(urljoin(base_url, src))
    
    # From <picture> sources
    for source in soup.find_all('source'):
        srcset = source.get('srcset')
        if srcset:
            # Parse srcset (can contain multiple URLs)
            for item in srcset.split(','):
                url = item.strip().split()[0]
                media_urls.append(urljoin(base_url, url))
    
    # From CSS background-image (basic extraction)
    for elem in soup.find_all(style=True):
        style = elem.get('style', '')
        if 'background-image' in style:
            # Extract URL from url(...)
            import re
            urls = re.findall(r'url\([\'"]?([^\'"]+)[\'"]?\)', style)
            for url in urls:
                media_urls.append(urljoin(base_url, url))
    
    # Deduplicate
    media_urls = list(set(media_urls))
    
    # Filter by supported formats
    supported_formats = settings.media_formats_list
    filtered_urls = []
    for url in media_urls:
        ext = get_file_extension(url)
        if ext and ext.lower() in supported_formats:
            filtered_urls.append(url)
    
    logger.info("media_urls_found", count=len(filtered_urls))
    
    # Download media files
    media_items = []
    os.makedirs(storage_dir, exist_ok=True)
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for url in filtered_urls[:50]:  # Limit to 50 files
            try:
                media_info = await download_media(client, url, storage_dir)
                if media_info:
                    media_items.append(media_info)
            except Exception as e:
                logger.warning("media_download_failed", url=url, error=str(e))
    
    logger.info("media_extraction_completed", count=len(media_items))
    return media_items


async def download_media(client: httpx.AsyncClient, url: str, storage_dir: str) -> Optional[Dict[str, Any]]:
    """
    Download a media file.
    
    Args:
        client: HTTP client
        url: Media URL
        storage_dir: Storage directory
    
    Returns:
        Media file information or None if failed
    """
    try:
        # Download file
        response = await client.get(url)
        response.raise_for_status()
        
        # Check size
        content_length = len(response.content)
        if content_length > settings.max_media_size_bytes:
            logger.warning("media_too_large", url=url, size=content_length)
            return None
        
        # Determine MIME type
        content_type = response.headers.get('content-type', '').split(';')[0].strip()
        if not content_type:
            content_type = mimetypes.guess_type(url)[0] or 'application/octet-stream'
        
        # Generate filename
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        ext = get_file_extension(url) or guess_extension(content_type) or 'bin'
        filename = f"media_{url_hash}.{ext}"
        filepath = os.path.join(storage_dir, filename)
        
        # Save file
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        return {
            "url": url,
            "filename": filename,
            "type": content_type,
            "size": content_length
        }
    
    except Exception as e:
        logger.error("media_download_error", url=url, error=str(e))
        return None


def get_file_extension(url: str) -> Optional[str]:
    """
    Get file extension from URL.
    
    Args:
        url: File URL
    
    Returns:
        File extension without dot, or None
    """
    parsed = urlparse(url)
    path = parsed.path
    
    # Remove query parameters
    if '?' in path:
        path = path.split('?')[0]
    
    # Get extension
    if '.' in path:
        ext = path.rsplit('.', 1)[-1].lower()
        # Remove any trailing slashes
        ext = ext.rstrip('/')
        return ext if ext else None
    
    return None


def guess_extension(mime_type: str) -> Optional[str]:
    """
    Guess file extension from MIME type.
    
    Args:
        mime_type: MIME type
    
    Returns:
        File extension without dot, or None
    """
    mime_map = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp',
        'image/avif': 'avif',
        'image/svg+xml': 'svg'
    }
    
    return mime_map.get(mime_type.lower())
