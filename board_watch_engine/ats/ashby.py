"""Ashby — full descriptions in the list call, but no public application form."""

from ..models import Job
from ..util import strip_html
from .base import first, get_json

LIST_URL = "https://api.ashbyhq.com/posting-api/job-board/%s?includeCompensation=true"


def fetch(token):
    d = get_json(LIST_URL % token)
    out = []
    for j in d.get("jobs", []):
        if j.get("isListed") is False:
            continue
        comp = j.get("compensation") or {}
        out.append(
            Job(
                id=str(j.get("id")),
                title=j.get("title", ""),
                location=j.get("location") or "",
                url=j.get("jobUrl", ""),
                apply_url=first(j.get("applyUrl"), j.get("jobUrl")),
                description=first(
                    j.get("descriptionPlain"),
                    strip_html(j.get("descriptionHtml", "")),
                ),
                compensation=(
                    comp.get("compensationTierSummary", "")
                    if isinstance(comp, dict) else ""
                ),
                team=first(j.get("team"), j.get("department")),
                posted_at=first(j.get("publishedAt"), j.get("updatedAt")),
                remote=bool(j.get("isRemote")),
                questions=None,  # Ashby does not expose the form publicly
            )
        )
    return out
