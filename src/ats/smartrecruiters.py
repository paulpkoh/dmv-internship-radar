"""SmartRecruiters public postings API."""

from __future__ import annotations

from ..models import Company, Job
from .. import net
from ._common import iso, join_location, strip_html

LIST = "https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={offset}"
DETAIL = "https://api.smartrecruiters.com/v1/companies/{token}/postings/{pid}"


def probe(token: str) -> bool:
    data = net.get_json(LIST.format(token=token, offset=0))
    return isinstance(data, dict) and "content" in data


def fetch(token: str, company: Company) -> list[Job]:
    out: list[Job] = []
    offset = 0
    for _ in range(10):  # hard cap: 1000 postings
        data = net.get_json(LIST.format(token=token, offset=offset))
        if not isinstance(data, dict):
            break
        content = data.get("content") or []
        if not content:
            break
        for j in content:
            if not isinstance(j, dict):
                continue
            title = (j.get("name") or "").strip()
            if not title:
                continue
            loc = j.get("location") or {}
            location = join_location(loc.get("city"), loc.get("region"), loc.get("country", "").upper() if loc.get("country") else "")
            pid = j.get("id") or ""
            url = (j.get("ref") or "").replace("api.smartrecruiters.com/v1", "jobs.smartrecruiters.com")
            if not url:
                url = f"https://jobs.smartrecruiters.com/{token}/{pid}"
            dept = (j.get("department") or {}).get("label", "") if isinstance(j.get("department"), dict) else ""
            out.append(
                Job(
                    title=title,
                    company=company.name,
                    company_slug=company.slug,
                    location=location,
                    url=url,
                    source="smartrecruiters",
                    posted_at=iso(j.get("releasedDate")),
                    department=dept,
                    remote=bool(loc.get("remote")),
                    company_location=company.location,
                    company_tier=company.tier,
                )
            )
        offset += len(content)
        if offset >= int(data.get("totalFound") or 0):
            break
    return out


def enrich(token: str, job: Job) -> None:
    """Pull the full description for a posting we already care about."""
    pid = job.url.rstrip("/").split("/")[-1]
    data = net.get_json(DETAIL.format(token=token, pid=pid))
    if not isinstance(data, dict):
        return
    sections = ((data.get("jobAd") or {}).get("sections") or {})
    parts = []
    for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        sec = sections.get(key) or {}
        parts.append(strip_html(sec.get("text")))
    job.description = " ".join(p for p in parts if p)[:4000]
