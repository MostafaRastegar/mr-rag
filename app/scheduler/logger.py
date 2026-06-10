"""
Scheduler logging module.

Keeps track of the last successful fetch: timestamp, total documents, and status.
The log is stored as a JSON file for easy inspection.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.scheduler.config import scheduler_settings

logger = logging.getLogger(__name__)


def log_last_fetch(
    total_documents: int,
    status: str = "success",
    error_message: Optional[str] = None,
) -> None:
    """
    Write a log entry for the last fetch attempt.

    Args:
        total_documents: Number of documents fetched.
        status: "success" or "error".
        error_message: Error details if status is "error".
    """
    log_path = Path(scheduler_settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry: Dict[str, Any] = {
        "last_fetch": datetime.now(timezone.utc).isoformat(),
        "total_documents": total_documents,
        "status": status,
    }
    if error_message:
        entry["error_message"] = error_message

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
        logger.info(
            "Scheduler log updated: status=%s, total=%d", status, total_documents
        )
    except OSError as e:
        logger.error("Failed to write scheduler log: %s", e)


def read_last_fetch() -> Optional[Dict[str, Any]]:
    """
    Read the last fetch log entry.

    Returns:
        The log dict if the file exists and is valid JSON, otherwise None.
    """
    log_path = Path(scheduler_settings.log_file)
    if not log_path.exists():
        return None

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read scheduler log: %s", e)
        return None
