"""Amazon — in-house board, one company rather than an ATS product.

Unusually generous compared with the hosted boards: the list endpoint returns
the full description and qualifications inline, so there is no `enrich` step and
`require_any_keyword_in_description` works on the first pass.

`token` is unused (there is only one Amazon). `search` is what narrows the board
— Amazon publishes tens of thousands of reqs, so an unbounded fetch is never
wanted.
"""

import re
from datetime import datetime, timezone

from ..models import Job
from ..util import strip_html
from .base import get_json

SEARCH_URL = "https://www.amazon.jobs/search.json"
JOB_URL = "https://www.amazon.jobs%s"

PAGE = 100  # 200 is rejected
MAX_PAGES = 10  # 1000 most-recent postings; a safety valve
DEFAULT_SEARCH = "product"  # catches product manager / owner / technical PM


def fetch(token=None, search=""):
    out, offset, seen_ids = [], 0, set()
    query = search or DEFAULT_SEARCH

    for _ in range(MAX_PAGES):
        d = get_json(
            "%s?base_query=%s&result_limit=%d&offset=%d&sort=recent"
            % (SEARCH_URL, _quote(query), PAGE, offset)
        )
        postings = d.get("jobs") or []
        if not postings:
            break

        for p in postings:
            job = _to_job(p)
            if job.id in seen_ids:
                continue
            seen_ids.add(job.id)
            out.append(job)

        offset += PAGE
        if len(postings) < PAGE:
            break
        if offset >= int(d.get("hits") or 0):
            break

    return out


def _to_job(p):
    location = p.get("normalized_location") or p.get("location") or ""
    path = p.get("job_path") or ""
    url = JOB_URL % path if path else ""

    return Job(
        # id_icims is the stable requisition number; `id` is a UUID that churns.
        id=str(p.get("id_icims") or p.get("id") or ""),
        title=p.get("title", ""),
        location=location,
        url=url,
        apply_url=p.get("url_next_step") or url,
        description=_description(p),
        team=p.get("job_family") or p.get("job_category") or "",
        posted_at=_parse_date(p.get("posted_date")),
        remote="virtual" in location.lower() or "remote" in location.lower(),
        questions=None,  # Amazon does not expose the form publicly
    )


def _description(p):
    """Amazon splits the posting across three fields; matching needs all of them."""
    parts = [
        p.get("description"),
        p.get("basic_qualifications"),
        p.get("preferred_qualifications"),
    ]
    return strip_html("<br/><br/>".join(x for x in parts if x))


def _parse_date(text):
    """'August 11, 2026' -> ISO. Returns None rather than raising on a new format."""
    if not text:
        return None
    try:
        dt = datetime.strptime(str(text).strip(), "%B %d, %Y")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _quote(s):
    return re.sub(r"\s+", "+", str(s).strip())
