"""seen.json — the state of record — plus the run lock.

Schema v2:

    {
      "_schema": 2,
      "Anthropic": {
        "4567890": {
          "applied": false,
          "status": "sent",
          "title": "Product Manager, Claude Code",
          "first_seen": "2026-08-09T14:03:00Z",
          "issue": 42,
          "packet": "2026-08-09_anthropic_product-manager",
          "archetype": "AI-PM"
        }
      }
    }

status transitions: seeded | new -> sent -> applied

`seeded` entries were open when the user set up and deliberately never produce a
packet. Everything else is written only *after* the corresponding side effect has
succeeded, so a crash costs a delayed alert, never a duplicate.
"""

import errno
import os
import time
from datetime import timedelta

from . import SCHEMA_VERSION
from .util import days_since, iso, now_utc, read_json, write_json_atomic

SEEDED = "seeded"
NEW = "new"
SENT = "sent"
APPLIED = "applied"


class SeenState:
    def __init__(self, path, data=None):
        self.path = path
        self.data = data if data is not None else {"_schema": SCHEMA_VERSION}
        self.dirty = False

    # -- load / save ---------------------------------------------------------

    @classmethod
    def load(cls, path):
        raw = read_json(path, None)
        if raw is None:
            return cls(path)
        data, migrated = migrate(raw)
        st = cls(path, data)
        st.dirty = migrated
        return st

    def save(self):
        self.data["_schema"] = SCHEMA_VERSION
        write_json_atomic(self.path, self.data)
        self.dirty = False

    # -- reads ---------------------------------------------------------------

    def companies(self):
        return [k for k in self.data if not k.startswith("_")]

    def get(self, company, job_id):
        return (self.data.get(company) or {}).get(str(job_id))

    def knows(self, company, job_id):
        return self.get(company, job_id) is not None

    def entries(self):
        """Yield (company, job_id, meta) for every tracked job."""
        for company in self.companies():
            for job_id, meta in (self.data.get(company) or {}).items():
                yield company, job_id, meta

    def by_status(self, status):
        return [
            (c, j, m) for c, j, m in self.entries()
            if (m or {}).get("status") == status
        ]

    def open_issues(self):
        """Jobs whose issue is still open — i.e. not yet applied to."""
        return [
            (c, j, m) for c, j, m in self.entries()
            if (m or {}).get("status") == SENT and (m or {}).get("issue")
        ]

    def counts(self):
        out = {}
        for _, _, m in self.entries():
            st = (m or {}).get("status", "unknown")
            out[st] = out.get(st, 0) + 1
        return out

    # -- writes --------------------------------------------------------------

    def record(self, company, job_id, status, **fields):
        job_id = str(job_id)
        bucket = self.data.setdefault(company, {})
        entry = bucket.get(job_id) or {"first_seen": iso()}
        entry["status"] = status
        entry["applied"] = status == APPLIED
        for k, v in fields.items():
            if v is not None:
                entry[k] = v
        bucket[job_id] = entry
        self.dirty = True
        return entry

    def seed(self, company, job_id, title=None, posted_at=None):
        if self.knows(company, job_id):
            return None
        return self.record(
            company, job_id, SEEDED, title=title, posted_at=posted_at
        )

    def mark_applied(self, company, job_id):
        entry = self.get(company, job_id)
        if not entry:
            return None
        entry["status"] = APPLIED
        entry["applied"] = True
        entry["applied_at"] = iso()
        self.dirty = True
        return entry

    def stale_open(self, days):
        """Open jobs first seen more than `days` ago — the digest nudges these."""
        out = []
        for c, j, m in self.open_issues():
            age = days_since((m or {}).get("first_seen"))
            if age is not None and age >= days:
                out.append((c, j, m, age))
        return out


# -- migration ---------------------------------------------------------------


def migrate(raw):
    """v1 {company: [id, ...]} -> v2. Returns (data, changed).

    The v1 file is a real seed baseline; discarding it would make the next poll
    treat every currently-open posting as new.
    """
    if not isinstance(raw, dict):
        return {"_schema": SCHEMA_VERSION}, True

    if raw.get("_schema") == SCHEMA_VERSION:
        return raw, False

    out = {"_schema": SCHEMA_VERSION}
    stamp = iso()
    changed = False

    for company, value in raw.items():
        if company.startswith("_"):
            continue
        if isinstance(value, list):
            changed = True
            out[company] = {
                str(job_id): {
                    "applied": False,
                    "status": SEEDED,
                    "first_seen": stamp,
                }
                for job_id in value
            }
        elif isinstance(value, dict):
            bucket = {}
            for job_id, meta in value.items():
                if isinstance(meta, dict):
                    bucket[str(job_id)] = _normalise(meta, stamp)
                else:
                    # {"jobid": true/false} — the shape in the original spec.
                    changed = True
                    applied = bool(meta) if not isinstance(meta, str) else (
                        meta.strip().lower() in ("true", "applied", "yes", "1")
                    )
                    bucket[str(job_id)] = {
                        "applied": applied,
                        "status": APPLIED if applied else SEEDED,
                        "first_seen": stamp,
                    }
            out[company] = bucket
    return out, changed or raw.get("_schema") != SCHEMA_VERSION


def _normalise(meta, stamp):
    meta = dict(meta)
    meta.setdefault("first_seen", stamp)
    meta.setdefault("applied", meta.get("status") == APPLIED)
    meta.setdefault("status", APPLIED if meta.get("applied") else SEEDED)
    return meta


# -- lock --------------------------------------------------------------------


class LockBusy(Exception):
    pass


class RunLock:
    """Exclusive run lock that expires.

    A routine can be killed without unwinding, so a lock that outlives its run
    would wedge the service permanently. Anything older than `stale_after` is
    assumed dead and broken.
    """

    def __init__(self, path, stale_after_minutes=120):
        self.path = path
        self.stale_after = timedelta(minutes=stale_after_minutes)
        self.acquired = False

    def acquire(self):
        try:
            self._create()
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
            if not self._is_stale():
                raise LockBusy("another run holds %s" % self.path)
            self.break_stale()
            self._create()
        self.acquired = True
        return self

    def _create(self):
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "w") as f:
            f.write("%d %s\n" % (os.getpid(), iso()))

    def _is_stale(self):
        try:
            age = time.time() - os.path.getmtime(self.path)
        except OSError:
            return True
        return age > self.stale_after.total_seconds()

    def break_stale(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def release(self):
        if self.acquired:
            try:
                os.unlink(self.path)
            except OSError:
                pass
            self.acquired = False

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False


def lock_for(paths, cfg):
    """Stale window is two cadence periods — long enough to never race a healthy
    run, short enough that a crash self-heals within one cycle."""
    return RunLock(paths.lock_file, stale_after_minutes=cfg.cadence_minutes * 2)


def utcnow_iso():
    return iso(now_utc())
