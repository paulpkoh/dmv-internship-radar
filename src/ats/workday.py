"""Workday tenants (myworkdayjobs.com).

Workday boards are large and paginated, so instead of pulling everything we
run a handful of targeted searches. The token is stored as "tenant|host|site",
for example "leidos|wd5|External".
"""

from __future__ import annotations

import json

from ..models import Company, Job
from .. import net
from ._common import iso, strip_html

SEARCH_TERMS = ("intern", "internship", "co-op", "student", "summer")
PAGE = 20
MAX_PAGES = 5


def parse_token(token: str) -> tuple[str, str, str] | None:
    parts = token.split("|")
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def _endpoint(tenant: str, host: str, site: str) -> str:
    return f"https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"


def _query(tenant: str, host: str, site: str, text: str, offset: int) -> dict | None:
    body = {"appliedFacets": {}, "limit": PAGE, "offset": offset, "searchText": text}
    r = net.post(
        _endpoint(tenant, host, site),
        data=json.dumps(body),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    if r is None or r.status_code != 200:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def probe(token: str) -> bool:
    parsed = parse_token(token)
    if not parsed:
        return False
    data = _query(*parsed, "intern", 0)
    return isinstance(data, dict) and "jobPostings" in data


def fetch(token: str, company: Company) -> list[Job]:
    parsed = parse_token(token)
    if not parsed:
        return []
    tenant, host, site = parsed
    base = f"https://{tenant}.{host}.myworkdayjobs.com/en-US/{site}"
    seen: set[str] = set()
    out: list[Job] = []

    for term in SEARCH_TERMS:
        offset = 0
        for _ in range(MAX_PAGES):
            data = _query(tenant, host, site, term, offset)
            if not isinstance(data, dict):
                break
            postings = data.get("jobPostings") or []
            if not postings:
                break
            for j in postings:
                if not isinstance(j, dict):
                    continue
                path = j.get("externalPath") or ""
                title = (j.get("title") or "").strip()
                if not title or not path or path in seen:
                    continue
                seen.add(path)
                bullets = j.get("bulletFields") or []
                out.append(
                    Job(
                        title=title,
                        company=company.name,
                        company_slug=company.slug,
                        location=j.get("locationsText") or "",
                        url=base + path,
                        source="workday",
                        posted_at=iso(j.get("startDate")),
                        description=strip_html(" ".join(str(b) for b in bullets)),
                        company_location=company.location,
                        company_tier=company.tier,
                    )
                )
            offset += PAGE
            if offset >= int(data.get("total") or 0):
                break
    return out
