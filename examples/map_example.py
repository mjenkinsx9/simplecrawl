"""
Example: Site mapping with SimpleCrawl API
"""

import requests

BASE_URL = "http://localhost:8000"


def map_basic():
    """Basic site mapping."""
    print("=== Basic Site Mapping ===\n")
    
    response = requests.post(
        f"{BASE_URL}/v1/map",
        json={
            "url": "https://example.com"
        }
    )
    
    data = response.json()
    
    if data["success"]:
        print(f"✓ Found {len(data['links'])} links\n")
        for link in data['links']:
            print(f"  - {link['title'] or 'No title'}: {link['url']}")
    else:
        print(f"✗ Mapping failed: {data['error']}")


def map_with_search():
    """Site mapping with search filter."""
    print("\n=== Site Mapping with Search ===\n")
    
    response = requests.post(
        f"{BASE_URL}/v1/map",
        json={
            "url": "https://example.com",
            "search": "example"
        }
    )
    
    data = response.json()
    
    if data["success"]:
        print(f"✓ Found {len(data['links'])} matching links\n")
        for link in data['links']:
            print(f"  - {link['url']}")
    else:
        print(f"✗ Mapping failed: {data['error']}")


if __name__ == "__main__":
    map_basic()
    map_with_search()
