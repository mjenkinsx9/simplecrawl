"""
Configuration management for SimpleCrawl using pydantic-settings.
All settings are loaded from environment variables with sensible defaults.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    log_level: str = "INFO"
    
    # Redis settings
    redis_url: str = "redis://localhost:6379/0"
    
    # Database settings
    database_url: str = "sqlite:///./simplecrawl.db"
    
    # AI API settings (optional)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4.1-mini"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-haiku-20240307"
    
    # Proxy settings (optional)
    proxy_url: Optional[str] = None
    proxy_list_file: Optional[str] = None
    proxy_rotation_enabled: bool = False
    
    # Scraping limits
    max_crawl_depth: int = 10
    max_crawl_pages: int = 1000
    max_concurrent_requests: int = 10
    job_retention_hours: int = 24
    request_timeout_seconds: int = 30
    
    # Browser settings
    headless: bool = True
    user_agent: str = "SimpleCrawl/1.0 (https://github.com/simplecrawl)"
    browser_pool_size: int = 5
    
    # Media settings
    media_storage_dir: str = "/app/media"
    media_formats: str = "jpeg,jpg,png,gif,webp,avif,svg"
    max_media_size_mb: int = 50
    
    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_period_seconds: int = 60
    
    @property
    def media_formats_list(self) -> list[str]:
        """Get media formats as a list."""
        return [fmt.strip().lower() for fmt in self.media_formats.split(",")]
    
    @property
    def max_media_size_bytes(self) -> int:
        """Get max media size in bytes."""
        return self.max_media_size_mb * 1024 * 1024


# Global settings instance
settings = Settings()
