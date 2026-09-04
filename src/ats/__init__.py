"""Connectors for the applicant tracking systems companies actually use.

Every connector exposes the same shape:

    fetch(token, company) -> list[Job]      # returns [] on any failure
    probe(token) -> bool                    # cheap validity check for discovery

`REGISTRY` maps a source name to its module. Discovery writes the source name
and token into data/ats.json; the fetch stage reads it back.
"""

from __future__ import annotations

from . import (
    ashby,
    bamboohr,
    greenhouse,
    lever,
    recruitee,
    rippling,
    smartrecruiters,
    workable,
    workday,
)

REGISTRY = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "smartrecruiters": smartrecruiters,
    "workable": workable,
    "recruitee": recruitee,
    "bamboohr": bamboohr,
    "rippling": rippling,
    "workday": workday,
}

__all__ = ["REGISTRY"]
