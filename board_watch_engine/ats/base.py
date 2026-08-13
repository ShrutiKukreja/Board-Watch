"""Shared HTTP for the ATS adapters. urllib only — no requests dependency."""

import json
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
TIMEOUT = 25


class FetchError(Exception):
    """Any failure reaching or parsing a board. Carries a short, loggable reason."""


def get_json(url, data=None, headers=None, timeout=TIMEOUT):
    h = dict(UA)
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise FetchError("HTTP %s" % e.code)
    except urllib.error.URLError as e:
        raise FetchError(str(e.reason))
    except ValueError:
        raise FetchError("malformed JSON")
    except OSError as e:
        raise FetchError(str(e))


def first(*vals):
    """First non-empty value, else ''."""
    for v in vals:
        if v:
            return v
    return ""
