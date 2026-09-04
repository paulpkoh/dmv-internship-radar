"""Rippling ATS public board."""

from __future__ import annotations

from ..models import Company, Job
from .. import net
from ._common import iso, strip_html

API = "https://api.rippling.com/platform/api/ats/v1/board/{token}/jobs"


def probe(token: str) -> bool:
    return isinstance(net.get_json(API.format(token=token)), list)


def fetch(token: str, company: Company) -> list[Job]:
    data = net.get_json(API.format(token=token))
    if not isinstance(data, list):
        return []
    out: list[Job] = []
    for j in data:
        if not isinstance(j, dict):
            continue
        title = (j.get("name") or j.get("title") or "").strip()
        url = j.get("url") or j.get("jobUrl") or ""
        if not title or not url:
            continue
        loc = j.get("workLocation") or {}
        location = loc.get("label") if isinstance(loc, dict) else str(loc or "")
        out.append(
            Job(
                title=title,
                company=company.name,
                company_slug=company.slug,
                location=location or "",
                url=url,
                source="rippling",
                posted_at=iso(j.get("createdAt")),
                description=strip_html(j.get("description")),
                department=j.get("department") or "",
                company_location=company.location,
                company_tier=company.tier,
            )
        )
    return out
