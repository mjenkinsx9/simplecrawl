"""
Playwright browser pool management for efficient browser reuse.
"""

import asyncio
from typing import Optional, Dict
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from app.config import settings
from app.utils.logger import get_logger
from app.core.proxy import get_proxy_pool, ProxyPool

logger = get_logger(__name__)


class BrowserPool:
    """
    Manages a pool of Playwright browser contexts for efficient reuse.
    Supports proxy rotation when configured.
    """

    def __init__(self, pool_size: int = 5, headless: bool = True, user_agent: Optional[str] = None):
        """
        Initialize the browser pool.

        Args:
            pool_size: Maximum number of browser contexts to maintain
            headless: Whether to run browsers in headless mode
            user_agent: Custom user agent string
        """
        self.pool_size = pool_size
        self.headless = headless
        self.user_agent = user_agent or settings.user_agent

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: list[BrowserContext] = []
        self._lock = asyncio.Lock()
        self._initialized = False
        self._proxy_pool: Optional[ProxyPool] = None
    
    async def initialize(self) -> None:
        """Initialize the browser pool."""
        if self._initialized:
            return

        logger.info("browser_pool_initializing", pool_size=self.pool_size)

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )

        # Initialize proxy pool if configured
        self._proxy_pool = get_proxy_pool()
        if self._proxy_pool and self._proxy_pool.has_proxies:
            logger.info("proxy_pool_attached", proxy_count=self._proxy_pool.proxy_count)

        self._initialized = True
        logger.info("browser_pool_initialized")
    
    async def close(self) -> None:
        """Close all browser contexts and the browser."""
        logger.info("browser_pool_closing")
        
        # Close all contexts
        for context in self._contexts:
            try:
                await context.close()
            except Exception as e:
                logger.warning("context_close_failed", error=str(e))
        
        self._contexts.clear()
        
        # Close browser
        if self._browser:
            await self._browser.close()
        
        # Stop playwright
        if self._playwright:
            await self._playwright.stop()
        
        self._initialized = False
        logger.info("browser_pool_closed")
    
    @asynccontextmanager
    async def get_context(self, use_proxy: bool = True, extra_headers: Optional[Dict[str, str]] = None):
        """
        Get a browser context from the pool.

        Args:
            use_proxy: Whether to use proxy for this context (if available)
            extra_headers: Custom HTTP headers (e.g., Authorization, Cookie)

        Yields:
            BrowserContext: A Playwright browser context
        """
        if not self._initialized:
            await self.initialize()

        proxy = None
        proxy_server = None

        # Get proxy if enabled and requested
        if use_proxy and self._proxy_pool and self._proxy_pool.has_proxies:
            proxy = await self._proxy_pool.get_proxy()
            if proxy:
                proxy_server = proxy.get("server")
                logger.debug("using_proxy", server=proxy_server)

        # When using proxies or custom headers, always create a new context (can't reuse)
        if proxy or extra_headers:
            context_opts = {
                "user_agent": self.user_agent,
                "viewport": {'width': 1920, 'height': 1080},
            }
            if proxy:
                context_opts["proxy"] = proxy
            if extra_headers:
                context_opts["extra_http_headers"] = extra_headers
                logger.debug("using_custom_headers", header_count=len(extra_headers))

            context = await self._browser.new_context(**context_opts)
            logger.debug("context_created_with_options", proxy=bool(proxy), headers=bool(extra_headers))
        else:
            # No proxy or headers - use pooled contexts
            async with self._lock:
                if self._contexts:
                    context = self._contexts.pop()
                    logger.debug("context_reused", pool_size=len(self._contexts))
                else:
                    context = await self._browser.new_context(
                        user_agent=self.user_agent,
                        viewport={'width': 1920, 'height': 1080}
                    )
                    logger.debug("context_created", pool_size=len(self._contexts))

        try:
            yield context
        except Exception as e:
            # Report proxy failure if we were using one
            if proxy_server and self._proxy_pool:
                await self._proxy_pool.report_failure(proxy_server)
            raise
        else:
            # Report proxy success if we were using one
            if proxy_server and self._proxy_pool:
                await self._proxy_pool.report_success(proxy_server)
        finally:
            if proxy or extra_headers:
                # Always close contexts with proxy or custom headers (can't reuse)
                await context.close()
                logger.debug("custom_context_closed", proxy=bool(proxy), headers=bool(extra_headers))
            else:
                # Return standard context to pool
                async with self._lock:
                    if len(self._contexts) < self.pool_size:
                        try:
                            await context.clear_cookies()
                        except Exception:
                            pass
                        self._contexts.append(context)
                        logger.debug("context_returned", pool_size=len(self._contexts))
                    else:
                        await context.close()
                        logger.debug("context_closed_pool_full", pool_size=len(self._contexts))
    
    @asynccontextmanager
    async def get_page(self, extra_headers: Optional[Dict[str, str]] = None):
        """
        Get a new page from a browser context.

        Args:
            extra_headers: Custom HTTP headers for this page

        Yields:
            Page: A Playwright page
        """
        async with self.get_context(extra_headers=extra_headers) as context:
            page = await context.new_page()
            try:
                yield page
            finally:
                await page.close()


# Global browser pool instance
browser_pool = BrowserPool(
    pool_size=settings.browser_pool_size,
    headless=settings.headless,
    user_agent=settings.user_agent
)
