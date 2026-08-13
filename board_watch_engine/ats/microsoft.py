"""Microsoft — in-house board (`pcsx`), one company rather than an ATS product.

Endpoint confirmed by watching the careers site's own network traffic. Note the
host: `jobs.careers.microsoft.com` redirects to `apply.careers.microsoft.com`,
and only the latter serves the API.

Descriptions are not retrievable — no per-position endpoint responds, so this
board behaves like Ashby and Lever: title, location and link only. That means
`require_any_keyword_in_description` cannot filter Microsoft roles.

`token` is unused (there is only one Microsoft). `search` narrows the board;
Microsoft publishes ~500 product roles at any time, so an unbounded fetch is
never wanted.
"""

import re
from datetime import datetime, timezone

from ..models import Job
from .base import get_json

BASE = "https://apply.careers.microsoft.com"
SEARCH_URL = BASE + "/api/pcsx/search?domain=microsoft.com&query=%s&location=%s&start=%d"

PAGE = 10  # fixed by the API; `start` is a row offset, not a page number
MAX_PAGES = 30  # 300 postings; a safety valve
DEFAULT_SEARCH = "product manager"


def fetch(token=None, search="", location=""):
    out, start, seen_ids, total = [], 0, set(), None
    query = _quote(search or DEFAULT_SEARCH)

    for _ in range(MAX_PAGES):
        d = get_json(SEARCH_URL % (query, _quote(location), start))
        data = d.get("data") or {}
        positions = data.get("positions") or []
        if not positions:
            break

        if total is None:
            total = int(data.get("count") or 0)

        for p in positions:
            job = _to_job(p)
            if not job.id or job.id in seen_ids:
                continue
            seen_ids.add(job.id)
            out.append(job)

        start += PAGE
        if len(positions) < PAGE:
            break
        if total and start >= total:
            break

    return out


def _to_job(p):
    # standardizedLocations is cleaner ('Redmond, WA, US') than the raw
    # 'United States, Washington, Redmond'.
    locations = p.get("standardizedLocations") or p.get("locations") or []
    location = " | ".join(locations)
    url = BASE + (p.get("positionUrl") or "")
    flexibility = (p.get("workLocationOption") or "").lower()

    return Job(
        # displayJobId is the requisition number users see and recruiters quote;
        # `id` is an internal surrogate.
        id=str(p.get("displayJobId") or p.get("atsJobId") or p.get("id") or ""),
        title=p.get("name", ""),
        location=location,
        url=url,
        apply_url=url,
        description="",  # no per-position endpoint exists
        team=p.get("department") or "",
        posted_at=_epoch(p.get("postedTs") or p.get("creationTs")),
        remote=flexibility in ("remote", "hybrid") or "remote" in location.lower(),
        questions=None,  # form not exposed publicly
    )


def _epoch(ts):
    """postedTs is epoch seconds."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def _quote(s):
    return re.sub(r"\s+", "%20", str(s or "").strip())
