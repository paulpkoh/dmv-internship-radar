"""Plain data structures shared across the pipeline."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "unknown"


@dataclass
class Company:
    name: str
    domain: str = ""
    city: str = ""
    state: str = ""
    category: str = ""          # free-text description from the directory
    tier: str = "biotech"       # biotech | major_employer | research_institution
    slug: str = field(default="")

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        self.domain = normalize_domain(self.domain)

    @property
    def location(self) -> str:
        if self.city and self.state:
            return f"{self.city}, {self.state}"
        return self.city or self.state or ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Company":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def normalize_domain(raw: str) -> str:
    if not raw:
        return ""
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    d = d.split("/")[0].split("?")[0].strip()
    return d


@dataclass
class Job:
    title: str
    company: str
    company_slug: str
    location: str
    url: str
    source: str                     # greenhouse | lever | ashby | ... | html
    remote: bool = False
    posted_at: str = ""             # ISO date if the board tells us
    description: str = ""           # plain text, truncated
    department: str = ""
    category: str = ""              # internship | part_time_research
    relevance: int = 0
    matched_keywords: list[str] = field(default_factory=list)
    confidence: str = "high"        # high (from an ATS) | low (page scrape)
    company_location: str = ""
    company_tier: str = "biotech"
    id: str = ""
    first_seen: str = ""
    last_seen: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.make_id()

    def make_id(self) -> str:
        basis = f"{self.company_slug}|{self.title.strip().lower()}|{self.location.strip().lower()}|{self.url.strip()}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Job":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
