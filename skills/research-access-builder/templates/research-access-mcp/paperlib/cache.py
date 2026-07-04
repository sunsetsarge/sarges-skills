"""SQLite-backed cache for paperlib. Keyed by normalized (kind, key, source) with TTL."""

import hashlib
import json
import sqlite3
import threading
import time
from typing import Optional

from . import config

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.ensure_dirs()
        _conn = sqlite3.connect(str(config.CACHE_DB_PATH), check_same_thread=False)
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                kind TEXT,
                payload TEXT,
                created_at REAL,
                expires_at REAL
            )
            """
        )
        _conn.commit()
    return _conn


def _make_key(kind: str, key: str, source: str = "") -> str:
    raw = f"{kind}|{source}|{key.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(kind: str, key: str, source: str = "") -> Optional[dict]:
    """Return cached payload dict if present and not expired, else None."""
    try:
        with _lock:
            conn = _get_conn()
            cache_key = _make_key(kind, key, source)
            row = conn.execute(
                "SELECT payload, expires_at FROM cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
            if row is None:
                return None
            payload_str, expires_at = row
            if expires_at is not None and time.time() > expires_at:
                return None
            return json.loads(payload_str)
    except Exception:
        return None


def set(kind: str, key: str, payload: dict, ttl_seconds: float, source: str = "") -> None:
    try:
        with _lock:
            conn = _get_conn()
            cache_key = _make_key(kind, key, source)
            now = time.time()
            conn.execute(
                """
                INSERT INTO cache (cache_key, kind, payload, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload=excluded.payload,
                    created_at=excluded.created_at,
                    expires_at=excluded.expires_at
                """,
                (cache_key, kind, json.dumps(payload, default=str), now, now + ttl_seconds),
            )
            conn.commit()
    except Exception:
        pass


def was_hit(kind: str, key: str, source: str = "") -> bool:
    """Convenience check used by tests: is there a live (non-expired) entry?"""
    return get(kind, key, source) is not None
