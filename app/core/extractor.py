"""
AI-powered structured data extraction using OpenAI or Anthropic.

Supports schema-based extraction with JSON Schema validation.
"""

import json
from typing import Dict, Any, List, Optional

from jsonschema import validate, ValidationError as JsonSchemaError

from app.config import settings
from app.core.scraper import scrape_url
from app.utils.logger import get_logger

logger = get_logger(__name__)


def validate_against_schema(data: Any, schema: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate extracted data against a JSON schema.

    Args:
        data: Extracted data to validate
        schema: JSON Schema to validate against

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        validate(instance=data, schema=schema)
        return True, None
    except JsonSchemaError as e:
        return False, str(e.message)


def generate_extraction_prompt(schema: Optional[Dict[str, Any]], prompt: Optional[str]) -> str:
    """
    Generate an optimized system prompt for extraction.

    Args:
        schema: JSON Schema for structured extraction
        prompt: User's natural language prompt

    Returns:
        System prompt string
    """
    parts = [
        "You are a precise data extraction assistant. Your task is to extract structured data from web page content.",
        "Always respond with valid JSON only - no markdown code blocks, no explanations, just the JSON object."
    ]

    if schema:
        # Generate field descriptions from schema
        parts.append(f"\nExtract data matching this JSON schema:\n{json.dumps(schema, indent=2)}")
        parts.append("\nIMPORTANT: Your response must be a valid JSON object that conforms exactly to this schema.")
        parts.append("If a required field cannot be found, use null for optional fields or make a reasonable inference.")

    if prompt:
        parts.append(f"\nAdditional extraction instructions: {prompt}")

    return "\n".join(parts)


async def extract_data(
    urls: List[str],
    schema: Optional[Dict[str, Any]] = None,
    prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract structured data from URLs using AI.

    Supports Firecrawl-compatible schema-based extraction with JSON Schema validation.

    Args:
        urls: List of URLs to extract from
        schema: JSON Schema for structured extraction (validates output)
        prompt: Natural language extraction prompt

    Returns:
        Dict with:
        - data: Extracted data matching the schema
        - sources: List of URLs used for extraction
        - validation: Schema validation result (if schema provided)

    Example schema:
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "price": {"type": "number"},
                "inStock": {"type": "boolean"}
            },
            "required": ["title", "price"]
        }
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

    # Use OpenAI if available, otherwise Anthropic
    if settings.openai_api_key:
        extracted = await extract_with_openai(scraped_data, schema, prompt)
    elif settings.anthropic_api_key:
        extracted = await extract_with_anthropic(scraped_data, schema, prompt)
    else:
        raise ValueError("No AI API key configured")

    # Build result with validation info
    result = {
        "data": extracted,
        "sources": [d["url"] for d in scraped_data],
    }

    # Validate against schema if provided
    if schema:
        is_valid, error = validate_against_schema(extracted, schema)
        result["validation"] = {
            "valid": is_valid,
            "error": error
        }
        if not is_valid:
            logger.warning("schema_validation_failed", error=error)

    logger.info("extract_completed", url_count=len(urls))
    return result


async def extract_with_openai(
    scraped_data: List[Dict[str, Any]],
    schema: Optional[Dict[str, Any]],
    prompt: Optional[str]
) -> Dict[str, Any]:
    """
    Extract data using OpenAI API with structured output support.

    Args:
        scraped_data: List of scraped page data
        schema: JSON Schema for structured extraction
        prompt: Natural language extraction prompt

    Returns:
        Extracted data matching the schema
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)

        # Generate optimized extraction prompt
        system_prompt = generate_extraction_prompt(schema, prompt)

        # Combine all scraped content
        content_parts = []
        for i, data in enumerate(scraped_data):
            content_parts.append(f"=== Page {i+1}: {data['url']} ===")
            content_parts.append(f"Title: {data['title']}")
            if data.get("error"):
                content_parts.append(f"Error: {data['error']}")
            else:
                content_parts.append(f"Content:\n{data['content']}")
            content_parts.append("")

        user_content = "\n".join(content_parts)

        # Call OpenAI with JSON mode when schema is provided
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

        logger.debug("openai_extraction_success", model=settings.openai_model)
        return result

    except json.JSONDecodeError as e:
        logger.error("openai_json_parse_failed", error=str(e))
        raise Exception(f"Failed to parse OpenAI response as JSON: {str(e)}")
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
        schema: JSON Schema for structured extraction
        prompt: Natural language extraction prompt

    Returns:
        Extracted data matching the schema
    """
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)

        # Generate optimized extraction prompt
        system_prompt = generate_extraction_prompt(schema, prompt)

        # Combine all scraped content
        content_parts = []
        for i, data in enumerate(scraped_data):
            content_parts.append(f"=== Page {i+1}: {data['url']} ===")
            content_parts.append(f"Title: {data['title']}")
            if data.get("error"):
                content_parts.append(f"Error: {data['error']}")
            else:
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

        logger.debug("anthropic_extraction_success", model=settings.anthropic_model)
        return result

    except json.JSONDecodeError as e:
        logger.error("anthropic_json_parse_failed", error=str(e))
        raise Exception(f"Failed to parse Anthropic response as JSON: {str(e)}")
    except Exception as e:
        logger.error("anthropic_extraction_failed", error=str(e))
        raise Exception(f"Anthropic extraction failed: {str(e)}")
