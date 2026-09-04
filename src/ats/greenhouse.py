"""Greenhouse job boards (boards-api.greenhouse.io)."""

from __future__ import annotations

from ..models import Company, Job
from .. import net
from ._common import iso, strip_html

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def probe(token: str) -> bool:
    data = net.get_json(API.format(token=token))
    return bool(data) and isinstance(data, dict) and "jobs" in data


def fetch(token: str, company: Company) -> list[Job]:
    data = net.get_json(API.format(token=token) + "?content=true")
    if not isinstance(data, dict):
        return []
    out: list[Job] = []
    for j in data.get("jobs") or []:
        if not isinstance(j, dict):
            continue
        title = (j.get("title") or "").strip()
        url = j.get("absolute_url") or ""
        if not title or not url:
            continue
        loc = (j.get("location") or {}).get("name", "") if isinstance(j.get("location"), dict) else ""
        depts = j.get("departments") or []
        dept = depts[0].get("name", "") if depts and isinstance(depts[0], dict) else ""
        out.append(
            Job(
                title=title,
                company=company.name,
                company_slug=company.slug,
                location=loc,
                url=url,
                source="greenhouse",
                posted_at=iso(j.get("updated_at") or j.get("first_published")),
                description=strip_html(j.get("content")),
                department=dept,
                company_location=company.location,
                company_tier=company.tier,
            )
        )
    return out
