"""Greenhouse — the only ATS that exposes the real application form questions.

Two calls: a cheap list, then a per-job enrichment fetched only for matches.
"""

from ..models import Job, Question
from ..util import strip_html
from .base import get_json

LIST_URL = "https://boards-api.greenhouse.io/v1/boards/%s/jobs"
JOB_URL = "https://boards-api.greenhouse.io/v1/boards/%s/jobs/%s?questions=true"


def fetch(token):
    d = get_json(LIST_URL % token)
    out = []
    for j in d.get("jobs", []):
        url = j.get("absolute_url", "")
        out.append(
            Job(
                id=str(j.get("id")),
                title=j.get("title", ""),
                location=(j.get("location") or {}).get("name", ""),
                url=url,
                apply_url=url,
                posted_at=j.get("first_published") or j.get("updated_at"),
                board_token=token,
            )
        )
    return out


def enrich(job):
    """Second call — full description plus the real form questions."""
    try:
        d = get_json(JOB_URL % (job.board_token, job.id))
    except Exception as e:  # noqa: BLE001 — recorded on the job, never fatal
        job.error = str(e)
        return job

    job.description = strip_html(d.get("content", ""))
    job.questions = [_question(q) for q in d.get("questions", [])]
    if d.get("location") and not job.location:
        job.location = (d.get("location") or {}).get("name", "")
    return job


def _question(q):
    fields = q.get("fields") or [{}]
    f = fields[0]
    return Question(
        label=(q.get("label") or "").strip(),
        required=bool(q.get("required")),
        type=f.get("type", ""),
        options=[v.get("label") for v in (f.get("values") or []) if v.get("label")],
    )
