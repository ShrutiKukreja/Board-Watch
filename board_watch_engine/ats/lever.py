"""Lever — descriptions in the list call, no public application form."""

from datetime import datetime, timezone

from ..models import Job
from ..util import strip_html
from .base import first, get_json

LIST_URL = "https://api.lever.co/v0/postings/%s?mode=json"


def fetch(token):
    d = get_json(LIST_URL % token)
    out = []
    for j in d if isinstance(d, list) else []:
        cats = j.get("categories") or {}
        out.append(
            Job(
                id=str(j.get("id")),
                title=j.get("text", ""),
                location=cats.get("location", ""),
                url=j.get("hostedUrl", ""),
                apply_url=first(j.get("applyUrl"), j.get("hostedUrl")),
                description=strip_html(
                    first(j.get("descriptionPlain"), j.get("description"))
                ),
                team=cats.get("team", ""),
                posted_at=_epoch_ms(j.get("createdAt")),
                remote="remote" in (cats.get("commitment") or "").lower(),
                questions=None,
            )
        )
    return out


def _epoch_ms(v):
    """Lever reports createdAt as epoch milliseconds."""
    if not v:
        return None
    try:
        return datetime.fromtimestamp(int(v) / 1000, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (ValueError, TypeError, OSError, OverflowError):
        return None
