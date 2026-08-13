"""SmartRecruiters — list is public; descriptions need a per-posting call.

Unlike the others this board exposes no usable posting date on the list
endpoint, so age-based backfill cannot apply here (see DESIGN.md §6.3).
"""

from ..models import Job
from ..util import strip_html
from .base import get_json

LIST_URL = "https://api.smartrecruiters.com/v1/companies/%s/postings?limit=100"
DETAIL_URL = "https://api.smartrecruiters.com/v1/companies/%s/postings/%s"
APPLY_URL = "https://jobs.smartrecruiters.com/%s/%s"


def fetch(token):
    d = get_json(LIST_URL % token)
    out = []
    for j in d.get("content", []):
        loc = j.get("location") or {}
        out.append(
            Job(
                id=str(j.get("id")),
                title=j.get("name", ""),
                location=", ".join(
                    x for x in [loc.get("city"), loc.get("country")] if x
                ),
                url=j.get("ref", ""),
                apply_url=APPLY_URL % (token, j.get("id")),
                posted_at=j.get("releasedDate"),
                remote=bool(loc.get("remote")),
                board_token=token,
                questions=None,
            )
        )
    return out


def enrich(job):
    """Descriptions live behind a second call, same as Greenhouse."""
    try:
        d = get_json(DETAIL_URL % (job.board_token, job.id))
    except Exception as e:  # noqa: BLE001
        job.error = str(e)
        return job

    sections = ((d.get("jobAd") or {}).get("sections")) or {}
    parts = []
    for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        text = (sections.get(key) or {}).get("text")
        if text:
            parts.append(strip_html(text))
    job.description = "\n\n".join(parts)
    return job
