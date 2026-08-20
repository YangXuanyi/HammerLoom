from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class Store:
    """Small SQLite document store with explicit entity collections."""

    TABLES = ("runs", "skills", "versions", "candidates", "decisions", "settings")

    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # FastAPI serves synchronous routes through a worker thread.
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        for table in self.TABLES:
            self.connection.execute(
                f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
        self.connection.commit()

    def put(self, table: str, entity: Dict[str, Any]) -> None:
        self.connection.execute(
            f"INSERT INTO {table} (id, payload) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
            (entity["id"], json.dumps(entity, ensure_ascii=False)),
        )
        self.connection.commit()

    def get(self, table: str, entity_id: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(f"SELECT payload FROM {table} WHERE id=?", (entity_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def all(self, table: str) -> List[Dict[str, Any]]:
        rows = self.connection.execute(f"SELECT payload FROM {table}").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def close(self) -> None:
        self.connection.close()
