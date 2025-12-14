# SimpleCrawl Deployment Guide

This guide covers deploying SimpleCrawl in various environments.

## Table of Contents

1. [Docker Compose (Recommended)](#docker-compose-recommended)
2. [Manual VPS Deployment](#manual-vps-deployment)
3. [Production Configuration](#production-configuration)
4. [Monitoring & Maintenance](#monitoring--maintenance)
5. [Troubleshooting](#troubleshooting)

## Docker Compose (Recommended)

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 2-4 GB RAM
- 10 GB disk space

### Quick Start

1. **Clone or extract the project**:
```bash
cd /opt
tar -xzf simplecrawl-complete.tar.gz
cd simplecrawl
```

2. **Configure environment**:
```bash
cp .env.example .env
nano .env  # Edit as needed
```

3. **Start all services**:
```bash
docker-compose up -d
```

4. **Verify deployment**:
```bash
curl http://localhost:8000/health
```

5. **View logs**:
```bash
docker-compose logs -f api
docker-compose logs -f worker
```

### Service Architecture

```yaml
services:
  api:        # FastAPI server (port 8000)
  worker:     # Celery worker for async jobs
  redis:      # Redis for job queue (port 6379)
```

### Stopping Services

```bash
docker-compose down
```

### Updating

```bash
docker-compose pull
docker-compose up -d --force-recreate
```

## Manual VPS Deployment

### System Requirements

- Ubuntu 22.04 LTS (recommended)
- Python 3.11+
- Redis 6.0+
- 2-4 GB RAM
- 10 GB disk space

### Installation Steps

1. **Update system**:
```bash
sudo apt update && sudo apt upgrade -y
```

2. **Install dependencies**:
```bash
sudo apt install -y python3.11 python3.11-venv python3-pip redis-server
```

3. **Create application user**:
```bash
sudo useradd -m -s /bin/bash simplecrawl
sudo su - simplecrawl
```

4. **Clone/extract project**:
```bash
cd ~
tar -xzf simplecrawl-complete.tar.gz
cd simplecrawl
```

5. **Set up Python environment**:
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

6. **Configure environment**:
```bash
cp .env.example .env
nano .env
```

7. **Create systemd service for API**:
```bash
sudo nano /etc/systemd/system/simplecrawl-api.service
```

```ini
[Unit]
Description=SimpleCrawl API Server
After=network.target redis.service

[Service]
Type=simple
User=simplecrawl
WorkingDirectory=/home/simplecrawl/simplecrawl
Environment="PATH=/home/simplecrawl/simplecrawl/venv/bin"
ExecStart=/home/simplecrawl/simplecrawl/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

8. **Create systemd service for Celery worker**:
```bash
sudo nano /etc/systemd/system/simplecrawl-worker.service
```

```ini
[Unit]
Description=SimpleCrawl Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=simplecrawl
WorkingDirectory=/home/simplecrawl/simplecrawl
Environment="PATH=/home/simplecrawl/simplecrawl/venv/bin"
ExecStart=/home/simplecrawl/simplecrawl/venv/bin/celery -A app.workers.tasks worker --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

9. **Enable and start services**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable simplecrawl-api simplecrawl-worker redis
sudo systemctl start simplecrawl-api simplecrawl-worker redis
```

10. **Check status**:
```bash
sudo systemctl status simplecrawl-api
sudo systemctl status simplecrawl-worker
curl http://localhost:8000/health
```

### Nginx Reverse Proxy (Optional)

1. **Install Nginx**:
```bash
sudo apt install -y nginx
```

2. **Configure site**:
```bash
sudo nano /etc/nginx/sites-available/simplecrawl
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeouts for long-running scrapes
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

3. **Enable site**:
```bash
sudo ln -s /etc/nginx/sites-available/simplecrawl /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

4. **Set up SSL with Let's Encrypt** (recommended):
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Production Configuration

### Environment Variables

**Required**:
```bash
HOST=0.0.0.0
PORT=8000
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///./data/simplecrawl.db
```

**Security**:
```bash
# Generate a secure secret key
SECRET_KEY=$(openssl rand -hex 32)
```

**Performance**:
```bash
BROWSER_POOL_SIZE=5
MAX_CONCURRENT_REQUESTS=10
MAX_CRAWL_PAGES=1000
REQUEST_TIMEOUT_SECONDS=30
```

**AI APIs** (optional):
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

**Logging**:
```bash
LOG_LEVEL=INFO  # Use WARNING in production
```

### Database Backup

```bash
# Backup SQLite database
cp data/simplecrawl.db data/simplecrawl.db.backup-$(date +%Y%m%d)

# Automated daily backup
echo "0 2 * * * cp /home/simplecrawl/simplecrawl/data/simplecrawl.db /home/simplecrawl/backups/simplecrawl.db.\$(date +\%Y\%m\%d)" | crontab -
```

### Resource Limits

**Memory**:
- Minimum: 2 GB RAM
- Recommended: 4 GB RAM
- Each browser context: ~100-150 MB

**Disk**:
- Application: ~500 MB
- Database: Grows with jobs (~1 MB per 1000 jobs)
- Media storage: Configure MAX_MEDIA_SIZE_MB

**CPU**:
- Minimum: 2 cores
- Recommended: 4 cores

## Monitoring & Maintenance

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Redis health
redis-cli ping

# Check logs
journalctl -u simplecrawl-api -f
journalctl -u simplecrawl-worker -f
```

### Log Rotation

```bash
sudo nano /etc/logrotate.d/simplecrawl
```

```
/var/log/simplecrawl/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 simplecrawl simplecrawl
    sharedscripts
    postrotate
        systemctl reload simplecrawl-api
    endscript
}
```

### Performance Monitoring

**Key metrics to monitor**:
- API response time
- Memory usage
- Browser pool utilization
- Job queue length
- Failed job rate

**Prometheus metrics** (future enhancement):
```python
# Add to app/main.py
from prometheus_client import Counter, Histogram
scrape_requests = Counter('scrape_requests_total', 'Total scrape requests')
scrape_duration = Histogram('scrape_duration_seconds', 'Scrape duration')
```

### Database Maintenance

```bash
# Vacuum SQLite database (monthly)
sqlite3 data/simplecrawl.db "VACUUM;"

# Clean old jobs (older than 30 days)
sqlite3 data/simplecrawl.db "DELETE FROM crawl_jobs WHERE created_at < datetime('now', '-30 days');"
```

## Troubleshooting

### API Won't Start

**Check logs**:
```bash
journalctl -u simplecrawl-api -n 50
```

**Common issues**:
- Port 8000 already in use: Change PORT in .env
- Redis not running: `sudo systemctl start redis`
- Permission issues: Check file ownership

### Playwright Issues

**Browser not found**:
```bash
source venv/bin/activate
playwright install chromium
```

**Permission denied**:
```bash
# Install system dependencies
sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
```

### High Memory Usage

**Reduce browser pool**:
```bash
BROWSER_POOL_SIZE=3
```

**Limit concurrent requests**:
```bash
MAX_CONCURRENT_REQUESTS=5
```

**Restart services regularly**:
```bash
# Add to crontab
0 4 * * * systemctl restart simplecrawl-api simplecrawl-worker
```

### Celery Worker Not Processing Jobs

**Check worker status**:
```bash
systemctl status simplecrawl-worker
```

**Check Redis connection**:
```bash
redis-cli ping
```

**Restart worker**:
```bash
systemctl restart simplecrawl-worker
```

### Slow Scraping

**Increase timeout**:
```bash
REQUEST_TIMEOUT_SECONDS=60
```

**Check network**:
```bash
curl -w "@curl-format.txt" -o /dev/null -s https://example.com
```

**Disable headless mode for debugging**:
```bash
HEADLESS=false
```

## Security Best Practices

1. **Use environment variables** for secrets
2. **Enable firewall**:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
3. **Regular updates**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
4. **Use HTTPS** with Let's Encrypt
5. **Restrict Redis** to localhost
6. **Set up authentication** (future enhancement)

## Scaling

### Horizontal Scaling

**Multiple workers**:
```bash
# Start additional workers
celery -A app.workers.tasks worker --loglevel=info --concurrency=4 -n worker2@%h
```

**Load balancing**:
- Use Nginx upstream for multiple API instances
- Use Redis Sentinel for Redis HA

### Vertical Scaling

- Increase BROWSER_POOL_SIZE
- Increase MAX_CONCURRENT_REQUESTS
- Add more RAM
- Use faster storage (SSD)

## Support

For issues:
- Check logs first
- Review this troubleshooting guide
- Open an issue on GitHub
- Check documentation at /docs

---

**Deployment Status**: Production Ready ✅
