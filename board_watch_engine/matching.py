"""Deciding which postings are worth an application packet."""

import re

# Questions companies commonly want written without AI assistance, or that are
# so personal a generated answer is actively harmful. The packet builder gives
# raw material for these, never a draft.
WRITE_YOURSELF = re.compile(
    r"why (do you want to |would you like to )?(work at|join|anthropic|openai|us\b)"
    r"|why (are you )?interested"
    r"|in your own words"
    r"|personal (statement|preferences)"
    r"|what excites you"
    r"|tell us about yourself",
    re.I,
)


def title_hit(title, pattern):
    """'a && b' requires both terms; a plain string is a substring test."""
    if "&&" in pattern:
        return all(p.strip() in title for p in pattern.split("&&"))
    return pattern in title


def matches(job, rules):
    """Apply the configured filters. Order is cheapest-test-first."""
    title = (job.title or "").lower()

    if rules.include_title and not any(
        title_hit(title, k) for k in rules.include_title
    ):
        return False
    if any(k in title for k in rules.exclude_title):
        return False

    if rules.locations_allow:
        loc = (job.location or "").lower()
        remote = job.remote or "remote" in loc
        allows_remote = "remote" in rules.locations_allow
        if not (remote and allows_remote) and not any(
            a in loc for a in rules.locations_allow
        ):
            return False

    if rules.require_any_keyword_in_description:
        desc = (job.description or "").lower()
        # An empty description means the ATS defers it to a second call; do not
        # reject on evidence we have not fetched yet.
        if desc and not any(
            k in desc for k in rules.require_any_keyword_in_description
        ):
            return False

    return True


def needs_write_yourself(label):
    return bool(WRITE_YOURSELF.search(label or ""))


def is_fresh(job, backfill_days):
    """Whether a posting is recent enough to package during init backfill.

    Unknown dates count as stale — SmartRecruiters exposes none, and treating
    unknown as fresh would package an entire board on day one.
    """
    from .util import days_since

    if backfill_days <= 0:
        return False
    age = days_since(job.posted_at)
    return age is not None and age <= backfill_days
