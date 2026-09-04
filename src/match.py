"""Decides whether a posting is close enough, junior enough, and relevant.

Three independent gates, in order of how cheap they are to evaluate:

    1. location  - is it in the DMV commute radius, or genuinely US-remote?
    2. category  - is it an internship/co-op or a part-time research role?
    3. relevance - does it touch AI/ML, data, software or computational bio?

Each gate is a pure function so the whole thing is testable without network.
"""

from __future__ import annotations

import re
from typing import Iterable

from . import config
from .models import Job

# --------------------------------------------------------------------------
# Location
# --------------------------------------------------------------------------

_STATE_WORDS = {
    "maryland": "MD", "md": "MD",
    "virginia": "VA", "va": "VA",
    "district of columbia": "DC", "washington dc": "DC", "dc": "DC",
    "d.c.": "DC", "washington, d.c.": "DC",
    "delaware": "DE", "de": "DE",
}

_SPLIT_RE = re.compile(r"\s*(?:\||;|/| or | and |&|\bor\b)\s*|\s{2,}")
_METRO_HINTS = ("dmv", "dc metro", "washington metro", "national capital",
                "baltimore metro", "greater washington", "greater baltimore",
                "capital region", "mid-atlantic")


def _normalize(text: str) -> str:
    t = (text or "").lower()
    t = t.replace("–", "-").replace("—", "-").replace("\xa0", " ")
    t = re.sub(r"\bd\.?\s*c\.?\b", "dc", t)
    t = re.sub(r"[^a-z0-9,.\-' ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_remote(text: str) -> bool:
    t = _normalize(text)
    return any(p in t for p in config.REMOTE_PATTERNS)


def _remote_is_us(text: str) -> bool:
    t = _normalize(text)
    return not any(h in t for h in config.REMOTE_REJECT_HINTS)


def _segment_state(seg: str) -> str:
    """Pull a two-letter state out of one location segment."""
    m = re.search(r",\s*([a-z]{2})\b", seg)
    if m and m.group(1) in {"md", "va", "dc", "de"}:
        return m.group(1).upper()
    for word, code in _STATE_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", seg):
            return code
    return ""


def _segment_in_scope(seg: str) -> bool:
    seg = seg.strip().strip(",.")
    if not seg:
        return False
    if any(far in seg for far in config.FAR_LOCALITIES):
        return False
    if any(h in seg for h in _METRO_HINTS):
        return True

    state = _segment_state(seg)
    if state and state not in config.IN_SCOPE_STATES:
        return False

    if state == "DC" or re.search(r"\bwashington\b", seg) and state != "VA":
        # "Washington, DC" is in; "Washington state" is not.
        if not re.search(r"\bwashington state\b|\bseattle\b|\bredmond\b|\bwa\b", seg):
            return True

    cities = config.MD_CITIES if state == "MD" else config.VA_CITIES if state == "VA" else None
    if cities is not None:
        return any(re.search(rf"\b{re.escape(city)}\b", seg) for city in cities)

    # No state given: accept only if a locality name is unambiguous.
    if not state:
        for city in config.MD_CITIES | config.VA_CITIES:
            if len(city) > 5 and re.search(rf"\b{re.escape(city)}\b", seg):
                return True
    return False


def location_status(raw: str) -> str:
    """Return 'in_scope', 'remote', 'out' or 'unknown'."""
    if not raw or not raw.strip():
        return "unknown"
    text = _normalize(raw)
    segments = [s for s in _SPLIT_RE.split(text) if s.strip()] or [text]

    if any(_segment_in_scope(s) for s in segments):
        return "in_scope"
    if is_remote(text):
        return "remote" if _remote_is_us(text) else "out"
    return "out"


# --------------------------------------------------------------------------
# Category
# --------------------------------------------------------------------------

_INTERN_RE = re.compile("|".join(config.INTERNSHIP_PATTERNS), re.I)
_PARTTIME_RE = re.compile("|".join(config.PART_TIME_PATTERNS), re.I)
_BLOCK_RE = re.compile("|".join(config.SENIORITY_BLOCKLIST), re.I)


def category(title: str, description: str = "") -> str:
    """Return 'internship', 'part_time_research' or '' (not a fit)."""
    t = " " + (title or "").lower().strip() + " "
    d = (description or "").lower()

    title_intern = bool(_INTERN_RE.search(t))
    title_parttime = bool(_PARTTIME_RE.search(t))

    # "Internal Medicine" and "International" must not read as "intern".
    if title_intern and _BLOCK_RE.search(t) and not re.search(r"\bintern(ship)?s?\b|\bco-?op\b", t):
        title_intern = False
    if _BLOCK_RE.search(t) and not (title_intern or title_parttime):
        return ""

    if title_intern:
        return "internship"
    if title_parttime:
        return "part_time_research"

    # Title is silent; fall back to a strong statement in the description.
    if re.search(r"\b(this is an? |summer )?internship\b|\bco-?op (position|program|student)\b", d):
        if not _BLOCK_RE.search(t):
            return "internship"
    return ""


# --------------------------------------------------------------------------
# Relevance
# --------------------------------------------------------------------------

def relevance(title: str, description: str = "") -> tuple[int, list[str]]:
    """Weighted keyword score. Title matches count double."""
    t = f" {(title or '').lower()} "
    d = f" {(description or '').lower()} "
    score = 0
    hits: list[str] = []
    for keyword, weight in config.RELEVANCE_KEYWORDS.items():
        in_title = keyword in t
        in_desc = keyword in d
        if not (in_title or in_desc):
            continue
        score += weight * 2 if in_title else weight
        hits.append(keyword.strip())
    return score, hits


_TITLE_RESCUE_RE = re.compile("|".join(config.TITLE_RESCUE_PATTERNS), re.I)


def title_is_technical(title: str) -> bool:
    return bool(_TITLE_RESCUE_RE.search(title or ""))


# --------------------------------------------------------------------------
# The whole pipeline for one job
# --------------------------------------------------------------------------

def evaluate(job: Job) -> Job | None:
    """Annotate and return the job, or None if it should be dropped."""
    status = location_status(job.location)
    if status == "unknown":
        # Boards that omit location: fall back to where the company sits.
        status = location_status(job.company_location) or "out"
        if status == "unknown":
            status = "out"
    if status == "out":
        return None
    job.remote = job.remote or status == "remote"

    cat = category(job.title, job.description)
    if cat not in config.ENABLED_CATEGORIES:
        return None
    job.category = cat

    score, hits = relevance(job.title, job.description)
    # A thin description should not sink an obviously technical title.
    if score < config.MIN_RELEVANCE and title_is_technical(job.title) and len(job.description) < 200:
        score = config.MIN_RELEVANCE
        hits = hits or ["technical title"]
    if score < config.MIN_RELEVANCE:
        return None

    job.relevance = score
    job.matched_keywords = sorted(set(hits))[:12]
    return job


def evaluate_all(jobs: Iterable[Job]) -> list[Job]:
    out: list[Job] = []
    seen: set[str] = set()
    for job in jobs:
        kept = evaluate(job)
        if kept is None or kept.id in seen:
            continue
        seen.add(kept.id)
        out.append(kept)
    out.sort(key=lambda j: (-j.relevance, j.company.lower(), j.title.lower()))
    return out
