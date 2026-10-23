import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = Path("history.db")


class HistoryDatabase:
    """Stores and retrieves transcription history using local SQLite."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    duration_seconds REAL DEFAULT 0.0,
                    text TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    source TEXT DEFAULT 'dictation',
                    file_name TEXT
                )
                """
            )
            conn.commit()

    def save_record(
        self,
        text: str,
        duration_seconds: float = 0.0,
        model_used: str = "base.en",
        source: str = "dictation",
        file_name: Optional[str] = None,
    ) -> int:
        """Saves a transcription record to history and returns record id."""
        if not text.strip():
            return -1

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transcriptions (timestamp, duration_seconds, text, model_used, source, file_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now, duration_seconds, text.strip(), model_used, source, file_name),
            )
            conn.commit()
            return cursor.lastrowid

    def get_recent(self, limit: int = 100) -> List[Dict]:
        """Fetches the most recent transcriptions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, duration_seconds, text, model_used, source, file_name
                FROM transcriptions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def search(self, query: str, limit: int = 50) -> List[Dict]:
        """Searches past transcriptions matching query."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, duration_seconds, text, model_used, source, file_name
                FROM transcriptions
                WHERE text LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (f"%{query}%", limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete(self, record_id: int) -> bool:
        """Deletes a record by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transcriptions WHERE id = ?", (record_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all(self) -> None:
        """Clears all records."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM transcriptions")
            conn.commit()
