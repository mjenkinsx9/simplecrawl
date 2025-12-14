"""
Batch scraping endpoint for processing multiple URLs.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.models.requests import BatchScrapeRequest
from app.models.responses import JobResponse, JobStatusResponse
from app.config import settings
from app.db.models import BatchJob, get_session
from app.workers.tasks import batch_scrape_task
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/batch/scrape", response_model=JobResponse)
async def start_batch_scrape(request: BatchScrapeRequest):
    """
    Start a batch scraping job for multiple URLs.
    
    This endpoint:
    1. Creates a batch job in the database
    2. Submits the job to Celery for async processing
    3. Returns a job ID for status checking
    
    URLs are processed in parallel with configurable concurrency.
    
    Example:
    ```json
    {
      "urls": [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page3"
      ],
      "formats": ["markdown", "metadata"]
    }
    ```
    
    Returns a job ID that can be used with `GET /v1/batch/{job_id}` to check status.
    """
    try:
        logger.info("batch_scrape_request", url_count=len(request.urls))
        
        # Generate job ID
        job_id = f"batch_{uuid.uuid4().hex[:16]}"
        
        # Create job in database
        db = get_session(settings.database_url)
        job = BatchJob(
            id=job_id,
            status="pending",
            total=len(request.urls),
            completed=0,
            failed=0,
            config={
                "urls": [str(url) for url in request.urls],
                "formats": request.formats
            },
            created_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.close()
        
        # Submit to Celery
        batch_scrape_task.delay(
            job_id,
            [str(url) for url in request.urls],
            {"formats": request.formats}
        )
        
        logger.info("batch_scrape_job_created", job_id=job_id)
        
        return JobResponse(
            success=True,
            id=job_id,
            status_url=f"/v1/batch/{job_id}"
        )
    
    except Exception as e:
        logger.error("batch_scrape_request_failed", error=str(e))
        return JobResponse(
            success=False,
            error={
                "code": "BATCH_START_FAILED",
                "message": str(e)
            }
        )


@router.get("/batch/{job_id}", response_model=JobStatusResponse)
async def get_batch_status(job_id: str):
    """
    Get the status of a batch scraping job.
    
    Returns:
    - `status`: Job status (pending, running, completed, failed)
    - `total`: Total number of URLs
    - `completed`: Number of completed URLs
    - `failed`: Number of failed URLs
    - `data`: Scrape results (when completed)
    - `created_at`: Job creation time
    - `completed_at`: Job completion time (when completed)
    
    Example:
    ```
    GET /v1/batch/batch_abc123def456
    ```
    """
    try:
        db = get_session(settings.database_url)
        job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
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
        logger.error("get_batch_status_failed", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
