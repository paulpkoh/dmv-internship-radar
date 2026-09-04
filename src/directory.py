"""Scrapes the BioPharmGuy DC-area company directory into Company records.

The directory is a plain HTML table, but the markup has changed shape before,
so this parser tries a structured pass first and falls back to a link sweep.
If both come up short, run.py falls back to the bundled snapshot in
data/companies_snapshot.json.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from . import config, net
from .models import Company, normalize_domain

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = DATA_DIR / "companies_snapshot.json"

# Anchors pointing at these are navigation, not companies.
_IGNORE_HOSTS = re.compile(
    r"(biopharmguy|facebook|twitter|x\.com|linkedin|google|youtube|instagram)\.",
    re.I,
)

_STATE_RE = re.compile(r"\b([A-Z]{2})\b\s*$")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _split_location(raw: str) -> tuple[str, str]:
    """'Rockville, MD' -> ('Rockville', 'MD')."""
    raw = _clean(raw).strip(",")
    if not raw:
        return "", ""
    m = _STATE_RE.search(raw)
    if m:
        state = m.group(1).upper()
        city = raw[: m.start()].strip().strip(",").strip()
        return city, state
    if "," in raw:
        city, _, state = raw.rpartition(",")
        return _clean(city), _clean(state).upper()[:2]
    return raw, ""


def _from_table(soup: BeautifulSoup) -> list[Company]:
    out: list[Company] = []
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        anchor = None
        for c in cells:
            a = c.find("a", href=True)
            if a and a["href"].startswith("http") and not _IGNORE_HOSTS.search(a["href"]):
                anchor = a
                break
        if anchor is None:
            continue

        name = _clean(anchor.get_text()) or _clean(cells[0].get_text())
        if not name or len(name) > 120:
            continue
        domain = normalize_domain(anchor["href"])
        if not domain:
            continue

        texts = [_clean(c.get_text()) for c in cells]
        texts = [t for t in texts if t and t != name]
        city = state = ""
        description = ""
        for t in texts:
            c, s = _split_location(t)
            if s and len(s) == 2 and s.isalpha() and not city:
                city, state = c, s
            elif len(t) > len(description):
                description = t
        out.append(
            Company(
                name=name,
                domain=domain,
                city=city,
                state=state,
                category=description[:200],
                tier="biotech",
            )
        )
    return out


def _from_links(soup: BeautifulSoup) -> list[Company]:
    """Fallback: every external anchor becomes a company."""
    out: list[Company] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http") or _IGNORE_HOSTS.search(href):
            continue
        name = _clean(a.get_text())
        if not name or len(name) > 120 or name.lower().startswith("http"):
            continue
        domain = normalize_domain(href)
        if not domain or "." not in domain:
            continue
        # Look at the surrounding row/paragraph for a location.
        context = ""
        parent = a.find_parent(["tr", "li", "p", "div"])
        if parent is not None:
            context = _clean(parent.get_text())
        city = state = ""
        m = re.search(r"([A-Za-z .'\-]+),\s*(MD|VA|DC|DE)\b", context)
        if m:
            city, state = _clean(m.group(1)), m.group(2)
            # Trim the company name off the front of the captured city.
            if city.lower().startswith(name.lower()):
                city = _clean(city[len(name):])
        out.append(Company(name=name, domain=domain, city=city, state=state))
    return out


def _dedupe(companies: list[Company]) -> list[Company]:
    seen: dict[str, Company] = {}
    for c in companies:
        if not c.domain or not c.name:
            continue
        key = c.domain
        prev = seen.get(key)
        # Keep the record with the most information.
        if prev is None or (len(c.category) + len(c.city)) > (len(prev.category) + len(prev.city)):
            seen[key] = c
    return sorted(seen.values(), key=lambda c: c.name.lower())


def load_snapshot() -> list[Company]:
    if not SNAPSHOT.exists():
        return []
    data = json.loads(SNAPSHOT.read_text())
    return [Company.from_dict(d) for d in data]


def fetch(url: str = config.BIOPHARMGUY_URL) -> list[Company]:
    html = net.get_text(url)
    if not html:
        log.warning("Could not fetch %s", url)
        return []
    soup = BeautifulSoup(html, "html.parser")
    companies = _dedupe(_from_table(soup))
    if len(companies) < 50:
        log.warning("Table parse yielded %d rows; falling back to link sweep", len(companies))
        companies = _dedupe(companies + _from_links(soup))
    log.info("Directory: parsed %d companies", len(companies))
    return companies
