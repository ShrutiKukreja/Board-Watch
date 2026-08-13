"""Small helpers shared across the engine. No third-party imports."""

import html
import json
import os
import re
import tempfile
from datetime import datetime, timezone


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt=None):
    """ISO-8601 in UTC, second precision, always Z-suffixed."""
    return (dt or now_utc()).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    """Best-effort ISO-8601 parse. Returns None rather than raising.

    ATS APIs are inconsistent — Greenhouse sends '2026-08-09T14:03:00-04:00',
    Ashby sends '2026-08-09T14:03:00.000Z'. Both need to land as aware UTC.
    """
    if not s:
        return None
    s = str(s).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    s = re.sub(r"\.\d+", "", s, count=1)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def days_since(s):
    """Whole days between an ISO timestamp and now. None if unparseable."""
    dt = parse_iso(s)
    if dt is None:
        return None
    return max(0, (now_utc() - dt).days)


def strip_html(s):
    """Flatten an HTML job description into readable plain text."""
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "  - ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return "\n".join(line.rstrip() for line in s.splitlines()).strip()


def slugify(s, maxlen=48):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:maxlen].strip("-")


def write_json_atomic(path, data):
    """Write JSON via a temp file + os.replace.

    A routine can be killed between stages; a half-written seen.json would be
    unrecoverable state, so the swap has to be atomic.
    """
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except (ValueError, OSError):
        return default


def truncate(s, n):
    s = s or ""
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"
