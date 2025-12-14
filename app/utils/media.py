"""
Media extraction and downloading utilities.

Supports:
- Standard <img src> tags
- <picture> and <source> elements with srcset
- Lazy-loaded images (data-src, data-srcset)
- Next.js optimized images (/_next/image?url=...)
- CSS background-image
"""

import os
import re
import hashlib
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import mimetypes

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Page

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def extract_nextjs_image_url(url: str) -> Optional[str]:
    """
    Extract the original image URL from Next.js image optimization URLs.

    Next.js uses: /_next/image?url=ENCODED_URL&w=WIDTH&q=QUALITY

    Args:
        url: Potentially a Next.js optimized image URL

    Returns:
        The original image URL, or None if not a Next.js URL
    """
    if '/_next/image' not in url:
        return None

    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        if 'url' in params:
            original_url = unquote(params['url'][0])
            # If it's a relative URL, make it absolute using the base
            if original_url.startswith('/'):
                base = f"{parsed.scheme}://{parsed.netloc}"
                return urljoin(base, original_url)
            return original_url
    except Exception:
        pass

    return None


def extract_srcset_urls(srcset: str, base_url: str) -> List[str]:
    """
    Parse srcset attribute and extract all image URLs.

    Srcset format: "url1 1x, url2 2x" or "url1 100w, url2 200w"

    Args:
        srcset: The srcset attribute value
        base_url: Base URL for resolving relative URLs

    Returns:
        List of absolute URLs from the srcset
    """
    urls = []
    for item in srcset.split(','):
        item = item.strip()
        if not item:
            continue
        # URL is the first part before any space
        url = item.split()[0]
        if url:
            urls.append(urljoin(base_url, url))
    return urls


async def extract_media(page: Page, base_url: str, storage_dir: str) -> List[Dict[str, Any]]:
    """
    Extract and download media files from a page.

    Handles:
    - Standard <img src> and srcset
    - Lazy-loaded images (data-src, data-srcset, data-lazy-src)
    - Next.js optimized images (/_next/image?url=...)
    - <picture> and <source> elements
    - CSS background-image

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

    # Use a set to deduplicate as we go
    media_urls: Set[str] = set()

    def add_url(url: str):
        """Add URL to set, handling Next.js optimization."""
        if not url or url.startswith('data:'):
            return

        absolute_url = urljoin(base_url, url)

        # Check if it's a Next.js optimized image and extract original
        nextjs_url = extract_nextjs_image_url(absolute_url)
        if nextjs_url:
            media_urls.add(nextjs_url)
            logger.debug("nextjs_image_extracted", original=nextjs_url)
        else:
            media_urls.add(absolute_url)

    # From <img> tags - check multiple attributes
    for img in soup.find_all('img'):
        # Standard src
        if img.get('src'):
            add_url(img.get('src'))

        # Lazy loading attributes
        for attr in ['data-src', 'data-lazy-src', 'data-original', 'data-lazy']:
            if img.get(attr):
                add_url(img.get(attr))

        # Srcset (multiple resolutions)
        for attr in ['srcset', 'data-srcset']:
            if img.get(attr):
                for url in extract_srcset_urls(img.get(attr), base_url):
                    add_url(url)

    # From <picture> and <source> elements
    for source in soup.find_all('source'):
        if source.get('src'):
            add_url(source.get('src'))

        for attr in ['srcset', 'data-srcset']:
            if source.get(attr):
                for url in extract_srcset_urls(source.get(attr), base_url):
                    add_url(url)

    # From <video> poster images
    for video in soup.find_all('video'):
        if video.get('poster'):
            add_url(video.get('poster'))

    # From CSS background-image (inline styles)
    for elem in soup.find_all(style=True):
        style = elem.get('style', '')
        if 'url(' in style:
            urls = re.findall(r'url\([\'"]?([^\'")\s]+)[\'"]?\)', style)
            for url in urls:
                add_url(url)

    # From <style> blocks
    for style_tag in soup.find_all('style'):
        if style_tag.string:
            urls = re.findall(r'url\([\'"]?([^\'")\s]+)[\'"]?\)', style_tag.string)
            for url in urls:
                add_url(url)

    # Convert set to list
    media_urls_list = list(media_urls)

    # Filter by supported formats
    supported_formats = settings.media_formats_list
    filtered_urls = []
    for url in media_urls_list:
        ext = get_file_extension(url)
        if ext and ext.lower() in supported_formats:
            filtered_urls.append(url)

    logger.info("media_urls_found", total=len(media_urls_list), filtered=len(filtered_urls))
    
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

        # Generate safe filename using hash (prevents path traversal)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        ext = get_file_extension(url) or guess_extension(content_type) or 'bin'

        # Sanitize extension to prevent path traversal via malicious extensions
        ext = ext.replace('/', '').replace('\\', '').replace('..', '')[:10]

        filename = f"media_{url_hash}.{ext}"

        # Ensure storage directory exists and get its real path
        os.makedirs(storage_dir, exist_ok=True)
        real_storage_dir = os.path.realpath(storage_dir)

        # Build filepath and verify it's within the storage directory
        filepath = os.path.join(real_storage_dir, filename)
        real_filepath = os.path.realpath(filepath)

        # Security check: ensure the final path is within the storage directory
        if not real_filepath.startswith(real_storage_dir + os.sep):
            logger.warning("media_path_traversal_blocked", url=url, filepath=filepath)
            return None

        # Save file
        with open(real_filepath, 'wb') as f:
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
