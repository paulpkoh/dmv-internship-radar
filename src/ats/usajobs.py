"""USAJOBS search API - covers NIST, NIH, FDA, Census, CMS, NGA and the rest
of the federal DMV in one place.

Needs a free API key: https://developer.usajobs.gov/apirequest/
Set USAJOBS_API_KEY and USAJOBS_EMAIL in the environment (GitHub Actions
secrets). Without them this source is skipped silently.
"""

from __future__ import annotations

import logging
import os

from ..models import Company, Job
from .. import net
from ._common import iso, strip_html

log = logging.getLogger(__name__)

BASE = "https://data.usajobs.gov/api/search"

# Federal duty stations within commuting range.
LOCATIONS = (
    "Washington, District of Columbia",
    "Baltimore, Maryland",
    "Bethesda, Maryland",
    "Rockville, Maryland",
    "Gaithersburg, Maryland",
    "Silver Spring, Maryland",
    "College Park, Maryland",
    "Frederick, Maryland",
    "Arlington, Virginia",
    "Alexandria, Virginia",
)

KEYWORDS = (
    "data science", "machine learning", "artificial intelligence",
    "bioinformatics", "computer science", "software", "biomedical engineering",
    "computational", "statistics",
)


def _credentials() -> tuple[str, str] | None:
    key = os.environ.get("USAJOBS_API_KEY", "").strip()
    email = os.environ.get("USAJOBS_EMAIL", "").strip()
    if not key or not email:
        return None
    return key, email


def available() -> bool:
    return _credentials() is not None


def fetch_all() -> list[Job]:
    creds = _credentials()
    if not creds:
        log.info("USAJOBS: no API key configured, skipping")
        return []
    key, email = creds
    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}

    company = Company(
        name="US Federal Government",
        domain="usajobs.gov",
        city="Washington",
        state="DC",
        category="Federal agencies (NIST, NIH, FDA, Census, CMS, NGA and others)",
        tier="research_institution",
    )

    seen: set[str] = set()
    out: list[Job] = []
    for location in LOCATIONS:
        for keyword in KEYWORDS:
            params = {
                "Keyword": keyword,
                "LocationName": location,
                "Radius": "30",
                "ResultsPerPage": "100",
                "HiringPath": "student;intern;recentgrad",
                "SortField": "opendate",
                "SortDirection": "Desc",
            }
            r = net.get(BASE, params=params, headers=headers)
            if r is None or r.status_code != 200:
                continue
            try:
                data = r.json()
            except ValueError:
                continue
            items = (((data or {}).get("SearchResult") or {}).get("SearchResultItems")) or []
            for item in items:
                d = (item or {}).get("MatchedObjectDescriptor") or {}
                title = (d.get("PositionTitle") or "").strip()
                url = d.get("PositionURI") or ""
                if not title or not url or url in seen:
                    continue
                seen.add(url)
                locs = d.get("PositionLocation") or []
                loc_names = ", ".join(
                    x.get("LocationName", "") for x in locs[:3] if isinstance(x, dict)
                )
                summary = (d.get("UserArea") or {}).get("Details", {}) or {}
                desc = " ".join(
                    strip_html(str(x))
                    for x in (
                        d.get("QualificationSummary"),
                        summary.get("JobSummary"),
                        summary.get("MajorDuties"),
                    )
                    if x
                )
                out.append(
                    Job(
                        title=title,
                        company=d.get("OrganizationName") or "US Federal Government",
                        company_slug="us-federal-government",
                        location=loc_names,
                        url=url,
                        source="usajobs",
                        posted_at=iso(d.get("PublicationStartDate")),
                        description=desc[:4000],
                        department=d.get("DepartmentName") or "",
                        company_location=company.location,
                        company_tier=company.tier,
                    )
                )
    log.info("USAJOBS: %d postings", len(out))
    return out
