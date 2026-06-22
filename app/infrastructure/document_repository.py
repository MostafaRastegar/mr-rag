"""
SQLite-backed Document Metadata Repository.

Implements the DocumentRepositoryPort interface using SQLite
for persistent storage of document metadata records.
"""

import logging
import sqlite3
import threading
from pathlib import Path

from app.core.domain import DocumentInfo
from app.core.ports import DocumentRepositoryPort

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/document_metadata.db")


class SQLiteDocumentRepository(DocumentRepositoryPort):
    """
    Document metadata repository backed by SQLite.

    Thread-safe via a reentrant lock. Creates the database and
    table on first use if they do not exist.
    """

    def __init__(self, db_path: str | Path = _DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Create the database and table if they do not exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    ingested_at REAL NOT NULL
                )
            """)
            conn.commit()
        logger.info("Document metadata database initialized at %s", self._db_path)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new SQLite connection (called within lock context)."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, doc: DocumentInfo) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO documents
                        (id, filename, source_path, file_type, chunk_count, ingested_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc.id,
                        doc.filename,
                        doc.source_path,
                        doc.file_type,
                        doc.chunk_count,
                        doc.ingested_at,
                    ),
                )
                conn.commit()
                logger.debug("Saved document metadata: %s", doc.id)
            finally:
                conn.close()

    def get(self, doc_id: str) -> DocumentInfo | None:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT * FROM documents WHERE id = ?", (doc_id,)
                ).fetchone()
                return self._row_to_doc(row) if row else None
            finally:
                conn.close()

    def list_all(self) -> list[DocumentInfo]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY ingested_at DESC"
                ).fetchall()
                return [self._row_to_doc(r) for r in rows]
            finally:
                conn.close()

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info("Deleted document metadata: %s", doc_id)
                return deleted
            finally:
                conn.close()

    def count(self) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT COUNT(*) AS cnt FROM documents").fetchone()
                return row["cnt"] if row else 0
            finally:
                conn.close()

    @staticmethod
    def _row_to_doc(row: sqlite3.Row) -> DocumentInfo:
        return DocumentInfo(
            id=row["id"],
            filename=row["filename"],
            source_path=row["source_path"],
            file_type=row["file_type"],
            chunk_count=row["chunk_count"],
            ingested_at=row["ingested_at"],
        )