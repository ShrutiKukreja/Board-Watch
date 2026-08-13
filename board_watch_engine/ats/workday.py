"""Workday — self-hosted per tenant, so the token carries three parts.

    "token": "fractal/wd1/Careers"
              tenant  host site

Unlike the other four boards there is no shared API host: every customer runs
its own `<tenant>.<host>.myworkdayjobs.com`. The list endpoint is a POST, caps
at 20 results per page, and reports only a *relative* posting age
("Posted 30+ Days Ago"). An exact date exists, but only on the per-job call.

Large tenants (Nvidia publishes thousands of reqs) would need hundreds of
requests to enumerate, so a company may set `"search"` to narrow server-side
before our own filters run.
"""

import re
from datetime import timedelta

from ..models import Job
from ..util import iso, now_utc, strip_html
from .base import FetchError, get_json

PAGE = 20  # Workday rejects anything larger with HTTP 400
MAX_PAGES = 25  # 500 postings; a safety valve, not an expected limit

_RELATIVE = re.compile(r"posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)", re.I)


def _parse_token(token):
    parts = [p for p in (token or "").split("/") if p]
    if len(parts) != 3:
        raise FetchError(
            "workday token must be 'tenant/host/site', got %r" % token
        )
    return parts  # tenant, host, site


def _base(tenant, host, site):
    return "https://%s.%s.myworkdayjobs.com/wday/cxs/%s/%s" % (
        tenant, host, tenant, site
    )


def fetch(token, search=""):
    tenant, host, site = _parse_token(token)
    base = _base(tenant, host, site)
    out, offset, seen_ids, total = [], 0, set(), None

    for _ in range(MAX_PAGES):
        d = get_json(
            base + "/jobs",
            data={
                "appliedFacets": {},
                "limit": PAGE,
                "offset": offset,
                "searchText": search or "",
            },
        )
        postings = d.get("jobPostings") or []
        if not postings:
            break

        # `total` is only populated on the first page — every subsequent
        # response reports 0, so it must be captured once and never re-read.
        if total is None:
            total = int(d.get("total") or 0)

        for p in postings:
            job = _to_job(p, tenant, host, site)
            # Workday paginates over a live result set; a req can repeat across
            # pages if the underlying order shifts mid-enumeration.
            if job.id in seen_ids:
                continue
            seen_ids.add(job.id)
            out.append(job)

        offset += PAGE
        if len(postings) < PAGE:
            break
        if total and offset >= total:
            break

    return out


def _to_job(p, tenant, host, site):
    path = p.get("externalPath") or ""
    bullets = p.get("bulletFields") or []
    # bulletFields[0] is the requisition id (e.g. 'SR-43318') — stable across
    # re-postings, unlike the slugified path.
    job_id = bullets[0] if bullets else (path.rsplit("/", 1)[-1] or path)
    location = p.get("locationsText") or ""

    return Job(
        id=str(job_id),
        title=p.get("title", ""),
        location=location,
        url="https://%s.%s.myworkdayjobs.com/%s%s" % (tenant, host, site, path),
        apply_url="https://%s.%s.myworkdayjobs.com/%s%s" % (tenant, host, site, path),
        posted_at=_approx_date(p.get("postedOn")),
        remote="remote" in location.lower(),
        board_token="%s/%s/%s" % (tenant, host, site),
        questions=None,  # Workday does not expose the form publicly
    )


def enrich(job):
    """Second call — full description and, usefully, an exact posting date."""
    try:
        tenant, host, site = _parse_token(job.board_token)
        path = job.url.split("myworkdayjobs.com/%s" % site, 1)[-1]
        d = get_json(_base(tenant, host, site) + path)
    except Exception as e:  # noqa: BLE001 — recorded on the job, never fatal
        job.error = str(e)
        return job

    info = d.get("jobPostingInfo") or {}
    job.description = strip_html(info.get("jobDescription", ""))
    if info.get("externalUrl"):
        job.apply_url = info["externalUrl"]
    if info.get("startDate"):
        # Exact, unlike the relative text on the list endpoint.
        job.posted_at = "%sT00:00:00Z" % info["startDate"]
    if info.get("location") and not job.location:
        job.location = info["location"]
    return job


def _approx_date(text):
    """Turn 'Posted 3 Days Ago' into a timestamp.

    '30+ Days Ago' is deliberately left unresolved — the true age is unknown and
    guessing 30 would let a months-old req pass a 30-day freshness window.
    """
    m = _RELATIVE.search(text or "")
    if not m:
        return None
    token = m.group(1).lower()
    if token == "today":
        days = 0
    elif token == "yesterday":
        days = 1
    elif m.group(2) and "+" not in text:
        days = int(m.group(2))
    else:
        return None
    return iso(now_utc() - timedelta(days=days))
