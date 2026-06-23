"""
Cleanup orphaned chunks from ChromaDB.

Finds chunks whose original_filename does not match any document in the
SQLite document repository and removes them.

Usage:
    python -m scripts.cleanup_orphans [--dry-run]
"""

import argparse
import logging
import sys

from app.config import settings
from app.infrastructure.chroma_vector_store import ChromaVectorStore
from app.infrastructure.document_repository import SQLiteDocumentRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cleanup orphaned chunks from ChromaDB"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report orphans without deleting them",
    )
    args = parser.parse_args()

    vector_store = ChromaVectorStore()
    doc_repo = SQLiteDocumentRepository()

    # Collect known original_filenames from document metadata
    docs = doc_repo.list_all()
    known_filenames: set[str] = {d.original_filename for d in docs}
    logger.info("Found %d documents in SQLite", len(docs))

    # Get all chunks from vector store
    chunks = vector_store.get_all_chunks()
    logger.info("Found %d chunks in ChromaDB", len(chunks))

    # Find orphans
    orphans = [
        c
        for c in chunks
        if c.metadata.get("original_filename") not in known_filenames
    ]

    if not orphans:
        logger.info("No orphan chunks found. All clean!")
        return

    logger.info(
        "Found %d orphan chunk(s) (%.1f%% of total)",
        len(orphans),
        100.0 * len(orphans) / len(chunks) if chunks else 0,
    )

    # Show orphan details
    for c in orphans:
        orig = c.metadata.get("original_filename", "?")
        src = c.metadata.get("source_path", "?")
        logger.info(
            "  Orphan chunk: id=%s  original_filename=%s  source_path=%s  text=%s",
            c.id,
            orig,
            src,
            c.text[:80],
        )

    if args.dry_run:
        logger.info("Dry-run mode: no chunks were deleted")
        return

    # Delete orphans
    orphan_ids = [c.id for c in orphans]
    vector_store.delete(orphan_ids)
    logger.info("Deleted %d orphan chunk(s) from ChromaDB", len(orphan_ids))


if __name__ == "__main__":
    main()
