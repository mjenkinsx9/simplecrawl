"""
Content change monitoring functionality.
"""

import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Monitor, get_session
from app.core.scraper import scrape_url
from app.utils.logger import get_logger
from app.utils.url_validator import validate_webhook_url

logger = get_logger(__name__)


def check_content_change(monitor_id: str) -> Dict[str, Any]:
    """
    Check if content has changed for a monitor (synchronous wrapper for Celery).
    
    Args:
        monitor_id: Monitor identifier
    
    Returns:
        Check result
    """
    logger.info("monitor_check_started", monitor_id=monitor_id)
    
    # Run async check
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_check_content_async(monitor_id))
        logger.info("monitor_check_completed", monitor_id=monitor_id, changed=result.get("changed", False))
        return result
    finally:
        loop.close()


async def _check_content_async(monitor_id: str) -> Dict[str, Any]:
    """
    Async implementation of content change check.
    
    Args:
        monitor_id: Monitor identifier
    
    Returns:
        Check result with change status
    """
    db = get_session(settings.database_url)
    
    try:
        # Get monitor from database
        monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
        if not monitor:
            raise ValueError(f"Monitor {monitor_id} not found")
        
        # Scrape current content
        data = await scrape_url(monitor.url, formats=["markdown"])
        current_content = data.get("markdown", "")
        
        # Calculate content hash
        current_hash = hashlib.sha256(current_content.encode()).hexdigest()
        
        # Check if changed
        changed = False
        if monitor.content_hash and monitor.content_hash != current_hash:
            changed = True
            logger.info("content_changed", monitor_id=monitor_id, url=monitor.url)
            
            # Send webhook notification if configured
            if monitor.webhook_url:
                await send_webhook_notification(
                    monitor.webhook_url,
                    monitor.url,
                    monitor.content_hash,
                    current_hash
                )
        
        # Update monitor
        monitor.content_hash = current_hash
        monitor.last_checked = datetime.utcnow()
        monitor.next_check = datetime.utcnow() + timedelta(hours=monitor.interval_hours)
        db.commit()
        
        return {
            "monitor_id": monitor_id,
            "url": monitor.url,
            "changed": changed,
            "previous_hash": monitor.content_hash if changed else None,
            "current_hash": current_hash,
            "checked_at": datetime.utcnow().isoformat()
        }
    
    finally:
        db.close()


async def send_webhook_notification(
    webhook_url: str,
    page_url: str,
    old_hash: str,
    new_hash: str
) -> None:
    """
    Send webhook notification about content change.

    Args:
        webhook_url: Webhook URL
        page_url: Page URL that changed
        old_hash: Previous content hash
        new_hash: New content hash
    """
    # Validate webhook URL to prevent SSRF attacks
    is_valid, error = validate_webhook_url(webhook_url)
    if not is_valid:
        logger.warning("webhook_ssrf_blocked", webhook_url=webhook_url, reason=error)
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "event": "content_changed",
                "url": page_url,
                "old_hash": old_hash,
                "new_hash": new_hash,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            
            logger.info("webhook_sent", webhook_url=webhook_url, status=response.status_code)
    
    except Exception as e:
        logger.error("webhook_failed", webhook_url=webhook_url, error=str(e))
