"""Configuration for paperlib. ALL values come from environment variables — never hardcode
API keys, emails, or personal identifiers in this file or anywhere else in the codebase."""

import os
from pathlib import Path

# --- Contact / politeness ---
# Used in polite User-Agent headers and Crossref/OpenAlex mailto params.
# If unset, we fall back to a generic string (no personal info baked in).
CONTACT_EMAIL = os.environ.get("UNPAYWALL_EMAIL") or os.environ.get("RESEARCH_CONTACT_EMAIL") or ""

USER_AGENT = (
    f"research-access-mcp/0.1 (https://github.com/sunsetsarge; mailto:{CONTACT_EMAIL})"
    if CONTACT_EMAIL
    else "research-access-mcp/0.1 (https://github.com/sunsetsarge)"
)

# --- API keys (all optional unless noted) ---
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")
CORE_API_KEY = os.environ.get("CORE_API_KEY", "")
SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "")

# Unpaywall REQUIRES an email. No default/fallback value is provided on purpose —
# callers must set this themselves. See paperlib.resolve for the refusal behavior.
UNPAYWALL_EMAIL = os.environ.get("UNPAYWALL_EMAIL", "")

# --- Storage locations ---
RESEARCH_PDF_DIR = Path(os.environ.get("RESEARCH_PDF_DIR", str(Path.home() / "Documents" / "Papers")))

_LOCALAPPDATA = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
APP_DATA_DIR = Path(_LOCALAPPDATA) / "research-access"
CACHE_DB_PATH = APP_DATA_DIR / "cache.db"
LOG_JSONL_PATH = APP_DATA_DIR / "log.jsonl"

# --- Cache TTLs (seconds) ---
CACHE_TTL_SEARCH = 7 * 24 * 3600
CACHE_TTL_DOI = 30 * 24 * 3600

# --- HTTP behavior ---
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


def ensure_dirs() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_PDF_DIR.mkdir(parents=True, exist_ok=True)


def unpaywall_configured() -> bool:
    return bool(UNPAYWALL_EMAIL)
