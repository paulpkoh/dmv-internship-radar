"""Workable embedded job widget API."""

from __future__ import annotations

from ..models import Company, Job
from .. import net
from ._common import iso, join_location, strip_html

API = "https://apply.workable.com/api/v1/widget/accounts/{token}?details=true"


def probe(token: str) -> bool:
    data = net.get_json(API.format(token=token))
    return isinstance(data, dict) and "jobs" in data


def fetch(token: str, company: Company) -> list[Job]:
    data = net.get_json(API.format(token=token))
    if not isinstance(data, dict):
        return []
    out: list[Job] = []
    for j in data.get("jobs") or []:
        if not isinstance(j, dict):
            continue
        title = (j.get("title") or "").strip()
        url = j.get("url") or j.get("shortlink") or j.get("application_url") or ""
        if not title or not url:
            continue
        location = join_location(j.get("city"), j.get("state"), j.get("country"))
        if str(j.get("telecommuting")).lower() == "true":
            location = join_location(location, "Remote")
        out.append(
            Job(
                title=title,
                company=company.name,
                company_slug=company.slug,
                location=location,
                url=url,
                source="workable",
                posted_at=iso(j.get("published_on") or j.get("created_at")),
                description=strip_html(j.get("description")) + " " + strip_html(j.get("requirements")),
                department=j.get("department") or "",
                remote=bool(j.get("telecommuting")),
                company_location=company.location,
                company_tier=company.tier,
            )
        )
    return out
