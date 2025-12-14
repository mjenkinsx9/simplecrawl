"""
Extract endpoint for AI-powered data extraction.
"""

from fastapi import APIRouter

from app.models.requests import ExtractRequest
from app.models.responses import ExtractResponse
from app.core.extractor import extract_data
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/extract", response_model=ExtractResponse)
async def extract(request: ExtractRequest):
    """
    Extract structured data from URLs using AI.
    
    Requires either `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to be configured.
    
    You can provide either:
    - `schema`: A JSON schema defining the structure to extract
    - `prompt`: A natural language description of what to extract
    - Both: For more precise extraction
    
    Example with schema:
    ```json
    {
      "urls": ["https://example.com/product"],
      "schema": {
        "type": "object",
        "properties": {
          "productName": {"type": "string"},
          "price": {"type": "number"},
          "inStock": {"type": "boolean"}
        }
      }
    }
    ```
    
    Example with prompt:
    ```json
    {
      "urls": ["https://example.com/article"],
      "prompt": "Extract the article title, author, publication date, and main points"
    }
    ```
    """
    try:
        logger.info("extract_request", url_count=len(request.urls))
        
        result = await extract_data(
            urls=[str(url) for url in request.urls],
            schema=request.schema,
            prompt=request.prompt
        )
        
        return ExtractResponse(
            success=True,
            data=result
        )
    
    except Exception as e:
        logger.error("extract_request_failed", error=str(e))
        return ExtractResponse(
            success=False,
            error={
                "code": "EXTRACT_FAILED",
                "message": str(e)
            }
        )
