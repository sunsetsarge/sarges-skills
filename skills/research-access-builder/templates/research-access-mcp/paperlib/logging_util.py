"""Structured JSONL logging for paperlib operations."""

import json
import time
from typing import Any

from . import config


def log_operation(op: str, **fields: Any) -> None:
    """Append one JSON record to the log file. Never raises — logging failures
    must not break the calling operation."""
    try:
        config.ensure_dirs()
        record = {"ts": time.time(), "op": op}
        record.update(fields)
        with open(config.LOG_JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


def read_log_tail(n: int = 20) -> list:
    """Read the last n log records. Used by tests to verify cache-hit behavior."""
    try:
        with open(config.LOG_JSONL_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out
    except FileNotFoundError:
        return []
