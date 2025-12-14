# SimpleCrawl Quick Start Guide

Get SimpleCrawl running in 5 minutes!

## 🚀 One-Command Start (Docker)

```bash
docker-compose up -d && sleep 5 && curl http://localhost:8000/health
```

That's it! SimpleCrawl is now running on http://localhost:8000

## 📖 Basic Usage

### 1. Scrape a Single URL

```bash
curl -X POST http://localhost:8000/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "formats": ["markdown", "metadata"]
  }'
```

**Response**:
```json
{
  "success": true,
  "data": {
    "markdown": "# Example Domain\n\nThis domain is for use in...",
    "metadata": {
      "title": "Example Domain",
      "language": "en"
    }
  }
}
```

### 2. Map a Website

```bash
curl -X POST http://localhost:8000/v1/map \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com"
  }'
```

**Response**:
```json
{
  "success": true,
  "links": [
    {
      "url": "https://example.com/about",
      "title": "About Us"
    }
  ]
}
```

### 3. Crawl Multiple Pages

```bash
curl -X POST http://localhost:8000/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "limit": 10,
    "depth": 2
  }'
```

**Response**:
```json
{
  "success": true,
  "id": "crawl_abc123",
  "status_url": "/v1/crawl/crawl_abc123"
}
```

**Check status**:
```bash
curl http://localhost:8000/v1/crawl/crawl_abc123
```

### 4. Extract Structured Data with AI

**Requires OpenAI or Anthropic API key in .env**

```bash
curl -X POST http://localhost:8000/v1/extract \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/product"],
    "prompt": "Extract the product name, price, and availability"
  }'
```

## 🎯 Common Use Cases

### Scrape with Page Actions

Wait for dynamic content:
```bash
curl -X POST http://localhost:8000/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "formats": ["markdown"],
    "actions": [
      {"type": "wait", "milliseconds": 2000},
      {"type": "scroll", "direction": "down"}
    ]
  }'
```

### Get All Available Formats

```bash
curl -X POST http://localhost:8000/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "formats": ["markdown", "html", "screenshot", "links", "metadata", "media"]
  }'
```

### Batch Scrape Multiple URLs

```bash
curl -X POST http://localhost:8000/v1/batch/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://example.com/page1",
      "https://example.com/page2",
      "https://example.com/page3"
    ],
    "formats": ["markdown"]
  }'
```

### Monitor Content Changes

```bash
curl -X POST http://localhost:8000/v1/monitor \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/pricing",
    "webhook_url": "https://myapp.com/webhook",
    "interval_hours": 24
  }'
```

## 📚 Interactive Documentation

Visit http://localhost:8000/docs for:
- Complete API reference
- Try out endpoints
- Request/response examples
- Schema definitions

## 🐍 Python Examples

```python
import requests

# Scrape a URL
response = requests.post(
    "http://localhost:8000/v1/scrape",
    json={
        "url": "https://example.com",
        "formats": ["markdown", "metadata"]
    }
)

data = response.json()
if data["success"]:
    print(data["data"]["markdown"])
```

More examples in the `examples/` directory!

## ⚙️ Configuration

Edit `.env` file:

```bash
# Server
PORT=8000

# Browser
BROWSER_POOL_SIZE=5

# AI APIs (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Restart after changes:
```bash
docker-compose restart
```

## 🔍 Troubleshooting

**API not responding?**
```bash
docker-compose logs api
```

**Check health**:
```bash
curl http://localhost:8000/health
```

**Restart everything**:
```bash
docker-compose restart
```

## 📖 Next Steps

- Read the full [README.md](README.md)
- Check [DEPLOYMENT.md](DEPLOYMENT.md) for production setup
- Review [TEST_RESULTS.md](TEST_RESULTS.md) for capabilities
- Explore the [examples/](examples/) directory

## 🆘 Need Help?

- API docs: http://localhost:8000/docs
- GitHub issues: [Open an issue]
- Documentation: [Full README](README.md)

---

**Happy Scraping! 🕷️**
