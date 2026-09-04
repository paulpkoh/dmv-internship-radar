"""Recruitee careers API."""

from __future__ import annotations

from ..models import Company, Job
from .. import net
from ._common import iso, join_location, strip_html

API = "https://{token}.recruitee.com/api/offers/"


def probe(token: str) -> bool:
    data = net.get_json(API.format(token=token))
    return isinstance(data, dict) and "offers" in data


def fetch(token: str, company: Company) -> list[Job]:
    data = net.get_json(API.format(token=token))
    if not isinstance(data, dict):
        return []
    out: list[Job] = []
    for j in data.get("offers") or []:
        if not isinstance(j, dict):
            continue
        title = (j.get("title") or "").strip()
        url = j.get("careers_url") or j.get("careers_apply_url") or ""
        if not title or not url:
            continue
        out.append(
            Job(
                title=title,
                company=company.name,
                company_slug=company.slug,
                location=join_location(j.get("city"), j.get("state_name"), j.get("country_code")),
                url=url,
                source="recruitee",
                posted_at=iso(j.get("published_at")),
                description=strip_html(j.get("description")) + " " + strip_html(j.get("requirements")),
                department=j.get("department") or "",
                remote=bool(j.get("remote")),
                company_location=company.location,
                company_tier=company.tier,
            )
        )
    return out
