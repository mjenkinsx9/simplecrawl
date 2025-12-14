"""
Crawl endpoints for multi-page crawling.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.models.requests import CrawlRequest
from app.models.responses import JobResponse, JobStatusResponse
from app.config import settings
from app.db.models import CrawlJob, get_session
from app.workers.tasks import crawl_task
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/crawl", response_model=JobResponse)
async def start_crawl(request: CrawlRequest):
    """
    Start an async crawl job for a website.
    
    This endpoint:
    1. Creates a crawl job in the database
    2. Submits the job to Celery for async processing
    3. Returns a job ID for status checking
    
    Example:
    ```json
    {
      "url": "https://example.com",
      "limit": 100,
      "depth": 3,
      "scrape_options": {
        "formats": ["markdown", "metadata"],
        "exclude_tags": ["nav", "footer"]
      },
      "include_patterns": ["*/docs/*"],
      "exclude_patterns": ["*/admin/*"]
    }
    ```
    
    Returns a job ID that can be used with `GET /v1/crawl/{job_id}` to check status.
    """
    try:
        logger.info("crawl_request", url=str(request.url), limit=request.limit, depth=request.depth)
        
        # Generate job ID
        job_id = f"crawl_{uuid.uuid4().hex[:16]}"
        
        # Create job in database
        db = get_session(settings.database_url)
        job = CrawlJob(
            id=job_id,
            url=str(request.url),
            status="pending",
            total=0,
            completed=0,
            failed=0,
            config={
                "limit": request.limit,
                "depth": request.depth,
                "scrape_options": request.scrape_options or {},
                "include_patterns": request.include_patterns or [],
                "exclude_patterns": request.exclude_patterns or []
            },
            created_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.close()
        
        # Submit to Celery
        crawl_task.delay(
            job_id,
            str(request.url),
            {
                "limit": request.limit,
                "depth": request.depth,
                "scrape_options": request.scrape_options or {},
                "include_patterns": request.include_patterns or [],
                "exclude_patterns": request.exclude_patterns or []
            }
        )
        
        logger.info("crawl_job_created", job_id=job_id)
        
        return JobResponse(
            success=True,
            id=job_id,
            status_url=f"/v1/crawl/{job_id}"
        )
    
    except Exception as e:
        logger.error("crawl_request_failed", url=str(request.url), error=str(e))
        return JobResponse(
            success=False,
            error={
                "code": "CRAWL_START_FAILED",
                "message": str(e),
                "url": str(request.url)
            }
        )


@router.get("/crawl/{job_id}", response_model=JobStatusResponse)
async def get_crawl_status(job_id: str):
    """
    Get the status of a crawl job.
    
    Returns:
    - `status`: Job status (pending, running, completed, failed)
    - `total`: Total number of pages discovered
    - `completed`: Number of pages crawled
    - `failed`: Number of failed pages
    - `data`: Crawled page data (when completed)
    - `created_at`: Job creation time
    - `completed_at`: Job completion time (when completed)
    
    Example:
    ```
    GET /v1/crawl/crawl_abc123def456
    ```
    """
    try:
        db = get_session(settings.database_url)
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        db.close()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Extract results data
        data = None
        if job.results and "data" in job.results:
            data = job.results["data"]
        
        return JobStatusResponse(
            status=job.status,
            total=job.total,
            completed=job.completed,
            failed=job.failed,
            data=data,
            created_at=job.created_at,
            completed_at=job.completed_at,
            error=job.error
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_crawl_status_failed", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
