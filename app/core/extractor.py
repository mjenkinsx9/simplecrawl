"""
AI-powered structured data extraction using OpenAI or Anthropic.
"""

import json
from typing import Dict, Any, List, Optional

from app.config import settings
from app.core.scraper import scrape_url
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def extract_data(
    urls: List[str],
    schema: Optional[Dict[str, Any]] = None,
    prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract structured data from URLs using AI.
    
    Args:
        urls: List of URLs to extract from
        schema: JSON schema for structured extraction
        prompt: Natural language extraction prompt
    
    Returns:
        Extracted data matching the schema
    """
    if not schema and not prompt:
        raise ValueError("Either schema or prompt must be provided")
    
    if not settings.openai_api_key and not settings.anthropic_api_key:
        raise ValueError("AI extraction requires OPENAI_API_KEY or ANTHROPIC_API_KEY")
    
    logger.info("extract_started", url_count=len(urls), has_schema=bool(schema))
    
    # Scrape all URLs first
    scraped_data = []
    for url in urls:
        try:
            data = await scrape_url(url, formats=["markdown", "metadata"])
            scraped_data.append({
                "url": url,
                "content": data.get("markdown", ""),
                "title": data.get("metadata", {}).get("title", "")
            })
        except Exception as e:
            logger.error("extract_scrape_failed", url=url, error=str(e))
            scraped_data.append({
                "url": url,
                "content": "",
                "title": "",
                "error": str(e)
            })
    
    # Use OpenAI if available
    if settings.openai_api_key:
        result = await extract_with_openai(scraped_data, schema, prompt)
    elif settings.anthropic_api_key:
        result = await extract_with_anthropic(scraped_data, schema, prompt)
    else:
        raise ValueError("No AI API key configured")
    
    logger.info("extract_completed", url_count=len(urls))
    return result


async def extract_with_openai(
    scraped_data: List[Dict[str, Any]],
    schema: Optional[Dict[str, Any]],
    prompt: Optional[str]
) -> Dict[str, Any]:
    """
    Extract data using OpenAI API.
    
    Args:
        scraped_data: List of scraped page data
        schema: JSON schema
        prompt: Extraction prompt
    
    Returns:
        Extracted data
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=settings.openai_api_key)
        
        # Build extraction prompt
        system_prompt = "You are a data extraction assistant. Extract structured data from the provided web page content."
        
        if schema:
            system_prompt += f"\n\nExtract data matching this JSON schema:\n{json.dumps(schema, indent=2)}"
        
        if prompt:
            system_prompt += f"\n\nAdditional instructions: {prompt}"
        
        # Combine all scraped content
        content_parts = []
        for i, data in enumerate(scraped_data):
            content_parts.append(f"=== Page {i+1}: {data['url']} ===")
            content_parts.append(f"Title: {data['title']}")
            content_parts.append(f"Content:\n{data['content']}")
            content_parts.append("")
        
        user_content = "\n".join(content_parts)
        
        # Call OpenAI
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"} if schema else None,
            temperature=0.1
        )
        
        # Parse response
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        
        return result
    
    except Exception as e:
        logger.error("openai_extraction_failed", error=str(e))
        raise Exception(f"OpenAI extraction failed: {str(e)}")


async def extract_with_anthropic(
    scraped_data: List[Dict[str, Any]],
    schema: Optional[Dict[str, Any]],
    prompt: Optional[str]
) -> Dict[str, Any]:
    """
    Extract data using Anthropic API.
    
    Args:
        scraped_data: List of scraped page data
        schema: JSON schema
        prompt: Extraction prompt
    
    Returns:
        Extracted data
    """
    try:
        from anthropic import Anthropic
        
        client = Anthropic(api_key=settings.anthropic_api_key)
        
        # Build extraction prompt
        system_prompt = "You are a data extraction assistant. Extract structured data from the provided web page content and return it as JSON."
        
        if schema:
            system_prompt += f"\n\nExtract data matching this JSON schema:\n{json.dumps(schema, indent=2)}"
        
        if prompt:
            system_prompt += f"\n\nAdditional instructions: {prompt}"
        
        # Combine all scraped content
        content_parts = []
        for i, data in enumerate(scraped_data):
            content_parts.append(f"=== Page {i+1}: {data['url']} ===")
            content_parts.append(f"Title: {data['title']}")
            content_parts.append(f"Content:\n{data['content']}")
            content_parts.append("")
        
        user_content = "\n".join(content_parts)
        
        # Call Anthropic
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_content}
            ],
            temperature=0.1
        )
        
        # Parse response
        result_text = response.content[0].text
        
        # Extract JSON from response (may be wrapped in markdown code blocks)
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(result_text)
        
        return result
    
    except Exception as e:
        logger.error("anthropic_extraction_failed", error=str(e))
        raise Exception(f"Anthropic extraction failed: {str(e)}")
