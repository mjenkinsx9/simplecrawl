#!/usr/bin/env python3
"""
Examples demonstrating Firecrawl-compatible features in SimpleCrawl.

Features covered:
1. Custom Headers - For authenticated/protected sites
2. Write/Press Actions - Form interaction (login, search)
3. Schema-based Extract - Structured data extraction with validation
"""

import httpx
import json

BASE_URL = "http://localhost:8000/v1"


def example_custom_headers():
    """
    Example 1: Custom Headers for Authenticated Sites

    Use custom headers to access protected content behind authentication.
    Common headers: Authorization, Cookie, X-API-Key
    """
    print("\n" + "=" * 60)
    print("Example 1: Custom Headers")
    print("=" * 60)

    # Scrape a protected page with auth headers
    response = httpx.post(
        f"{BASE_URL}/scrape",
        json={
            "url": "https://httpbin.org/headers",
            "formats": ["markdown"],
            "headers": {
                "Authorization": "Bearer my-secret-token",
                "X-Custom-Header": "SimpleCrawl-Test"
            }
        },
        timeout=60.0
    )

    result = response.json()
    print(f"Success: {result.get('success')}")
    if result.get("success"):
        # The response will show our custom headers were sent
        print("Custom headers were sent with the request!")
        print(f"Preview: {result['data'].get('markdown', '')[:500]}...")


def example_write_press_actions():
    """
    Example 2: Write/Press Actions for Form Interaction

    Use "write" (or "type") and "press" actions to interact with forms.
    This is useful for:
    - Logging into sites
    - Submitting search forms
    - Filling out any form before scraping
    """
    print("\n" + "=" * 60)
    print("Example 2: Write/Press Actions")
    print("=" * 60)

    # Example: Search on DuckDuckGo using actions
    response = httpx.post(
        f"{BASE_URL}/scrape",
        json={
            "url": "https://duckduckgo.com",
            "formats": ["markdown", "screenshot"],
            "actions": [
                # Wait for page to load
                {"type": "wait", "milliseconds": 1000},
                # Type into search box using "write" (Firecrawl-compatible)
                {"type": "write", "selector": "input[name='q']", "text": "SimpleCrawl web scraping"},
                # Press Enter to search
                {"type": "press", "key": "Enter"},
                # Wait for results
                {"type": "wait", "milliseconds": 2000}
            ],
            "wait_until": "networkidle"
        },
        timeout=90.0
    )

    result = response.json()
    print(f"Success: {result.get('success')}")
    if result.get("success"):
        print("Search was performed using write/press actions!")
        markdown = result["data"].get("markdown", "")
        print(f"Found {len(markdown)} chars of content")
        if result["data"].get("screenshot"):
            print("Screenshot captured after search!")


def example_schema_extract():
    """
    Example 3: Schema-based Extract with Validation

    Define a JSON Schema and extract structured data from web pages.
    The response includes validation results.
    """
    print("\n" + "=" * 60)
    print("Example 3: Schema-based Extract")
    print("=" * 60)

    # Define a schema for extracting product information
    product_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Product name"
            },
            "price": {
                "type": "number",
                "description": "Price in USD"
            },
            "currency": {
                "type": "string",
                "description": "Currency code"
            },
            "description": {
                "type": "string",
                "description": "Product description"
            },
            "features": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of key features"
            },
            "inStock": {
                "type": "boolean",
                "description": "Whether the product is in stock"
            }
        },
        "required": ["name", "price"]
    }

    # Extract from Ashes of Creation shop page
    response = httpx.post(
        f"{BASE_URL}/extract",
        json={
            "urls": ["https://ashesofcreation.com/shop/product/early-access"],
            "schema": product_schema,
            "prompt": "Extract information about the Early Access Bundle product"
        },
        timeout=120.0
    )

    result = response.json()
    print(f"Success: {result.get('success')}")

    if result.get("success"):
        data = result.get("data", {})
        print(f"\nExtracted Data:")
        print(json.dumps(data.get("data"), indent=2))
        print(f"\nSources: {data.get('sources')}")
        print(f"\nValidation: {data.get('validation')}")


def example_crawl_with_headers():
    """
    Example 4: Crawl with Custom Headers

    Crawl an authenticated site by passing headers.
    """
    print("\n" + "=" * 60)
    print("Example 4: Crawl with Headers")
    print("=" * 60)

    response = httpx.post(
        f"{BASE_URL}/crawl",
        json={
            "url": "https://httpbin.org/anything",
            "limit": 5,
            "depth": 1,
            "headers": {
                "Authorization": "Bearer crawl-token",
                "Cookie": "session=abc123"
            },
            "scrape_options": {
                "formats": ["markdown"]
            }
        },
        timeout=30.0
    )

    result = response.json()
    print(f"Success: {result.get('success')}")
    if result.get("success"):
        print(f"Job ID: {result.get('id')}")
        print(f"Check status at: {result.get('status_url')}")


def example_login_flow():
    """
    Example 5: Complete Login Flow

    Demonstrates logging into a site before scraping protected content.
    Uses write/press actions for the login form.

    Note: This is a template - replace with actual login credentials and selectors.
    """
    print("\n" + "=" * 60)
    print("Example 5: Login Flow (Template)")
    print("=" * 60)

    # Template for a login flow
    login_actions = [
        # Wait for login form to appear
        {"type": "wait", "selector": "#login-form"},

        # Enter username
        {"type": "write", "selector": "#username", "text": "your-username"},

        # Enter password
        {"type": "write", "selector": "#password", "text": "your-password"},

        # Click login button
        {"type": "click", "selector": "#login-button"},

        # Wait for redirect to dashboard
        {"type": "wait", "selector": ".dashboard-content", "timeout": 10000}
    ]

    print("Login flow actions:")
    for i, action in enumerate(login_actions):
        print(f"  {i+1}. {action['type']}: {action.get('selector', action.get('text', ''))}")

    print("\nTo use this, send to /scrape with your actual login page URL")


if __name__ == "__main__":
    print("SimpleCrawl - Firecrawl-Compatible Features Demo")
    print("=" * 60)
    print("Make sure SimpleCrawl is running at http://localhost:8000")

    # Run examples
    try:
        example_custom_headers()
    except Exception as e:
        print(f"Example 1 failed: {e}")

    try:
        example_write_press_actions()
    except Exception as e:
        print(f"Example 2 failed: {e}")

    try:
        example_schema_extract()
    except Exception as e:
        print(f"Example 3 failed: {e}")

    try:
        example_crawl_with_headers()
    except Exception as e:
        print(f"Example 4 failed: {e}")

    # Just show the template, don't run it
    example_login_flow()

    print("\n" + "=" * 60)
    print("All examples completed!")
