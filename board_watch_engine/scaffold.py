"""Spec step 1 — create anything that is missing, touch nothing that exists.

Runs at the head of every poll, so a repo that loses a folder heals itself on
the next cycle rather than erroring.
"""

import os

from . import SCHEMA_VERSION
from .config import DEFAULT_CONFIG
from .util import now_utc, read_json, write_json_atomic

SUMMARY_HEADER = "# Application ledger — %s\n\n"

PROFILE_TEMPLATE = """# %s — Master Profile / Answer Bank

> **Single source of truth.** Every application answer and every tailored resume is
> selected from this file. Nothing downstream invents content that is not here.
>
> `board-watch init` populates this from your resume plus the logistics
> questionnaire. Keep it updated by hand — everything downstream is only as good
> as this file.

---

## 1. Identity & logistics

<!-- populated by `board-watch init` -->

## 2. Work authorisation

<!-- populated by `board-watch init` — not derivable from a resume -->

## 3. Compensation & notice

<!-- populated by `board-watch init` — not derivable from a resume -->

## 4. Experience (superset)

> Every bullet, project and metric you have. Deliberately longer than two pages —
> tailoring is *selection* from this list, never generation.

<!-- populated by `board-watch init` -->
"""

# A starter board. `init` regenerates this from the user's target role; this
# exists so a bare `scaffold` still produces a runnable config.
DEFAULT_COMPANIES = {
    "_comment": (
        "ats: greenhouse | ashby | lever | smartrecruiters | manual. 'token' is the "
        "board slug. To resolve a 'manual' entry: open the company's careers page, "
        "DevTools > Network > XHR, reload, and look for a request to "
        "boards-api.greenhouse.io / api.ashbyhq.com / api.lever.co — the slug is in "
        "the URL."
    ),
    "companies": [
        {"name": "Anthropic", "region": "USA", "ats": "greenhouse", "token": "anthropic", "tier": 1},
        {"name": "OpenAI", "region": "USA", "ats": "ashby", "token": "openai", "tier": 1},
    ],
    "match": {
        "include_title": ["product manager", "product lead", "ai product"],
        "exclude_title": ["product marketing", "intern", "internship", "engineer"],
        "require_any_keyword_in_description": [],
        "locations_allow": [],
        "_locations_note": (
            "Empty list = match everywhere. Add e.g. [\"india\",\"remote\",\"london\"] "
            "to narrow."
        ),
    },
}


def ensure_scaffold(paths, profile_name="Profile"):
    """Create the full tree. Returns a list of what was created, for logging."""
    created = []

    for d in paths.all_directories():
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            created.append(_rel(paths, d))

    if not os.path.exists(paths.config_file):
        write_json_atomic(paths.config_file, DEFAULT_CONFIG.to_dict())
        created.append(_rel(paths, paths.config_file))

    if not os.path.exists(paths.companies_file):
        write_json_atomic(paths.companies_file, DEFAULT_COMPANIES)
        created.append(_rel(paths, paths.companies_file))

    if paths.profile_file() is None:
        target = os.path.join(paths.profile_dir, _slug_name(profile_name) + ".md")
        with open(target, "w") as f:
            f.write(PROFILE_TEMPLATE % profile_name)
        created.append(_rel(paths, target))

    if not os.path.exists(paths.seen_file):
        write_json_atomic(paths.seen_file, {"_schema": SCHEMA_VERSION})
        created.append(_rel(paths, paths.seen_file))

    now = now_utc()
    summary = paths.summary_file(now)
    if not os.path.exists(summary):
        from .summary import HEADER as SUMMARY_COLUMNS

        with open(summary, "w") as f:
            f.write(SUMMARY_HEADER % now.strftime("%B %Y"))
            f.write(SUMMARY_COLUMNS)
        created.append(_rel(paths, summary))

    gitignore = os.path.join(paths.root, ".gitignore")
    if not os.path.exists(gitignore):
        with open(gitignore, "w") as f:
            f.write(".board-watch.lock\n.tmp-*\n__pycache__/\n*.pyc\n.DS_Store\n")
        created.append(".gitignore")

    return created


def _rel(paths, p):
    return os.path.relpath(p, paths.root)


def _slug_name(name):
    keep = [c.lower() if c.isalnum() else "-" for c in (name or "profile")]
    return "".join(keep).strip("-") or "profile"


def describe(paths):
    """What exists right now — used by `board-watch status`."""
    seen = read_json(paths.seen_file, {}) or {}
    jobs = [
        (c, jid, meta)
        for c, entries in seen.items()
        if not c.startswith("_")
        for jid, meta in (entries or {}).items()
    ]
    by_status = {}
    for _, _, meta in jobs:
        st = (meta or {}).get("status", "unknown")
        by_status[st] = by_status.get(st, 0) + 1
    return {
        "root": paths.root,
        "schema": seen.get("_schema"),
        "companies_tracked": len([c for c in seen if not c.startswith("_")]),
        "jobs_tracked": len(jobs),
        "by_status": by_status,
    }
