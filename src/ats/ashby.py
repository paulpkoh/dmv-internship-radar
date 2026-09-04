"""Ashby job boards (api.ashbyhq.com posting API)."""

from __future__ import annotations

from ..models import Company, Job
from .. import net
from ._common import iso, strip_html

API = "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=false"


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
        url = j.get("jobUrl") or j.get("applyUrl") or ""
        if not title or not url:
            continue
        loc = j.get("location") or ""
        if not loc and isinstance(j.get("address"), dict):
            addr = j["address"].get("postalAddress") or {}
            loc = ", ".join(x for x in [addr.get("addressLocality"), addr.get("addressRegion")] if x)
        desc = j.get("descriptionPlain") or strip_html(j.get("descriptionHtml"))
        out.append(
            Job(
                title=title,
                company=company.name,
                company_slug=company.slug,
                location=loc,
                url=url,
                source="ashby",
                posted_at=iso(j.get("publishedAt") or j.get("updatedAt")),
                description=(desc or "")[:4000],
                department=j.get("department") or j.get("team") or "",
                remote=bool(j.get("isRemote")),
                company_location=company.location,
                company_tier=company.tier,
            )
        )
    return out
