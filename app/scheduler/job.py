"""
Scheduler job logic.

Orchestrates: fetch → save temp file → ingest → log → cleanup.
Includes retry logic with exponential backoff for external API failures.
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from app.scheduler.auth import ScraperAuth, ScraperAuthError
from app.scheduler.client import ScraperClient, ScraperClientError
from app.scheduler.config import scheduler_settings
from app.scheduler.logger import log_last_fetch

logger = logging.getLogger(__name__)


def _ensure_temp_dir() -> Path:
    """Create the temp data directory if it doesn't exist."""
    temp_dir = Path(scheduler_settings.temp_data_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _save_to_temp_file(data: List[Dict[str, Any]]) -> Path:
    """
    Save fetched data to a temporary JSON file.

    The file is named with a UUID to avoid collisions.

    Args:
        data: The message data to save.

    Returns:
        Path to the created temp file.
    """
    temp_dir = _ensure_temp_dir()
    filename = f"temp_{uuid.uuid4().hex[:12]}.json"
    temp_path = temp_dir / filename

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("Saved %d documents to %s", len(data), temp_path)
    return temp_path


def _delete_temp_file(path: Path) -> None:
    """Delete a temp file, logging a warning if it fails."""
    try:
        if path.exists():
            path.unlink()
            logger.info("Deleted temp file: %s", path)
    except OSError as e:
        logger.warning("Failed to delete temp file %s: %s", path, e)


def _build_ingestion_pipeline():
    """
    Build and return an IngestionPipeline instance.

    Imports are done lazily to avoid circular imports when this module
    is loaded at app startup.
    """
    from app.infrastructure.chroma_vector_store import ChromaVectorStore
    from app.infrastructure.document_loader import JsonDocumentLoader
    from app.infrastructure.openrouter_embedding import OpenRouterEmbedding
    from app.infrastructure.text_splitter import LangChainTextSplitter
    from app.pipeline.ingestion import IngestionPipeline

    embedding = OpenRouterEmbedding()
    vector_store = ChromaVectorStore()
    document_loader = JsonDocumentLoader()
    text_splitter = LangChainTextSplitter()

    return IngestionPipeline(
        loader=document_loader,
        splitter=text_splitter,
        embedding=embedding,
        vector_store=vector_store,
    )


def run_job() -> bool:
    """
    Execute one fetch-and-ingest cycle.

    Returns:
        True if the job completed successfully, False otherwise.
    """
    temp_path: Path | None = None

    try:
        # 1. Fetch data from the external Scraper API
        auth = ScraperAuth()
        client = ScraperClient(auth)
        data = client.fetch_all()

        if not data:
            logger.info("No data returned from Scraper API, skipping ingest")
            log_last_fetch(total_documents=0, status="empty")
            return True

        # 2. Save to temp file
        temp_path = _save_to_temp_file(data)

        # 3. Ingest
        pipeline = _build_ingestion_pipeline()
        chunks_ingested = pipeline.run(str(temp_path))
        logger.info("Ingested %d chunks from %d documents", chunks_ingested, len(data))

        # 4. Log success
        log_last_fetch(total_documents=len(data), status="success")
        return True

    except (ScraperAuthError, ScraperClientError) as e:
        logger.error("Scraper API error: %s", str(e))
        log_last_fetch(total_documents=0, status="error", error_message=str(e))
        return False

    except Exception as e:
        logger.exception("Scheduler job failed: %s", str(e))
        log_last_fetch(total_documents=0, status="error", error_message=str(e))
        return False

    finally:
        # 5. Cleanup temp file
        if temp_path is not None:
            _delete_temp_file(temp_path)


def run_with_retry() -> None:
    """
    Run the job with exponential backoff retry logic.

    Retries up to max_retries times with increasing delay
    between attempts (60s, 120s, 240s, ...).
    """
    max_retries = scheduler_settings.max_retries
    base_delay = scheduler_settings.retry_delay_seconds
    backoff = scheduler_settings.retry_backoff_factor

    for attempt in range(max_retries + 1):
        if attempt > 0:
            delay = base_delay * (backoff ** (attempt - 1))
            logger.info(
                "Retrying scheduler job (attempt %d/%d) in %ds...",
                attempt + 1,
                max_retries + 1,
                delay,
            )
            time.sleep(delay)

        logger.info(
            "Scheduler job execution attempt %d/%d", attempt + 1, max_retries + 1
        )
        success = run_job()

        if success:
            logger.info("Scheduler job completed successfully")
            return

    logger.error(
        "Scheduler job failed after %d attempts, will retry on next schedule",
        max_retries + 1,
    )
