"""
Proxy pool management for rotating proxies during scraping.
"""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from urllib.parse import urlparse

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProxyInfo:
    """Information about a proxy and its health status."""
    url: str
    server: str
    username: Optional[str] = None
    password: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None

    @property
    def is_healthy(self) -> bool:
        """Check if proxy is healthy and not in cooldown."""
        if self.cooldown_until and datetime.utcnow() < self.cooldown_until:
            return False
        return True

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.failure_count / total

    def to_playwright_proxy(self) -> Dict[str, str]:
        """Convert to Playwright proxy format."""
        proxy_dict = {"server": self.server}
        if self.username:
            proxy_dict["username"] = self.username
        if self.password:
            proxy_dict["password"] = self.password
        return proxy_dict


def parse_proxy_url(url: str) -> ProxyInfo:
    """
    Parse a proxy URL into ProxyInfo.

    Supported formats:
    - http://proxy.com:8080
    - http://user:pass@proxy.com:8080
    - socks5://proxy.com:1080
    """
    parsed = urlparse(url)

    # Extract auth if present
    username = parsed.username
    password = parsed.password

    # Build server URL without auth
    if parsed.port:
        server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    else:
        server = f"{parsed.scheme}://{parsed.hostname}"

    return ProxyInfo(
        url=url,
        server=server,
        username=username,
        password=password
    )


class ProxyPool:
    """
    Manages a pool of proxies with rotation and health tracking.

    Features:
    - Round-robin or random rotation
    - Health tracking per proxy
    - Automatic cooldown for failed proxies
    - Support for file-based or single proxy configuration
    """

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        proxy_file: Optional[str] = None,
        rotation_strategy: str = "round_robin",
        max_failures: int = 3,
        cooldown_seconds: int = 300
    ):
        """
        Initialize the proxy pool.

        Args:
            proxy_url: Single proxy URL
            proxy_file: Path to file containing proxy URLs (one per line)
            rotation_strategy: "round_robin" or "random"
            max_failures: Number of failures before cooldown
            cooldown_seconds: Cooldown duration after max failures
        """
        self.rotation_strategy = rotation_strategy
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds

        self._proxies: List[ProxyInfo] = []
        self._current_index = 0
        self._lock = asyncio.Lock()

        # Load proxies
        if proxy_file:
            self._load_from_file(proxy_file)
        elif proxy_url:
            self._proxies.append(parse_proxy_url(proxy_url))

        if self._proxies:
            logger.info("proxy_pool_initialized", count=len(self._proxies))
        else:
            logger.info("proxy_pool_empty", message="No proxies configured")

    def _load_from_file(self, filepath: str) -> None:
        """Load proxies from a file."""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            proxy = parse_proxy_url(line)
                            self._proxies.append(proxy)
                        except Exception as e:
                            logger.warning("proxy_parse_failed", line=line, error=str(e))

            logger.info("proxies_loaded_from_file", filepath=filepath, count=len(self._proxies))
        except FileNotFoundError:
            logger.error("proxy_file_not_found", filepath=filepath)
        except Exception as e:
            logger.error("proxy_file_load_failed", filepath=filepath, error=str(e))

    @property
    def has_proxies(self) -> bool:
        """Check if any proxies are configured."""
        return len(self._proxies) > 0

    @property
    def proxy_count(self) -> int:
        """Get total number of proxies."""
        return len(self._proxies)

    @property
    def healthy_count(self) -> int:
        """Get number of healthy proxies."""
        return sum(1 for p in self._proxies if p.is_healthy)

    async def get_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get the next proxy from the pool.

        Returns:
            Playwright-formatted proxy dict, or None if no proxies available
        """
        if not self._proxies:
            return None

        async with self._lock:
            # Find a healthy proxy
            attempts = 0
            max_attempts = len(self._proxies)

            while attempts < max_attempts:
                if self.rotation_strategy == "random":
                    proxy = random.choice(self._proxies)
                else:  # round_robin
                    proxy = self._proxies[self._current_index]
                    self._current_index = (self._current_index + 1) % len(self._proxies)

                if proxy.is_healthy:
                    proxy.last_used = datetime.utcnow()
                    logger.debug("proxy_selected", server=proxy.server)
                    return proxy.to_playwright_proxy()

                attempts += 1

            # All proxies in cooldown, return the one with earliest cooldown end
            earliest = min(self._proxies, key=lambda p: p.cooldown_until or datetime.min)
            logger.warning("all_proxies_in_cooldown", using=earliest.server)
            return earliest.to_playwright_proxy()

    async def report_success(self, proxy_server: str) -> None:
        """Report successful use of a proxy."""
        async with self._lock:
            for proxy in self._proxies:
                if proxy.server == proxy_server:
                    proxy.success_count += 1
                    logger.debug("proxy_success", server=proxy_server, total_success=proxy.success_count)
                    return

    async def report_failure(self, proxy_server: str) -> None:
        """Report failed use of a proxy."""
        async with self._lock:
            for proxy in self._proxies:
                if proxy.server == proxy_server:
                    proxy.failure_count += 1
                    logger.warning("proxy_failure", server=proxy_server, total_failures=proxy.failure_count)

                    # Check if we need to put proxy in cooldown
                    if proxy.failure_count >= self.max_failures:
                        proxy.cooldown_until = datetime.utcnow() + timedelta(seconds=self.cooldown_seconds)
                        logger.warning(
                            "proxy_cooldown_started",
                            server=proxy_server,
                            cooldown_seconds=self.cooldown_seconds
                        )
                    return

    def get_stats(self) -> Dict:
        """Get proxy pool statistics."""
        return {
            "total": len(self._proxies),
            "healthy": self.healthy_count,
            "proxies": [
                {
                    "server": p.server,
                    "success_count": p.success_count,
                    "failure_count": p.failure_count,
                    "failure_rate": round(p.failure_rate, 2),
                    "is_healthy": p.is_healthy,
                    "in_cooldown": p.cooldown_until is not None and datetime.utcnow() < p.cooldown_until
                }
                for p in self._proxies
            ]
        }


# Global proxy pool instance (initialized lazily)
_proxy_pool: Optional[ProxyPool] = None


def get_proxy_pool() -> Optional[ProxyPool]:
    """Get or create the global proxy pool."""
    global _proxy_pool

    if _proxy_pool is None:
        from app.config import settings

        if settings.proxy_rotation_enabled and (settings.proxy_url or settings.proxy_list_file):
            _proxy_pool = ProxyPool(
                proxy_url=settings.proxy_url,
                proxy_file=settings.proxy_list_file,
                rotation_strategy=settings.proxy_rotation_strategy,
                max_failures=settings.proxy_max_failures,
                cooldown_seconds=settings.proxy_cooldown_seconds
            )
        else:
            logger.debug("proxy_pool_disabled", message="Proxy rotation not enabled or no proxies configured")

    return _proxy_pool
