"""
Example: Document parsing with SimpleCrawl API

SimpleCrawl automatically detects PDF and DOCX files and parses them
directly, extracting text, metadata, and optionally images.
"""

import requests
import json

# API base URL
BASE_URL = "http://localhost:8000"


def scrape_pdf():
    """Parse a PDF document - works just like scraping a webpage."""
    print("=== PDF Document Parsing ===\n")

    # Example PDF - Python documentation
    response = requests.post(
        f"{BASE_URL}/v1/scrape",
        json={
            "url": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/img/table-word.pdf",
            "formats": ["markdown", "metadata"]
        }
    )

    data = response.json()

    if data["success"]:
        print("PDF parsed successfully!")
        print(f"\nDocument type: {data['data'].get('document_type', 'N/A')}")
        print(f"Extraction method: {data['data'].get('extraction_method', 'N/A')}")
        print(f"Quality score: {data['data'].get('quality_score', 'N/A')}")

        if data['data'].get('markdown'):
            print(f"\nMarkdown preview:\n{data['data']['markdown'][:500]}...\n")

        if data['data'].get('metadata'):
            meta = data['data']['metadata']
            print(f"Title: {meta.get('title', 'N/A')}")
            print(f"Author: {meta.get('author', 'N/A')}")
            print(f"Page count: {meta.get('pageCount', 'N/A')}")
    else:
        print(f"PDF parsing failed: {data.get('error')}")


def scrape_pdf_with_images():
    """Parse a PDF and extract embedded images."""
    print("\n=== PDF with Image Extraction ===\n")

    response = requests.post(
        f"{BASE_URL}/v1/scrape",
        json={
            "url": "https://www.w3.org/WAI/WCAG21/Techniques/pdf/img/table-word.pdf",
            "formats": ["markdown", "metadata", "media"]
        }
    )

    data = response.json()

    if data["success"]:
        print("PDF parsed successfully!")
        images = data['data'].get('images', [])
        print(f"\nImages extracted: {len(images)}")

        for i, img in enumerate(images[:3]):  # Show first 3
            print(f"  Image {i+1}: {img.get('format', 'unknown')}, "
                  f"{img.get('width', '?')}x{img.get('height', '?')} px")
    else:
        print(f"PDF parsing failed: {data.get('error')}")


def scrape_docx():
    """Parse a DOCX document."""
    print("\n=== DOCX Document Parsing ===\n")

    # Note: Replace with a real DOCX URL for testing
    response = requests.post(
        f"{BASE_URL}/v1/scrape",
        json={
            "url": "https://file-examples.com/storage/fe072f0206683c0f1f10fad/2017/02/file-sample_100kB.docx",
            "formats": ["markdown", "metadata"]
        }
    )

    data = response.json()

    if data["success"]:
        print("DOCX parsed successfully!")
        print(f"\nDocument type: {data['data'].get('document_type', 'N/A')}")
        print(f"Extraction method: {data['data'].get('extraction_method', 'N/A')}")

        if data['data'].get('markdown'):
            print(f"\nMarkdown preview:\n{data['data']['markdown'][:500]}...")

        if data['data'].get('metadata'):
            meta = data['data']['metadata']
            print(f"\nTitle: {meta.get('title', 'N/A')}")
            print(f"Author: {meta.get('author', 'N/A')}")
            print(f"Paragraphs: {meta.get('paragraphCount', 'N/A')}")
            print(f"Tables: {meta.get('tableCount', 'N/A')}")
    else:
        print(f"DOCX parsing failed: {data.get('error')}")


def batch_documents():
    """Parse multiple documents in batch."""
    print("\n=== Batch Document Parsing ===\n")

    response = requests.post(
        f"{BASE_URL}/v1/batch/scrape",
        json={
            "urls": [
                "https://www.w3.org/WAI/WCAG21/Techniques/pdf/img/table-word.pdf",
                "https://example.com"  # Mix of document and webpage
            ],
            "formats": ["markdown", "metadata"]
        }
    )

    data = response.json()

    if data["success"]:
        print(f"Batch job submitted: {data.get('id')}")
        print(f"Check status at: {data.get('status_url')}")
    else:
        print(f"Batch submission failed: {data.get('error')}")


if __name__ == "__main__":
    scrape_pdf()
    scrape_pdf_with_images()
    scrape_docx()
    batch_documents()
