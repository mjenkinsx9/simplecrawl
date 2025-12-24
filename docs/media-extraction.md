# Media Extraction & Image Download System

This document explains how SimpleCrawl extracts and downloads images from web pages during scraping operations.

## Overview

The media extraction system is designed to comprehensively discover and download images from modern web pages. It handles various image embedding techniques including:

- Standard `<img>` tags
- Responsive images with `srcset`
- Lazy-loaded images (`data-src`, `data-lazy-src`)
- Next.js optimized images (`/_next/image?url=...`)
- `<picture>` and `<source>` elements
- Video poster images
- CSS background images (inline and `<style>` blocks)

## Architecture

### Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  scraper.py     │────▶│  media.py        │────▶│  File System    │
│  (triggers)     │     │  (extract/save)  │     │  (storage)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

1. **Trigger**: When `"media"` is in the requested formats, `scraper.py` calls `extract_media()`
2. **Discovery**: `extract_media()` parses HTML and finds all image URLs
3. **Filtering**: URLs are filtered by supported file extensions
4. **Download**: Each image is downloaded via async HTTP client
5. **Storage**: Images are saved with sanitized, unique filenames

### Entry Point

Located in `app/core/scraper.py` at line 180-184:

```python
# Extract media
if "media" in formats:
    import os
    job_media_dir = os.path.join(settings.media_storage_dir, "scrape")
    result["media"] = await extract_media(page, url, job_media_dir)
```

## Configuration

Settings in `app/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `media_storage_dir` | `/app/media` | Base directory for saved media |
| `media_formats` | `jpeg,jpg,png,gif,webp,avif,svg` | Supported image formats |
| `max_media_size_mb` | `50` | Maximum file size to download |

## Complete Source Code

### File: `app/utils/media.py`

```python
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
        for url in filtered_urls[:50]:  # Limit to 50 files per page
            try:
                media_info = await download_media(client, url, storage_dir)
                if media_info:
                    media_items.append(media_info)
            except Exception as e:
                logger.warning("media_download_failed", url=url, error=str(e))

    logger.info("media_extraction_completed", count=len(media_items))
    return media_items


def extract_original_filename(url: str) -> str:
    """
    Extract the original filename from a URL.

    Args:
        url: The media URL

    Returns:
        The original filename, sanitized for filesystem safety
    """
    parsed = urlparse(url)
    path = parsed.path

    # Get the last path component
    filename = os.path.basename(path)

    # URL decode (handles %20 -> space, etc.)
    filename = unquote(filename)

    # If no filename found, use a hash
    if not filename or filename == '/':
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"media_{url_hash}"

    return filename


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize a filename for safe filesystem storage.

    Args:
        filename: Original filename
        max_length: Maximum filename length

    Returns:
        Safe filename
    """
    # Remove path traversal attempts
    filename = filename.replace('/', '_').replace('\\', '_').replace('..', '_')

    # Remove or replace unsafe characters
    # Keep: alphanumeric, dash, underscore, dot, space
    safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ')
    filename = ''.join(c if c in safe_chars else '_' for c in filename)

    # Collapse multiple underscores/spaces
    filename = re.sub(r'[_\s]+', '_', filename)

    # Remove leading/trailing underscores and dots
    filename = filename.strip('_. ')

    # Ensure we have something
    if not filename:
        return f"media_{hashlib.md5(str(id(filename)).encode()).hexdigest()[:8]}"

    # Truncate if too long (preserve extension)
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        max_name_len = max_length - len(ext) - 1
        if max_name_len > 0:
            filename = name[:max_name_len] + ext
        else:
            filename = filename[:max_length]

    return filename


def get_unique_filepath(storage_dir: str, filename: str) -> str:
    """
    Get a unique filepath, adding a counter suffix if file exists.

    Args:
        storage_dir: Directory to save to
        filename: Desired filename

    Returns:
        Unique filepath
    """
    filepath = os.path.join(storage_dir, filename)

    if not os.path.exists(filepath):
        return filepath

    # File exists, add counter suffix
    name, ext = os.path.splitext(filename)
    counter = 1

    while os.path.exists(filepath):
        new_filename = f"{name}_{counter}{ext}"
        filepath = os.path.join(storage_dir, new_filename)
        counter += 1

        # Safety limit
        if counter > 1000:
            # Fall back to hash
            url_hash = hashlib.md5(f"{filename}{counter}".encode()).hexdigest()[:8]
            filepath = os.path.join(storage_dir, f"{name}_{url_hash}{ext}")
            break

    return filepath


async def download_media(client: httpx.AsyncClient, url: str, storage_dir: str) -> Optional[Dict[str, Any]]:
    """
    Download a media file, preserving the original filename.

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

        # Extract and sanitize original filename from URL
        original_filename = extract_original_filename(url)
        filename = sanitize_filename(original_filename)

        # Ensure proper extension
        ext = get_file_extension(url) or guess_extension(content_type)
        if ext:
            # Sanitize extension
            ext = ext.replace('/', '').replace('\\', '').replace('..', '')[:10]
            # Add extension if missing
            if not filename.lower().endswith(f'.{ext.lower()}'):
                filename = f"{filename}.{ext}"

        # Ensure storage directory exists and get its real path
        os.makedirs(storage_dir, exist_ok=True)
        real_storage_dir = os.path.realpath(storage_dir)

        # Get unique filepath (handles duplicates)
        filepath = get_unique_filepath(real_storage_dir, filename)
        real_filepath = os.path.realpath(filepath)

        # Security check: ensure the final path is within the storage directory
        if not real_filepath.startswith(real_storage_dir + os.sep):
            logger.warning("media_path_traversal_blocked", url=url, filepath=filepath)
            return None

        # Save file
        with open(real_filepath, 'wb') as f:
            f.write(response.content)

        # Get the actual filename used (might have counter suffix)
        final_filename = os.path.basename(real_filepath)

        return {
            "url": url,
            "filename": final_filename,
            "original_name": original_filename,
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
```

## Function Reference

### Core Functions

| Function | Purpose |
|----------|---------|
| `extract_media()` | Main entry point - discovers and downloads all images from a page |
| `download_media()` | Downloads a single image file with proper error handling |
| `extract_nextjs_image_url()` | Unwraps Next.js optimized image URLs to get originals |
| `extract_srcset_urls()` | Parses responsive image `srcset` attributes |

### Helper Functions

| Function | Purpose |
|----------|---------|
| `extract_original_filename()` | Gets filename from URL path |
| `sanitize_filename()` | Makes filenames filesystem-safe |
| `get_unique_filepath()` | Prevents filename collisions with counter suffix |
| `get_file_extension()` | Extracts extension from URL |
| `guess_extension()` | Maps MIME type to file extension |

## Image Discovery Sources

The system looks for images in these locations:

### 1. Standard `<img>` Tags
```html
<img src="/images/photo.jpg">
```

### 2. Lazy-Loaded Images
```html
<img data-src="/images/photo.jpg" src="placeholder.gif">
<img data-lazy-src="/images/photo.jpg">
<img data-original="/images/photo.jpg">
```

### 3. Responsive Images (srcset)
```html
<img srcset="/small.jpg 100w, /medium.jpg 500w, /large.jpg 1000w">
<img data-srcset="/small.jpg 1x, /large.jpg 2x">
```

### 4. Picture Elements
```html
<picture>
  <source srcset="/photo.webp" type="image/webp">
  <source srcset="/photo.jpg" type="image/jpeg">
  <img src="/photo.jpg">
</picture>
```

### 5. Next.js Optimized Images
```html
<img src="/_next/image?url=%2Fimages%2Fphoto.jpg&w=1200&q=75">
```
The system extracts the original `/images/photo.jpg` URL.

### 6. Video Poster Images
```html
<video poster="/thumbnail.jpg">...</video>
```

### 7. CSS Background Images
```html
<div style="background-image: url('/images/bg.jpg')">
```

```html
<style>
  .hero { background-image: url('/images/hero.jpg'); }
</style>
```

## Security Features

1. **Path Traversal Prevention**: Filenames are sanitized to remove `..`, `/`, and `\`
2. **Directory Containment**: Final paths are validated to be within the storage directory
3. **Size Limits**: Files larger than `max_media_size_mb` are rejected
4. **Safe Characters Only**: Filenames are stripped of unsafe characters

## Limits

| Limit | Value | Location |
|-------|-------|----------|
| Images per page | 50 | `extract_media()` line 194 |
| Max file size | 50 MB | `settings.max_media_size_mb` |
| Filename length | 200 chars | `sanitize_filename()` |
| Duplicate counter | 1000 | `get_unique_filepath()` |

## Output Format

Each downloaded image returns metadata:

```python
{
    "url": "https://example.com/images/photo.jpg",
    "filename": "photo.jpg",           # Final saved filename
    "original_name": "photo.jpg",      # Original from URL
    "type": "image/jpeg",              # MIME type
    "size": 123456                     # Bytes
}
```

## Storage Location

Images are saved to:
- **Docker**: `/app/media/scrape/` (mounted to `./media/scrape/` on host)
- **Configurable**: Via `MEDIA_STORAGE_DIR` environment variable

All images from all pages go to the same directory. Duplicate filenames get counter suffixes (`photo_1.jpg`, `photo_2.jpg`, etc.).
