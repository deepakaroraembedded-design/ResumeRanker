from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from pathlib import Path


class Cache:
    """SQLite-backed response cache for LLM calls.

    The cache is keyed by a caller-provided string (typically a SHA-256 digest
    of the model, template version and rendered prompt). SQLite is used so the
    cache survives process restarts and is safe for concurrent access from a
    single event loop via an async lock.

    Attributes:
        path: Path to the SQLite database file.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._init_db()

    def key(
        self,
        *,
        model_id: str,
        template_version: str,
        prompt: str,
        sample_index: int,
    ) -> str:
        """Compute a SHA-256 cache key from the call inputs.

        TRD §6.3 requires the cache key to depend on the model id, template
        version and rendered prompt.  The sample index is included so that
        multiple samples for the same prompt are stored independently, as
        required by the C-05 implementation notes.

        Args:
            model_id: Model identifier.
            template_version: Template name and version, e.g. ``"E-PARSE-v1"``.
            prompt: Rendered prompt text (canonicalized by the caller).
            sample_index: Zero-based sample index.

        Returns:
            A 64-character hex digest.
        """
        hasher = hashlib.sha256()
        hasher.update(model_id.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(template_version.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(prompt.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(str(sample_index).encode("utf-8"))
        return hasher.hexdigest()

    def _init_db(self) -> None:
        """Create the cache table if it does not exist."""
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_cache (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.commit()

    async def get(self, key: str) -> bytes | None:
        """Return the cached value for *key*, or ``None`` if missing.

        Args:
            key: Cache key.

        Returns:
            The cached bytes, or ``None``.
        """
        async with self._lock:
            return await asyncio.to_thread(self.get_sync, key)

    def get_sync(self, key: str) -> bytes | None:
        """Synchronous version of :meth:`get`."""
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute("SELECT value FROM llm_cache WHERE key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row else None

    async def put(self, key: str, value: bytes) -> None:
        """Store *value* under *key*.

        Args:
            key: Cache key.
            value: Raw response bytes.
        """
        async with self._lock:
            await asyncio.to_thread(self.put_sync, key, value)

    def put_sync(self, key: str, value: bytes) -> None:
        """Synchronous version of :meth:`put`."""
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO llm_cache (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    async def clear(self) -> None:
        """Remove all entries from the cache."""
        async with self._lock:
            await asyncio.to_thread(self.clear_sync)

    def clear_sync(self) -> None:
        """Synchronous version of :meth:`clear`."""
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM llm_cache")
            conn.commit()

    def __len__(self) -> int:
        """Return the number of cached entries."""
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM llm_cache")
            row = cur.fetchone()
            return int(row[0]) if row else 0
