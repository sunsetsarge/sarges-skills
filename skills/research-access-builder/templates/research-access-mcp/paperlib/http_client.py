"""Shared HTTP client wrapper: per-host rate limiting, retries with backoff+jitter,
per-source timeout, polite User-Agent."""

import random
import threading
import time
from urllib.parse import urlparse

import httpx

from . import config

# Minimum interval (seconds) between requests to a given host. Conservative by design.
_MIN_INTERVAL_BY_HOST = {
    "api.openalex.org": 0.15,
    "api.crossref.org": 0.4,
    "api.semanticscholar.org": 1.0,
    "api.unpaywall.org": 0.2,
    "api.core.ac.uk": 2.0,
    "export.arxiv.org": 3.0,
    "arxiv.org": 1.0,
    "www.ebi.ac.uk": 1.0,
}
_DEFAULT_MIN_INTERVAL = 0.3

_last_request_time = {}
_rate_lock = threading.Lock()


def _host_of(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def _respect_rate_limit(host: str) -> None:
    min_interval = _MIN_INTERVAL_BY_HOST.get(host, _DEFAULT_MIN_INTERVAL)
    with _rate_lock:
        last = _last_request_time.get(host, 0.0)
        now = time.monotonic()
        wait = (last + min_interval) - now
        if wait > 0:
            time.sleep(wait)
        _last_request_time[host] = time.monotonic()


def request(
    method: str,
    url: str,
    *,
    params: dict = None,
    headers: dict = None,
    timeout: float = None,
    max_retries: int = None,
    follow_redirects: bool = True,
) -> httpx.Response:
    """Make an HTTP request with rate limiting + retry/backoff. Raises httpx exceptions
    on final failure — callers are expected to catch and convert to soft-fail dicts."""
    host = _host_of(url)
    timeout = timeout if timeout is not None else config.DEFAULT_TIMEOUT
    max_retries = max_retries if max_retries is not None else config.MAX_RETRIES

    hdrs = {"User-Agent": config.USER_AGENT}
    if headers:
        hdrs.update(headers)

    last_exc = None
    for attempt in range(max_retries + 1):
        _respect_rate_limit(host)
        try:
            with httpx.Client(timeout=timeout, follow_redirects=follow_redirects) as client:
                resp = client.request(method, url, params=params, headers=hdrs)
            if resp.status_code == 429:
                if attempt < max_retries:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = (2 ** attempt) + random.uniform(0, 1)
                    else:
                        delay = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(delay)
                    continue
                return resp
            if resp.status_code >= 500 and attempt < max_retries:
                delay = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
                continue
            return resp
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError(f"request() exhausted retries without a response for {url}")


def get(url: str, **kwargs) -> httpx.Response:
    return request("GET", url, **kwargs)


def head(url: str, **kwargs) -> httpx.Response:
    return request("HEAD", url, **kwargs)
