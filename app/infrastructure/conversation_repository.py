"""
SQLite-backed Conversation Repository.

Implements the ConversationRepositoryPort interface using SQLite
for persistent storage of chat conversations.
"""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import List

from app.core.domain import Conversation, ConversationMessage
from app.core.ports import ConversationRepositoryPort

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/conversations.db")


class SQLiteConversationRepository(ConversationRepositoryPort):
    """
    Conversation repository backed by SQLite.

    Thread-safe via a reentrant lock. Creates the database and
    tables on first use if they do not exist.
    """

    def __init__(self, db_path: str | Path = _DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Create the database and tables if they do not exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New Conversation',
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()
        logger.info("Conversation database initialized at %s", self._db_path)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new SQLite connection (called within lock context)."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, conversation: Conversation) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                messages_json = json.dumps(
                    [
                        {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                        for m in conversation.messages
                    ],
                    ensure_ascii=False,
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO conversations
                        (id, title, messages, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        conversation.id,
                        conversation.title,
                        messages_json,
                        conversation.created_at,
                        conversation.updated_at,
                    ),
                )
                conn.commit()
                logger.debug("Saved conversation: %s", conversation.id)
            finally:
                conn.close()

    def get(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
                ).fetchone()
                return self._row_to_conversation(row) if row else None
            finally:
                conn.close()

    def list_all(self, limit: int = 50, offset: int = 0) -> list[Conversation]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
                return [self._row_to_conversation(r) for r in rows]
            finally:
                conn.close()

    def delete(self, conversation_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    "DELETE FROM conversations WHERE id = ?", (conversation_id,)
                )
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info("Deleted conversation: %s", conversation_id)
                return deleted
            finally:
                conn.close()

    def count(self) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM conversations"
                ).fetchone()
                return row["cnt"] if row else 0
            finally:
                conn.close()

    @staticmethod
    def _row_to_conversation(row: sqlite3.Row) -> Conversation:
        messages_data = json.loads(row["messages"]) if row["messages"] else []
        messages = [
            ConversationMessage(
                role=m["role"],
                content=m["content"],
                timestamp=m["timestamp"],
            )
            for m in messages_data
        ]
        return Conversation(
            id=row["id"],
            title=row["title"],
            messages=messages,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )