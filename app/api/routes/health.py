"""
Health check endpoint for monitoring service status.
"""

import time
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
import redis

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Track startup time
startup_time = time.time()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    
    Returns:
        Service health status including version, uptime, and service statuses
    """
    uptime = int(time.time() - startup_time)
    
    # Check Redis connection
    redis_status = "disconnected"
    try:
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        redis_status = "connected"
    except Exception as e:
        logger.warning("redis_health_check_failed", error=str(e))
    
    # Check Celery (via Redis)
    celery_status = "unknown"
    if redis_status == "connected":
        try:
            from app.workers.tasks import celery_app
            inspect = celery_app.control.inspect(timeout=2)
            active = inspect.active()
            celery_status = "running" if active is not None else "not_running"
        except Exception as e:
            logger.warning("celery_health_check_failed", error=str(e))
            celery_status = "error"
    
    # Check Playwright (just verify it's importable)
    playwright_status = "ready"
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        logger.warning("playwright_health_check_failed", error=str(e))
        playwright_status = "error"
    
    overall_status = "ok" if redis_status == "connected" else "degraded"
    
    return {
        "status": overall_status,
        "version": "1.0.0",
        "uptime": uptime,
        "services": {
            "redis": redis_status,
            "celery": celery_status,
            "playwright": playwright_status
        }
    }


@router.get("/")
async def root() -> Dict[str, str]:
    """
    Root endpoint with API information.
    
    Returns:
        API information
    """
    return {
        "name": "SimpleCrawl API",
        "version": "1.0.0",
        "description": "Self-hosted web scraping and data extraction API",
        "docs": "/docs",
        "health": "/v1/health"
    }
