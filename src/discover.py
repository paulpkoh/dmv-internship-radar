"""Works out which job board, if any, each company actually uses.

For every company we fetch the homepage, follow anything that looks like a
careers link, and scan the resulting HTML for the fingerprints of the common
applicant tracking systems. Every candidate is then validated against the live
API before being cached, so a bad guess never reaches the fetch stage.

Results are cached in data/ats.json and refreshed every DISCOVERY_TTL_DAYS.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from . import config, net
from .ats import REGISTRY
from .models import Company

log = logging.getLogger(__name__)

_CAREERS_LINK_RE = re.compile(r"career|jobs?\b|join[- ]us|opportunit|employment|work[- ]with", re.I)

# Board tokens that are actually URL furniture rather than a company handle.
_RESERVED = {
    "embed", "boards", "job_board", "jobs", "careers", "api", "v0", "v1",
    "postings", "www", "en-us", "en", "search", "apply", "j",
}

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_.-]+)", re.I)),
    ("greenhouse", re.compile(r"greenhouse\.io/embed/job_board\?for=([A-Za-z0-9_.-]+)", re.I)),
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/([A-Za-z0-9_.-]+)", re.I)),
    ("lever", re.compile(r"api\.lever\.co/v0/postings/([A-Za-z0-9_.-]+)", re.I)),
    ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.-]+)", re.I)),
    ("ashby", re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([A-Za-z0-9_.-]+)", re.I)),
    ("smartrecruiters", re.compile(r"api\.smartrecruiters\.com/v1/companies/([A-Za-z0-9_-]+)", re.I)),
    ("smartrecruiters", re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/([A-Za-z0-9_-]+)", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/(?:api/v1/widget/accounts/)?([A-Za-z0-9_-]+)", re.I)),
    ("recruitee", re.compile(r"([A-Za-z0-9_-]+)\.recruitee\.com", re.I)),
    ("bamboohr", re.compile(r"([A-Za-z0-9_-]+)\.bamboohr\.com/(?:careers|jobs)", re.I)),
    ("rippling", re.compile(r"ats\.rippling\.com/([A-Za-z0-9_-]+)", re.I)),
    ("workday", re.compile(
        r"([A-Za-z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)", re.I)),
]


def _candidate_urls(domain: str) -> list[str]:
    if not domain:
        return []
    base = f"https://{domain}"
    urls = [base]
    urls += [base + p for p in config.CAREERS_PATHS[:6]]
    return urls


def _extract(html: str) -> list[tuple[str, str]]:
    """Return (source, token) candidates found in a blob of HTML."""
    found: list[tuple[str, str]] = []
    for source, pattern in _PATTERNS:
        for m in pattern.finditer(html):
            if source == "workday":
                tenant, host, site = m.group(1), m.group(2), m.group(3)
                if tenant.lower() in _RESERVED:
                    continue
                token = f"{tenant}|{host.lower()}|{site}"
            else:
                token = m.group(1)
                if token.lower() in _RESERVED or len(token) < 2:
                    continue
            pair = (source, token)
            if pair not in found:
                found.append(pair)
    return found


def _careers_links(html: str, page_url: str, domain: str) -> list[str]:
    out: list[str] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:  # noqa: BLE001
        return out
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip()
        href = a["href"]
        if not _CAREERS_LINK_RE.search(text) and not _CAREERS_LINK_RE.search(href):
            continue
        url = urljoin(page_url, href)
        host = urlparse(url).netloc.lower().replace("www.", "")
        # Follow same-site careers pages, and any off-site link (it is probably
        # the ATS itself, which _extract will pick up from the URL).
        if host and (host == domain or domain in host or any(
            k in host for k in ("greenhouse", "lever", "ashby", "workday", "smartrecruiters",
                                "workable", "recruitee", "bamboohr", "rippling", "icims")
        )):
            if url not in out:
                out.append(url)
    return out[:5]


def discover_company(company: Company) -> dict | None:
    """Find and validate a board for one company."""
    domain = company.domain
    if not domain:
        return None

    html_blobs: list[str] = []
    careers_url = ""
    followed: list[str] = []

    for url in _candidate_urls(domain):
        html = net.get_text(url)
        if not html:
            continue
        html_blobs.append(html)
        if url.rstrip("/") != f"https://{domain}":
            careers_url = careers_url or url
        else:
            followed = _careers_links(html, url, domain)
        # An early hit means we can stop crawling this site.
        if _extract(html):
            break

    for url in followed[:3]:
        if any(url in b for b in html_blobs):
            continue
        html = net.get_text(url)
        if html:
            html_blobs.append(html)
            careers_url = careers_url or url
            if _extract(html):
                break

    if not html_blobs:
        return None

    candidates: list[tuple[str, str]] = []
    for blob in html_blobs:
        for pair in _extract(blob):
            if pair not in candidates:
                candidates.append(pair)

    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for source, token in candidates[:6]:
        module = REGISTRY.get(source)
        if module is None:
            continue
        try:
            if module.probe(token):
                log.info("%s -> %s:%s", company.name, source, token)
                return {
                    "slug": company.slug,
                    "name": company.name,
                    "domain": domain,
                    "source": source,
                    "token": token,
                    "careers_url": careers_url,
                    "checked_at": checked_at,
                }
        except Exception as exc:  # noqa: BLE001
            log.debug("probe %s:%s failed: %s", source, token, exc)

    # No ATS, but remember where the careers page is for the HTML fallback.
    if careers_url:
        return {
            "slug": company.slug,
            "name": company.name,
            "domain": domain,
            "source": "html",
            "token": "",
            "careers_url": careers_url,
            "checked_at": checked_at,
        }
    return None


def is_fresh(record: dict, ttl_days: int = config.DISCOVERY_TTL_DAYS) -> bool:
    stamp = record.get("checked_at")
    if not stamp:
        return False
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - when < timedelta(days=ttl_days)


def discover(companies: list[Company], cache: dict[str, dict], force: bool = False) -> dict[str, dict]:
    """Refresh the ATS cache, keeping still-fresh entries untouched."""
    todo = [c for c in companies if force or not is_fresh(cache.get(c.slug, {}))]
    log.info("Discovery: %d companies to check (%d cached)", len(todo), len(companies) - len(todo))

    results = net.parallel(
        discover_company, todo, workers=config.DISCOVERY_MAX_WORKERS, label="discovery", jitter=0.3
    )
    for rec in results:
        cache[rec["slug"]] = rec

    # Companies we checked and found nothing for get a tombstone so we do not
    # re-crawl them every single run.
    found = {r["slug"] for r in results}
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for c in todo:
        if c.slug not in found:
            cache[c.slug] = {
                "slug": c.slug, "name": c.name, "domain": c.domain,
                "source": "none", "token": "", "careers_url": "", "checked_at": stamp,
            }
    return cache
