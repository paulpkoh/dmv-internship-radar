"""Helpers shared by the ATS connectors."""

from __future__ import annotations

import html as _html
import re
from datetime import datetime, timezone
from typing import Any

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

MAX_DESC = 4000


def strip_html(raw: str | None) -> str:
    if not raw:
        return ""
    text = _html.unescape(raw)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</li>|</div>", "\n", text, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    text = _html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    return text[:MAX_DESC]


def iso(value: Any) -> str:
    """Best-effort conversion of whatever a board calls a date into ISO-8601."""
    if value in (None, "", 0):
        return ""
    if isinstance(value, (int, float)):
        # Lever and friends use epoch milliseconds.
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return ""
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text.replace("Z", "+0000") if fmt.endswith("%z") else text, fmt).date().isoformat()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    return m.group(0) if m else ""


def join_location(*parts: Any) -> str:
    seen: list[str] = []
    for p in parts:
        if not p:
            continue
        s = str(p).strip().strip(",")
        if s and s.lower() not in {x.lower() for x in seen} and s.lower() not in {"null", "none"}:
            seen.append(s)
    return ", ".join(seen)
