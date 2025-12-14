"""
Monitor endpoint for content change tracking.
"""

import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter

from app.models.requests import MonitorRequest
from app.models.responses import MonitorResponse
from app.config import settings
from app.db.models import Monitor, get_session
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/monitor", response_model=MonitorResponse)
async def create_monitor(request: MonitorRequest):
    """
    Create a content change monitor for a URL.
    
    This endpoint:
    1. Creates a monitor in the database
    2. Schedules periodic checks (via Celery beat - not implemented yet)
    3. Sends webhook notifications when content changes
    
    Example:
    ```json
    {
      "url": "https://example.com/pricing",
      "webhook_url": "https://myapp.com/webhook",
      "interval_hours": 24
    }
    ```
    
    The monitor will:
    - Check the URL every `interval_hours`
    - Calculate a SHA256 hash of the content
    - Compare with previous hash
    - Send webhook notification if changed
    
    Webhook payload:
    ```json
    {
      "event": "content_changed",
      "url": "https://example.com/pricing",
      "old_hash": "abc123...",
      "new_hash": "def456...",
      "timestamp": "2024-01-15T10:30:00Z"
    }
    ```
    """
    try:
        logger.info("monitor_create_request", url=str(request.url))
        
        # Generate monitor ID
        monitor_id = f"mon_{uuid.uuid4().hex[:16]}"
        
        # Create monitor in database
        db = get_session(settings.database_url)
        monitor = Monitor(
            id=monitor_id,
            url=str(request.url),
            webhook_url=str(request.webhook_url) if request.webhook_url else None,
            interval_hours=request.interval_hours,
            content_hash=None,
            last_checked=None,
            next_check=datetime.utcnow() + timedelta(hours=request.interval_hours),
            active=True,
            created_at=datetime.utcnow()
        )
        db.add(monitor)
        db.commit()
        
        next_check = monitor.next_check
        db.close()
        
        logger.info("monitor_created", monitor_id=monitor_id)
        
        return MonitorResponse(
            success=True,
            monitor_id=monitor_id,
            next_check=next_check
        )
    
    except Exception as e:
        logger.error("monitor_create_failed", url=str(request.url), error=str(e))
        return MonitorResponse(
            success=False,
            error={
                "code": "MONITOR_CREATE_FAILED",
                "message": str(e),
                "url": str(request.url)
            }
        )
