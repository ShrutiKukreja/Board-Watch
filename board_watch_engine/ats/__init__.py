"""ATS adapter registry.

Each adapter exposes `fetch(token, search="") -> List[Job]`. Adapters whose
descriptions or form questions need a second call also expose
`enrich(job) -> Job`, which the pipeline invokes only for jobs that already
matched — one extra request per new role, not per posting.

`search` is a server-side narrowing hint, honoured by the boards in
HONOURS_SEARCH. Those publish hundreds or thousands of reqs that would otherwise
take a great many paginated requests to enumerate.
"""

from . import (amazon, ashby, greenhouse, lever, microsoft, smartrecruiters,
               workday)
from .base import FetchError  # noqa: F401 — re-exported for callers

FETCHERS = {
    "greenhouse": greenhouse.fetch,
    "ashby": ashby.fetch,
    "lever": lever.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workday": workday.fetch,
    "amazon": amazon.fetch,
    "microsoft": microsoft.fetch,
}

ENRICHERS = {
    "greenhouse": greenhouse.enrich,
    "smartrecruiters": smartrecruiters.enrich,
    "workday": workday.enrich,
}

# Boards that publish the application form itself, not just the posting.
EXPOSES_QUESTIONS = frozenset({"greenhouse"})

# Boards whose list endpoint carries a usable posting date, so age-based
# backfill can distinguish "posted this week" from "open for months".
# Workday reports only a relative age ("Posted 30+ Days Ago"); an exact date
# arrives with enrichment, too late for the freshness check.
HAS_POSTING_DATE = frozenset({"greenhouse", "ashby", "lever", "amazon",
                              "microsoft"})

# Boards that accept a server-side search term.
HONOURS_SEARCH = frozenset({"workday", "amazon", "microsoft"})


def fetch(ats, token, search=""):
    if ats not in FETCHERS:
        raise FetchError("no adapter for ats=%r" % ats)
    if ats in HONOURS_SEARCH:
        return FETCHERS[ats](token, search=search)
    return FETCHERS[ats](token)


def enrich(ats, job):
    fn = ENRICHERS.get(ats)
    return fn(job) if fn else job


def known():
    return frozenset(FETCHERS)
