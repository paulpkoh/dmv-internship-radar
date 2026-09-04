"""Lever job boards (api.lever.co)."""

from __future__ import annotations

from ..models import Company, Job
from .. import net
from ._common import iso, join_location, strip_html

API = "https://api.lever.co/v0/postings/{token}?mode=json"


def probe(token: str) -> bool:
    data = net.get_json(API.format(token=token))
    return isinstance(data, list)


def fetch(token: str, company: Company) -> list[Job]:
    data = net.get_json(API.format(token=token))
    if not isinstance(data, list):
        return []
    out: list[Job] = []
    for j in data:
        if not isinstance(j, dict):
            continue
        title = (j.get("text") or "").strip()
        url = j.get("hostedUrl") or j.get("applyUrl") or ""
        if not title or not url:
            continue
        cats = j.get("categories") or {}
        loc = join_location(cats.get("location"), cats.get("allLocations") and ", ".join(cats["allLocations"][:3]))
        desc = j.get("descriptionPlain") or strip_html(j.get("description"))
        lists = j.get("lists") or []
        extra = " ".join(strip_html(x.get("content", "")) for x in lists if isinstance(x, dict))
        out.append(
            Job(
                title=title,
                company=company.name,
                company_slug=company.slug,
                location=loc,
                url=url,
                source="lever",
                posted_at=iso(j.get("createdAt")),
                description=(desc + " " + extra).strip()[:4000],
                department=cats.get("team") or cats.get("department") or "",
                company_location=company.location,
                company_tier=company.tier,
            )
        )
    return out
