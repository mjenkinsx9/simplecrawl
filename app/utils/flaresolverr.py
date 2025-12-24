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
