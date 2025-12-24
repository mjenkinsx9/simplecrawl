# Cloudflare Bypass with FlareSolverr

This document explains how SimpleCrawl bypasses Cloudflare protection using FlareSolverr.

## Overview

Cloudflare protects websites with JavaScript challenges that block traditional web scrapers. SimpleCrawl integrates with [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr), a proxy server that uses a real headless browser to solve these challenges automatically.

## How It Works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  SimpleCrawl    │────▶│  Target Website  │────▶│  Cloudflare?    │
│  (Playwright)   │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                   YES    │    NO
                                                 ┌────────┴────────┐
                                                 ▼                 ▼
                                         ┌───────────────┐   ┌─────────────┐
                                         │  FlareSolverr │   │  Continue   │
                                         │  (Real Chrome)│   │  normally   │
                                         └───────┬───────┘   └─────────────┘
                                                 │
                                                 ▼
                                         ┌───────────────┐
                                         │  Return HTML  │
                                         │  + Cookies    │
                                         └───────────────┘
```

### Detection Flow

1. **Initial Request**: SimpleCrawl fetches the page with Playwright
2. **Challenge Detection**: The HTML is scanned for Cloudflare indicators
3. **Automatic Fallback**: If Cloudflare is detected and FlareSolverr is configured, the request is retried through FlareSolverr
4. **Challenge Solving**: FlareSolverr uses a real Chrome browser to solve the JavaScript challenge
5. **Response**: The solved HTML and bypass cookies are returned

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLARESOLVERR_URL` | `None` | FlareSolverr API endpoint (e.g., `http://flaresolverr:8191/v1`) |
| `FLARESOLVERR_TIMEOUT` | `60000` | Request timeout in milliseconds |
| `FLARESOLVERR_AUTO_FALLBACK` | `true` | Automatically retry with FlareSolverr when Cloudflare is detected |

### Docker Compose Setup

FlareSolverr runs as a separate container in the Docker stack:

```yaml
# FlareSolverr for Cloudflare bypass
flaresolverr:
  image: ghcr.io/flaresolverr/flaresolverr:latest
  container_name: simplecrawl-flaresolverr
  environment:
    - LOG_LEVEL=info
    - LOG_HTML=false
    - TZ=UTC
    - CAPTCHA_SOLVER=none
    - BROWSER_TIMEOUT=60000
  ports:
    - "8191:8191"
  restart: unless-stopped
```

The API and worker services are configured to use it:

```yaml
api:
  environment:
    - FLARESOLVERR_URL=http://flaresolverr:8191/v1
  depends_on:
    - flaresolverr

worker:
  environment:
    - FLARESOLVERR_URL=http://flaresolverr:8191/v1
  depends_on:
    - flaresolverr
```

## Cloudflare Detection

SimpleCrawl detects Cloudflare challenges by scanning the page content for these indicators:

```python
CLOUDFLARE_INDICATORS = [
    "Enable JavaScript and cookies to continue",
    "Just a moment...",
    "Checking your browser",
    "Verifying you are human",
    "needs to review the security of your connection",
    "Please enable cookies",
    "Please turn JavaScript on",
    "Attention Required! | Cloudflare",
    "cf-browser-verification",
    "cf_clearance",
    "_cf_bm",
]
```

The detection function:

```python
def is_cloudflare_challenge(content: str) -> bool:
    """
    Check if the content appears to be a Cloudflare challenge page.

    Args:
        content: HTML or text content from a page

    Returns:
        True if Cloudflare protection is detected
    """
    content_lower = content.lower()
    for indicator in CLOUDFLARE_INDICATORS:
        if indicator.lower() in content_lower:
            return True
    return False
```

## Integration in Scraper

The bypass logic is integrated in `app/core/scraper.py`:

```python
# Get HTML content from Playwright
html_content = await page.content()

# Track if we used FlareSolverr (affects how we extract links/metadata)
used_flaresolverr = False

# Check for Cloudflare challenge and retry with FlareSolverr if available
if is_cloudflare_challenge(html_content):
    logger.info("cloudflare_detected", url=url)

    if settings.flaresolverr_auto_fallback and flaresolverr_client.is_available:
        logger.info("flaresolverr_fallback", url=url)
        try:
            fs_result = await flaresolverr_client.get(url)
            if fs_result.get("status") == "ok":
                html_content = fs_result["solution"]["response"]
                used_flaresolverr = True
                logger.info("flaresolverr_bypass_success", url=url)
            else:
                logger.warning(
                    "flaresolverr_bypass_failed",
                    url=url,
                    message=fs_result.get("message"),
                )
        except Exception as e:
            logger.error("flaresolverr_error", url=url, error=str(e))
    else:
        logger.warning(
            "cloudflare_no_fallback",
            url=url,
            message="FlareSolverr not available for bypass",
        )
```

When FlareSolverr is used, link and metadata extraction falls back to HTML parsing (since we only have the HTML string, not a live Playwright page):

```python
# Extract links (use HTML parsing if FlareSolverr was used)
if "links" in formats:
    if used_flaresolverr:
        result["links"] = extract_links_from_html(html_content, url)
    else:
        result["links"] = await extract_links(page, url)

# Extract metadata (use HTML parsing if FlareSolverr was used)
if "metadata" in formats:
    if used_flaresolverr:
        result["metadata"] = extract_metadata_from_html(html_content, url)
    else:
        result["metadata"] = await extract_metadata(page, url)
```

## Complete FlareSolverr Client

### File: `app/utils/flaresolverr.py`

```python
"""
FlareSolverr client for bypassing Cloudflare protection.

FlareSolverr is a proxy server that uses a headless browser to solve
Cloudflare challenges. This module provides a client to interact with it.

Usage:
    client = FlareSolverClient()
    result = await client.get("https://cloudflare-protected-site.com")
    html = result["solution"]["response"]
    cookies = result["solution"]["cookies"]
"""

from typing import Dict, Any, Optional, List
import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Patterns that indicate Cloudflare protection
CLOUDFLARE_INDICATORS = [
    "Enable JavaScript and cookies to continue",
    "Just a moment...",
    "Checking your browser",
    "Verifying you are human",
    "needs to review the security of your connection",
    "Please enable cookies",
    "Please turn JavaScript on",
    "Attention Required! | Cloudflare",
    "cf-browser-verification",
    "cf_clearance",
    "_cf_bm",
]


def is_cloudflare_challenge(content: str) -> bool:
    """
    Check if the content appears to be a Cloudflare challenge page.

    Args:
        content: HTML or text content from a page

    Returns:
        True if Cloudflare protection is detected
    """
    content_lower = content.lower()
    for indicator in CLOUDFLARE_INDICATORS:
        if indicator.lower() in content_lower:
            return True
    return False


class FlareSolverClient:
    """
    Client for interacting with FlareSolverr API.

    FlareSolverr solves Cloudflare challenges using a real browser,
    returning the page content and cookies that can be used for
    subsequent requests.
    """

    def __init__(self, url: Optional[str] = None, timeout: Optional[int] = None):
        """
        Initialize the FlareSolverr client.

        Args:
            url: FlareSolverr API URL (defaults to settings.flaresolverr_url)
            timeout: Request timeout in milliseconds (defaults to settings.flaresolverr_timeout)
        """
        self.url = url or settings.flaresolverr_url
        self.timeout = timeout or settings.flaresolverr_timeout
        self._session_id: Optional[str] = None

    @property
    def is_available(self) -> bool:
        """Check if FlareSolverr is configured."""
        return bool(self.url)

    async def get(
        self,
        url: str,
        cookies: Optional[List[Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
        session: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a URL through FlareSolverr.

        Args:
            url: The URL to fetch
            cookies: Optional cookies to send with the request
            headers: Optional headers to send
            session: Optional session ID for persistent sessions

        Returns:
            FlareSolverr response containing solution with HTML and cookies

        Raises:
            Exception: If FlareSolverr is not configured or request fails
        """
        if not self.is_available:
            raise RuntimeError("FlareSolverr is not configured. Set FLARESOLVERR_URL.")

        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": self.timeout,
        }

        if cookies:
            payload["cookies"] = cookies
        if headers:
            payload["headers"] = headers
        if session:
            payload["session"] = session

        logger.info("flaresolverr_request", url=url)

        async with httpx.AsyncClient(timeout=self.timeout / 1000 + 10) as client:
            response = await client.post(
                self.url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

        if result.get("status") == "ok":
            logger.info(
                "flaresolverr_success",
                url=url,
                status_code=result.get("solution", {}).get("status"),
            )
        else:
            logger.warning(
                "flaresolverr_failed",
                url=url,
                message=result.get("message"),
            )

        return result

    async def create_session(self) -> str:
        """
        Create a persistent FlareSolverr session.

        Sessions keep the browser open between requests, which can be
        faster for multiple requests to the same domain.

        Returns:
            Session ID

        Raises:
            Exception: If session creation fails
        """
        if not self.is_available:
            raise RuntimeError("FlareSolverr is not configured.")

        payload = {"cmd": "sessions.create"}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

        if result.get("status") == "ok":
            self._session_id = result.get("session")
            logger.info("flaresolverr_session_created", session_id=self._session_id)
            return self._session_id
        else:
            raise RuntimeError(f"Failed to create session: {result.get('message')}")

    async def destroy_session(self, session_id: Optional[str] = None) -> bool:
        """
        Destroy a FlareSolverr session.

        Args:
            session_id: Session ID to destroy (uses stored ID if not provided)

        Returns:
            True if session was destroyed
        """
        if not self.is_available:
            return False

        session = session_id or self._session_id
        if not session:
            return False

        payload = {"cmd": "sessions.destroy", "session": session}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()

            if result.get("status") == "ok":
                logger.info("flaresolverr_session_destroyed", session_id=session)
                if session == self._session_id:
                    self._session_id = None
                return True
        except Exception as e:
            logger.warning("flaresolverr_session_destroy_failed", error=str(e))

        return False


def cookies_to_dict(flaresolverr_cookies: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Convert FlareSolverr cookies to a simple dict for use with requests/httpx.

    Args:
        flaresolverr_cookies: Cookies from FlareSolverr response

    Returns:
        Dictionary mapping cookie names to values
    """
    return {cookie["name"]: cookie["value"] for cookie in flaresolverr_cookies}


def cookies_to_header(flaresolverr_cookies: List[Dict[str, Any]]) -> str:
    """
    Convert FlareSolverr cookies to a Cookie header string.

    Args:
        flaresolverr_cookies: Cookies from FlareSolverr response

    Returns:
        Cookie header string (e.g., "name1=value1; name2=value2")
    """
    return "; ".join(
        f"{cookie['name']}={cookie['value']}" for cookie in flaresolverr_cookies
    )


# Global client instance
flaresolverr_client = FlareSolverClient()
```

## FlareSolverr API

FlareSolverr exposes a simple JSON API:

### GET Request

```bash
curl -X POST http://localhost:8191/v1 \
  -H "Content-Type: application/json" \
  -d '{
    "cmd": "request.get",
    "url": "https://cloudflare-protected-site.com",
    "maxTimeout": 60000
  }'
```

### Response

```json
{
  "status": "ok",
  "message": "Challenge solved!",
  "solution": {
    "url": "https://cloudflare-protected-site.com",
    "status": 200,
    "headers": { ... },
    "response": "<html>...</html>",
    "cookies": [
      {
        "name": "cf_clearance",
        "value": "abc123...",
        "domain": ".cloudflare-protected-site.com",
        "path": "/",
        "expires": 1234567890,
        "httpOnly": true,
        "secure": true
      }
    ],
    "userAgent": "Mozilla/5.0 ..."
  },
  "startTimestamp": 1234567890,
  "endTimestamp": 1234567891
}
```

### Session Management

For faster multi-page scraping, use sessions:

```python
# Create session (keeps browser open)
client = FlareSolverClient()
session_id = await client.create_session()

# Use session for multiple requests
result1 = await client.get("https://site.com/page1", session=session_id)
result2 = await client.get("https://site.com/page2", session=session_id)

# Destroy session when done
await client.destroy_session(session_id)
```

## Performance Considerations

| Factor | Impact |
|--------|--------|
| **Challenge solving time** | 5-60 seconds per page (depends on challenge complexity) |
| **Session reuse** | Faster for same-domain requests (browser stays open) |
| **Memory usage** | FlareSolverr uses ~500MB+ (runs real Chrome) |
| **Concurrency** | Limited by FlareSolverr's browser pool |

### Why It's Slow

Each Cloudflare challenge requires:
1. Starting/reusing a Chrome instance
2. Navigating to the page
3. Waiting for JavaScript challenge to execute
4. Waiting for verification to complete
5. Extracting HTML and cookies

This typically takes 30-60 seconds per page on Cloudflare-protected sites.

## Limitations

1. **CAPTCHAs**: FlareSolverr cannot solve CAPTCHAs by default (requires paid solver integration)
2. **Rate Limiting**: Too many requests may trigger additional Cloudflare blocks
3. **Resource Heavy**: Each FlareSolverr instance runs a full Chrome browser
4. **Not 100% Reliable**: Some advanced Cloudflare protections may still block

## Troubleshooting

### FlareSolverr Not Connecting

```bash
# Check if FlareSolverr is running
docker logs simplecrawl-flaresolverr

# Test directly
curl http://localhost:8191/v1 \
  -H "Content-Type: application/json" \
  -d '{"cmd": "request.get", "url": "https://example.com"}'
```

### Challenge Not Solving

- Increase `FLARESOLVERR_TIMEOUT` (default 60000ms)
- Check if site uses CAPTCHA (requires solver integration)
- Try with a session for cookie persistence

### High Memory Usage

FlareSolverr keeps Chrome instances running. Reduce memory by:
- Limiting concurrent requests
- Using sessions and destroying them when done
- Restarting FlareSolverr periodically

## Logs

Look for these log entries to track Cloudflare bypass:

```
cloudflare_detected          url=https://example.com
flaresolverr_fallback        url=https://example.com
flaresolverr_request         url=https://example.com
flaresolverr_success         url=https://example.com status_code=200
flaresolverr_bypass_success  url=https://example.com
```

Or on failure:

```
cloudflare_detected          url=https://example.com
flaresolverr_fallback        url=https://example.com
flaresolverr_failed          url=https://example.com message="Challenge not solved"
```
