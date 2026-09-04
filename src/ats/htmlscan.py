"""Last-resort scan of a plain HTML careers page.

Most of the 400-odd small biotechs on the directory run a hand-written
careers page rather than an ATS. This finds links whose text looks like an
internship and emits them as low-confidence hits so they still surface,
clearly marked so you know to click through and confirm.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import config, net
from ..models import Company, Job
from ._common import strip_html

_TITLE_HINT = re.compile("|".join(config.INTERNSHIP_PATTERNS + config.PART_TIME_PATTERNS), re.I)
_NOISE = re.compile(r"privacy|cookie|newsletter|sign in|log in|linkedin|twitter", re.I)


def scan(careers_url: str, company: Company) -> list[Job]:
    html = net.get_text(careers_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    page_text = strip_html(html)

    out: list[Job] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        text = re.sub(r"\s+", " ", a.get_text() or "").strip()
        if not text or len(text) > 140 or _NOISE.search(text):
            continue
        if not _TITLE_HINT.search(text):
            continue
        url = urljoin(careers_url, a["href"])
        if url in seen or url.startswith("mailto:"):
            continue
        seen.add(url)
        out.append(
            Job(
                title=text,
                company=company.name,
                company_slug=company.slug,
                location=company.location,
                url=url,
                source="html",
                description=page_text[:1500],
                confidence="low",
                company_location=company.location,
                company_tier=company.tier,
            )
        )

    # A careers page that mentions internships but has no per-role links still
    # deserves one pointer, so the page itself is not silently lost.
    if not out and _TITLE_HINT.search(page_text[:6000]):
        out.append(
            Job(
                title=f"Careers page mentions internships - {company.name}",
                company=company.name,
                company_slug=company.slug,
                location=company.location,
                url=careers_url,
                source="html",
                description=page_text[:1500],
                confidence="low",
                company_location=company.location,
                company_tier=company.tier,
            )
        )
    return out[:25]
