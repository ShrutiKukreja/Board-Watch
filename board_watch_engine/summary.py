"""The daily ledger — summary/MMM-yy.md, one row per day.

Rows are upserted by date rather than appended, because `poll` runs hourly and
the day's figures change with every run. Re-running is therefore safe: today's
row is rewritten in place, never duplicated.
"""

import os
import re

from .state import APPLIED, NEW, SEEDED, SENT
from .util import now_utc, parse_iso

COLUMNS = ("Date", "Role", "New", "Seeded", "Sent", "Applied", "Companies")
HEADER = "| " + " | ".join(COLUMNS) + " |\n|" + "---|" * len(COLUMNS) + "\n"

_ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|")


def tally(state, on_date):
    """Count what happened on `on_date`, by status.

    `seeded` is included deliberately: a board being baselined is the single
    largest event in the ledger's life, and omitting it makes day one look like
    nothing happened.
    """
    counts = {NEW: 0, SEEDED: 0, SENT: 0, APPLIED: 0}
    companies = set()

    for company, _job_id, meta in state.entries():
        meta = meta or {}
        status = meta.get("status")

        if _same_day(meta.get("applied_at"), on_date):
            counts[APPLIED] += 1
            companies.add(company)
            continue

        if not _same_day(meta.get("first_seen"), on_date):
            continue
        if status in counts:
            counts[status] += 1
            companies.add(company)

    return counts, sorted(companies)


def row_for(state, cfg, on_date):
    counts, companies = tally(state, on_date)
    role = ", ".join(cfg.target_roles) if cfg.target_roles else "—"
    return {
        "Date": on_date.strftime("%Y-%m-%d"),
        "Role": role,
        "New": str(counts[NEW]),
        "Seeded": str(counts[SEEDED]),
        "Sent": str(counts[SENT]),
        "Applied": str(counts[APPLIED]),
        "Companies": _companies_cell(companies),
    }


def upsert(paths, state, cfg, on_date=None):
    """Write today's row into summary/MMM-yy.md, replacing any existing one."""
    on_date = on_date or now_utc()
    path = paths.summary_file(on_date)
    row = row_for(state, cfg, on_date)
    line = "| " + " | ".join(row[c] for c in COLUMNS) + " |\n"

    lines = _read(path, on_date)
    for i, existing in enumerate(lines):
        m = _ROW.match(existing)
        if m and m.group(1) == row["Date"]:
            if existing == line:
                return path, False
            lines[i] = line
            _write(path, lines)
            return path, True

    lines.append(line)
    _write(path, lines)
    return path, True


def _read(path, on_date):
    if not os.path.exists(path):
        return [
            "# Application ledger — %s\n" % on_date.strftime("%B %Y"),
            "\n",
            HEADER,
        ]
    with open(path) as f:
        lines = f.readlines()
    if not any(line.startswith("| Date |") for line in lines):
        lines.append(HEADER)
    return lines


def _write(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.writelines(lines)


def _companies_cell(companies, limit=6):
    if not companies:
        return "—"
    if len(companies) <= limit:
        return ", ".join(companies)
    return "%s +%d more" % (", ".join(companies[:limit]), len(companies) - limit)


def _same_day(stamp, on_date):
    dt = parse_iso(stamp)
    return dt is not None and dt.date() == on_date.date()
