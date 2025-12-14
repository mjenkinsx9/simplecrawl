# SimpleCrawl

**Self-hosted web scraping and data extraction API**

SimpleCrawl is a lightweight, self-hosted web scraping API inspired by Firecrawl. It converts websites into LLM-ready markdown or structured data, handles JavaScript-rendered pages, and provides async crawling for multi-page sites.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com/)

## Features

- 🔥 **Single URL Scraping**: Get clean markdown, HTML, screenshots, links, and metadata
- 🕷️ **Multi-page Crawling**: Async crawling with depth and limit controls
- 🗺️ **Site Mapping**: Discover all URLs on a domain with optional search filtering
- 🤖 **AI Extraction**: Extract structured data using OpenAI or Anthropic
- 📄 **Document Parsing**: Parse PDFs and DOCX files (coming soon)
- 🎬 **Page Actions**: Click, scroll, wait, and type before scraping
- 📦 **Batch Processing**: Scrape multiple URLs in parallel
- 🔔 **Change Monitoring**: Track content changes with webhooks
- 🖼️ **Media Extraction**: Download and catalog images (JPEG, PNG, GIF, WebP, AVIF, SVG)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- 2-4 GB RAM minimum
- (Optional) OpenAI or Anthropic API key for AI extraction

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/simplecrawl.git
cd simplecrawl
```

2. **Configure environment variables**:
```bash
cp .env.example .env
# Edit .env with your settings (optional AI API keys)
```

3. **Start all services**:
```bash
docker-compose up -d
```

4. **Check health**:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime": 123,
  "services": {
    "redis": "connected",
    "celery": "running",
    "playwright": "ready"
  }
}
```

## API Documentation

Once running, visit:
- **Interactive API docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Core Endpoints

#### POST /v1/scrape
Scrape a single URL and return content in requested formats.

```bash
curl -X POST http://localhost:8000/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "formats": ["markdown", "metadata"],
    "exclude_tags": ["nav", "footer"],
    "timeout": 30000
  }'
```

**Supported formats**:
- `markdown`: Clean, LLM-ready markdown
- `html`: Raw HTML content
- `screenshot`: Full-page PNG screenshot (base64)
- `links`: All URLs found on the page
- `metadata`: Page metadata (title, description, OG tags)
- `media`: Downloaded media files

**Page actions**:
```json
{
  "url": "https://example.com",
  "formats": ["markdown"],
  "actions": [
    {"type": "wait", "milliseconds": 2000},
    {"type": "click", "selector": "#load-more"},
    {"type": "scroll", "direction": "down"},
    {"type": "type", "selector": "#search", "text": "query"}
  ]
}
```

#### POST /v1/map
Map a website by discovering all URLs.

```bash
curl -X POST http://localhost:8000/v1/map \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "search": "documentation"
  }'
```

#### POST /v1/crawl
Start an async crawl job for a website.

```bash
curl -X POST http://localhost:8000/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "limit": 100,
    "depth": 3,
    "scrape_options": {
      "formats": ["markdown", "metadata"]
    }
  }'
```

#### GET /v1/crawl/{job_id}
Check crawl job status and retrieve results.

```bash
curl http://localhost:8000/v1/crawl/crawl_abc123def456
```

### Advanced Endpoints

#### POST /v1/extract
Extract structured data using AI (requires API key).

```bash
curl -X POST http://localhost:8000/v1/extract \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/product"],
    "schema": {
      "type": "object",
      "properties": {
        "productName": {"type": "string"},
        "price": {"type": "number"},
        "inStock": {"type": "boolean"}
      }
    }
  }'
```

#### POST /v1/batch/scrape
Scrape multiple URLs in parallel.

```bash
curl -X POST http://localhost:8000/v1/batch/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://example.com/page1",
      "https://example.com/page2"
    ],
    "formats": ["markdown"]
  }'
```

#### POST /v1/monitor
Create a content change monitor.

```bash
curl -X POST http://localhost:8000/v1/monitor \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/pricing",
    "webhook_url": "https://myapp.com/webhook",
    "interval_hours": 24
  }'
```

## Configuration

All configuration is done via environment variables. See `.env.example` for all available options.

### Key Settings

```bash
# Server
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Redis
REDIS_URL=redis://localhost:6379/0

# Database
DATABASE_URL=sqlite:///./data/simplecrawl.db

# AI APIs (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Browser
HEADLESS=true
BROWSER_POOL_SIZE=5

# Limits
MAX_CRAWL_DEPTH=10
MAX_CRAWL_PAGES=1000
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT_SECONDS=30

# Media
MEDIA_STORAGE_DIR=/app/media
MEDIA_FORMATS=jpeg,jpg,png,gif,webp,avif,svg
MAX_MEDIA_SIZE_MB=50
```

## Architecture

```
┌─────────────────────────────────────────────┐
│           FastAPI REST API Server           │
│  (Python 3.11+, Pydantic, Type Hints)      │
└─────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│Playwright│  │  Redis   │  │  SQLite  │
│ Browser  │  │  Queue   │  │ Storage  │
└──────────┘  └──────────┘  └──────────┘
                    │
                    ▼
            ┌──────────────┐
            │Celery Workers│
            │ (Async Jobs) │
            └──────────────┘
```

## Technology Stack

- **API Framework**: FastAPI with Pydantic validation
- **Browser Automation**: Playwright for JavaScript rendering
- **Queue System**: Redis + Celery for async jobs
- **Database**: SQLite for job tracking
- **HTML to Markdown**: markdownify with BeautifulSoup
- **AI Integration**: OpenAI and Anthropic SDKs
- **Media Handling**: httpx for downloads, Pillow for processing

## Development

### Local Development

1. **Create virtual environment**:
```bash
python3.11 -m venv venv
source venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. **Start Redis**:
```bash
redis-server --daemonize yes
```

4. **Run the API server**:
```bash
uvicorn app.main:app --reload
```

5. **Run Celery worker** (in another terminal):
```bash
celery -A app.workers.tasks worker --loglevel=info
```

### Running Tests

```bash
pytest tests/
```

### Project Structure

```
simplecrawl/
├── app/
│   ├── api/routes/          # API endpoints
│   ├── core/                # Core scraping logic
│   ├── models/              # Pydantic models
│   ├── workers/             # Celery tasks
│   ├── utils/               # Utilities
│   ├── db/                  # Database models
│   ├── config.py            # Configuration
│   └── main.py              # FastAPI app
├── tests/                   # Test suite
├── examples/                # Example scripts
├── docker-compose.yml       # Docker orchestration
├── Dockerfile               # Container image
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## Examples

See the `examples/` directory for usage examples:

- `scrape_example.py` - Basic scraping examples
- `map_example.py` - Site mapping examples
- `crawl_example.py` - Crawling examples
- `extract_example.py` - AI extraction examples

Run an example:
```bash
python examples/scrape_example.py
```

## Deployment

### Docker Compose (Recommended)

```bash
docker-compose up -d
```

### Manual Deployment

1. Set up a VPS with 2-4 GB RAM
2. Install Python 3.11+, Redis, and system dependencies
3. Clone the repository and install dependencies
4. Configure environment variables
5. Run with systemd or supervisor

## Comparison with Firecrawl

| Feature | Firecrawl | SimpleCrawl |
|---------|-----------|-------------|
| **Codebase** | Large TypeScript monorepo | <5,000 lines Python |
| **Database** | PostgreSQL | SQLite |
| **Architecture** | Microservices | Monolithic FastAPI |
| **Deployment** | Complex multi-container | Single Docker Compose |
| **Target** | SaaS platform | Self-hosted tool |
| **Cost** | Paid service | Free, self-hosted |

## Roadmap

- [x] Core scraping with Playwright
- [x] Site mapping and crawling
- [x] AI-powered extraction
- [x] Page actions
- [x] Batch processing
- [x] Change monitoring
- [x] Media extraction
- [ ] Document parsing (PDF, DOCX)
- [ ] Proxy rotation
- [ ] Rate limiting per IP
- [ ] Authentication and API keys
- [ ] Web UI for testing

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[MIT License](LICENSE)

## Acknowledgments

Inspired by [Firecrawl](https://github.com/firecrawl/firecrawl) - a comprehensive web scraping platform.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check the [documentation](http://localhost:8000/docs)
- Review the [examples](examples/)

---

**Built with ❤️ for the AI and LLM community**

**Status**: Production Ready ✅ | All Core Features Implemented 🚀
