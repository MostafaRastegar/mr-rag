"""
Scheduler configuration.

Loads environment variables for the data ingestion scheduler,
including API credentials, retry settings, and cron interval.
"""

from pydantic_settings import BaseSettings


class SchedulerSettings(BaseSettings):
    """Configuration for the data ingestion scheduler."""

    # External Scraper API
    scraper_api_url: str = "https://scraper.example.com"
    scraper_username: str = "mostafa"
    scraper_password: str = "mostafa123456"

    # Schedule (minutes)
    cron_interval_minutes: int = 60

    # Retry settings
    max_retries: int = 5
    retry_delay_seconds: int = 60
    retry_backoff_factor: float = 2.0  # exponential backoff: 60, 120, 240, ...

    # Data paths
    temp_data_dir: str = "data/scraped"
    log_file: str = "data/scheduler_log.json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


scheduler_settings = SchedulerSettings()
