"""Shared HTTP plumbing: a retrying session and a small thread-pool helper."""

from __future__ import annotations

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

log = logging.getLogger(__name__)

_RETRY = Retry(
    total=2,
    connect=2,
    read=2,
    backoff_factor=0.6,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET", "POST"]),
    raise_on_status=False,
)


def make_session() -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(max_retries=_RETRY, pool_connections=32, pool_maxsize=32)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(
        {
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/json,application/xhtml+xml,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return s


SESSION = make_session()


def get(url: str, **kw: Any) -> requests.Response | None:
    """GET that never raises. Returns None on any transport-level failure."""
    kw.setdefault("timeout", config.REQUEST_TIMEOUT)
    kw.setdefault("allow_redirects", True)
    try:
        return SESSION.get(url, **kw)
    except Exception as exc:  # noqa: BLE001 - the whole point is to not raise
        log.debug("GET %s failed: %s", url, exc)
        return None


def post(url: str, **kw: Any) -> requests.Response | None:
    kw.setdefault("timeout", config.REQUEST_TIMEOUT)
    try:
        return SESSION.post(url, **kw)
    except Exception as exc:  # noqa: BLE001
        log.debug("POST %s failed: %s", url, exc)
        return None


def get_json(url: str, **kw: Any) -> Any | None:
    r = get(url, **kw)
    if r is None or r.status_code != 200:
        return None
    ctype = r.headers.get("content-type", "")
    if "json" not in ctype and not r.text.lstrip()[:1] in ("{", "["):
        return None
    try:
        return r.json()
    except ValueError:
        return None


def get_text(url: str, **kw: Any) -> str | None:
    r = get(url, **kw)
    if r is None or r.status_code != 200:
        return None
    ctype = r.headers.get("content-type", "")
    if ctype and "html" not in ctype and "text" not in ctype and "json" not in ctype:
        return None
    # Cap absurd pages so one bad site can't eat all the memory.
    return r.text[:1_500_000]


def parallel(
    fn: Callable[[Any], Any],
    items: Sequence[Any],
    workers: int | None = None,
    label: str = "",
    jitter: float = 0.0,
) -> list[Any]:
    """Run fn over items concurrently, collecting non-None results.

    Failures in fn are logged and skipped rather than aborting the batch.
    """
    workers = workers or config.MAX_WORKERS
    results: list[Any] = []
    total = len(items)
    done = 0

    def wrapped(item: Any) -> Any:
        if jitter:
            time.sleep(random.uniform(0, jitter))
        try:
            return fn(item)
        except Exception as exc:  # noqa: BLE001
            log.debug("%s worker failed on %r: %s", label, item, exc)
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(wrapped, it): it for it in items}
        for fut in as_completed(futures):
            done += 1
            if label and (done % 25 == 0 or done == total):
                log.info("%s: %d/%d", label, done, total)
            res = fut.result()
            if res is not None:
                results.append(res)
    return results


def flatten(chunks: Iterable[Iterable[Any]]) -> list[Any]:
    out: list[Any] = []
    for c in chunks:
        if c:
            out.extend(c)
    return out
