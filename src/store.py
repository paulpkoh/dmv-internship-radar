"""Persistence and change detection.

data/jobs.json is the memory of the system. Its only real job is to remember
when each posting was first seen, which is what makes the NEW badge possible
and what makes "actively updates" mean something.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import config
from .models import Company, Job

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JOBS_FILE = DATA / "jobs.json"
ATS_FILE = DATA / "ats.json"
COMPANIES_FILE = DATA / "companies.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text() or "null") or default
    except (ValueError, OSError) as exc:
        log.warning("Could not read %s: %s", path.name, exc)
        return default


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n")


# --------------------------------------------------------------------------
# ATS cache
# --------------------------------------------------------------------------

def load_ats() -> dict[str, dict]:
    return _read(ATS_FILE, {})


def save_ats(cache: dict[str, dict]) -> None:
    _write(ATS_FILE, dict(sorted(cache.items())))


# --------------------------------------------------------------------------
# Company list
# --------------------------------------------------------------------------

def load_companies() -> list[Company]:
    return [Company.from_dict(d) for d in _read(COMPANIES_FILE, [])]


def save_companies(companies: list[Company]) -> None:
    _write(COMPANIES_FILE, [c.to_dict() for c in companies])


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

def load_jobs() -> tuple[list[Job], list[dict]]:
    blob = _read(JOBS_FILE, {})
    if isinstance(blob, list):  # tolerate an older flat format
        return [Job.from_dict(d) for d in blob], []
    jobs = [Job.from_dict(d) for d in blob.get("jobs", [])]
    return jobs, blob.get("history", [])


def merge(previous: list[Job], scraped: list[Job]) -> tuple[list[Job], list[Job], list[Job]]:
    """Fold a fresh scrape into the stored set.

    Returns (current, newly_added, disappeared).
    """
    now = _now()
    today = datetime.now(timezone.utc)
    by_id = {j.id: j for j in previous}

    current: list[Job] = []
    added: list[Job] = []
    scraped_ids: set[str] = set()

    for job in scraped:
        scraped_ids.add(job.id)
        old = by_id.get(job.id)
        if old is None:
            job.first_seen = now
            job.last_seen = now
            added.append(job)
        else:
            job.first_seen = old.first_seen or now
            job.last_seen = now
        current.append(job)

    disappeared: list[Job] = []
    for job in previous:
        if job.id in scraped_ids:
            continue
        # Keep a vanished posting around briefly: boards flake, and a role
        # that 404s for one run is often back on the next.
        try:
            last = datetime.fromisoformat(job.last_seen)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            last = today
        if today - last < timedelta(days=config.STALE_AFTER_DAYS):
            current.append(job)
        else:
            disappeared.append(job)

    current.sort(key=lambda j: (-j.relevance, j.company.lower(), j.title.lower()))
    return current, added, disappeared


def is_new(job: Job, window_days: int = config.NEW_WINDOW_DAYS) -> bool:
    try:
        first = datetime.fromisoformat(job.first_seen)
    except (ValueError, TypeError):
        return False
    if first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - first < timedelta(days=window_days)


def save_jobs(jobs: list[Job], history: list[dict], stats: dict) -> None:
    entry = {"at": _now(), **stats}
    history = (history + [entry])[-120:]
    _write(JOBS_FILE, {"generated_at": _now(), "stats": stats, "history": history,
                       "jobs": [j.to_dict() for j in jobs]})
