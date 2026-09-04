"""BambooHR hosted careers pages."""

from __future__ import annotations

from ..models import Company, Job
from .. import net
from ._common import join_location

API = "https://{token}.bamboohr.com/careers/list"


def probe(token: str) -> bool:
    data = net.get_json(API.format(token=token))
    return isinstance(data, dict) and "result" in data


def fetch(token: str, company: Company) -> list[Job]:
    data = net.get_json(API.format(token=token))
    if not isinstance(data, dict):
        return []
    out: list[Job] = []
    for j in data.get("result") or []:
        if not isinstance(j, dict):
            continue
        title = (j.get("jobOpeningName") or "").strip()
        jid = j.get("id")
        if not title or jid is None:
            continue
        loc = j.get("location") or {}
        out.append(
            Job(
                title=title,
                company=company.name,
                company_slug=company.slug,
                location=join_location(loc.get("city"), loc.get("state")),
                url=f"https://{token}.bamboohr.com/careers/{jid}",
                source="bamboohr",
                description=j.get("employmentStatusLabel") or "",
                department=j.get("departmentLabel") or "",
                remote=str(j.get("isRemote", "")).lower() in ("yes", "true", "1"),
                company_location=company.location,
                company_tier=company.tier,
            )
        )
    return out
