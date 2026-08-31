from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


class ContentAddressedCache:
    """Shared content-addressed cache backed by SQLite.

    Keys are SHA-256 hashes of the cached content.  Values are stored as JSON.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(".ats-cache/cache.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def _key(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def get(self, content: bytes) -> Any | None:
        """Return the cached value for *content* or None."""
        key = self._key(content)
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def put(self, content: bytes, value: Any) -> None:
        """Store *value* for *content*."""
        key = self._key(content)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (key, json.dumps(value, default=str)),
            )
