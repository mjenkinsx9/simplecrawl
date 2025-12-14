FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright and build tools
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # Fonts (using correct package names for Debian trixie)
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (with retries and longer timeout for slow networks)
RUN pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

# Install Playwright Chromium browser (without --with-deps since we installed deps above)
RUN playwright install chromium

# Copy application code
COPY app/ /app/app/

# Create media directory
RUN mkdir -p /app/media

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
