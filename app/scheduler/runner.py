"""
Scheduler runner.

Starts a background loop that periodically fetches and ingests data
from the external Scraper API. Uses the `scheduler` library for
lightweight cron management without system-level dependencies.
"""

import logging
import time

import schedule

from app.scheduler.config import scheduler_settings
from app.scheduler.job import run_with_retry

logger = logging.getLogger(__name__)


def _run_job_wrapper() -> None:
    """Wrapper around run_with_retry that logs exceptions."""
    try:
        logger.info("=== Scheduler job started ===")
        run_with_retry()
    except Exception as e:
        logger.exception("Unhandled scheduler job error: %s", e)
    finally:
        logger.info("=== Scheduler job finished ===")


def start_scheduler(run_immediately: bool = True) -> None:
    """
    Start the scheduler loop.

    The job runs at the interval configured by ``cron_interval_minutes``.
    If ``run_immediately`` is True (default), the first job execution
    starts right away without waiting for the interval.

    Args:
        run_immediately: If True, runs the job immediately on start.
    """
    interval = scheduler_settings.cron_interval_minutes
    logger.info(
        "Starting scheduler with interval=%d minutes (run_immediately=%s)",
        interval,
        run_immediately,
    )

    # Schedule the job
    schedule.every(interval).minutes.do(_run_job_wrapper)

    # Run immediately if requested
    if run_immediately:
        logger.info("Running scheduler job immediately...")
        _run_job_wrapper()

    # Main loop
    logger.info("Scheduler entering main loop. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)


def main() -> None:
    """Entry point for running the scheduler standalone."""
    logging.basicConfig(level=logging.INFO)
    start_scheduler()


if __name__ == "__main__":
    main()
