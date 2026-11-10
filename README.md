# Board-Watch (Work-In-Progress)

Polls ATS job boards for roles matching your profile, builds a ready-to-submit
application packet the moment one appears, and tracks what you've applied to.

**Design:** [DESIGN.md](DESIGN.md) · **Status:** Phase 1 of 7 complete

```
python3 -m board_watch_engine poll --dry-run
```

No dependencies. Stdlib only, Python 3.8+. Nothing to install.

---

## Commands

| Command | What it does |
|---|---|
| `poll` | One cycle: fetch every board, match, detect new roles |
| `poll --dry-run` | Same, but writes nothing |
| `poll --tier 1` | Only the highest-priority companies |
| `seed` | Baseline every currently-open posting without producing packets |
| `scaffold` | Create any missing folders and config files |
| `status` | What's tracked right now |

Global flags: `--root <path>` (data root), `-v` (verbose). Both work before or
after the subcommand.

---

## Layout

The repo root is both the code root and the data root.

```
board_watch_engine/         the engine
config/
  config.json        cadence, digest time, caps
  companies.json     which boards to poll + your match filters
  profile/<name>.md  ★ single source of truth for every answer
resume/
  source/            your original resume
  archetypes/        role-variant PDFs, pre-positioned on your phone
inbox/
  new/ sent/ applied/   packets; the directory IS the status
  seen.json          ★ state of record
outbox/              ephemeral tailored resumes, deleted once applied
summary/MMM-yy.md    one ledger row per day, upserted every run
logs/ddMMyyyy.log    one log file per day
```

### The ledger

`summary/MMM-yy.md` carries one row per day:

```
| Date | Role | New | Seeded | Sent | Applied | Companies |
| 2026-08-09 | AI Product Manager | 4 | 158 | 3 | 2 | Anthropic, Sierra +2 more |
```

`poll` **upserts** today's row on every run rather than appending, so 24 hourly
polls leave one row, not 24. Jobs are attributed by timestamp — `applied_at` for
the Applied column, `first_seen` for the rest.

---

## Configuration

### `config/companies.json`

```json
{ "name": "Anthropic", "region": "USA", "ats": "greenhouse",
  "token": "anthropic", "tier": 1 }
```

Workday is self-hosted per tenant, so its token has three parts —
`tenant/host/site` — and huge boards may set `search` to narrow server-side
before the local filters run:

```json
{ "name": "Nvidia", "ats": "workday",
  "token": "nvidia/wd5/NVIDIAExternalCareerSite",
  "search": "product manager", "tier": 2 }
```

`ats` is one of `greenhouse`, `ashby`, `lever`, `smartrecruiters`, `workday`, or
`manual`.
`token` is the board slug. Entries marked `manual` are reported at the end of
every run as unresolved — to resolve one:

1. Open the company's careers page
2. DevTools → Network → XHR → reload
3. Find the request to `boards-api.greenhouse.io`, `api.ashbyhq.com`, or
   `api.lever.co` — the slug is in the URL
4. Add it with the right `ats`, then run `seed` so it doesn't alert on the
   entire existing board

**Match filters**, same file:

- `include_title` — substring match. `"a && b"` requires both terms.
- `exclude_title` — kills the match outright
- `locations_allow` — empty means everywhere
- `require_any_keyword_in_description` — e.g. `["agents", "evals"]`

### `config/config.json`

| Key | Default | Meaning |
|---|---|---|
| `cadence` | `hourly` | Poll frequency; sets the lock's stale window |
| `digest_time` | `22:00` | Daily summary + push notification |
| `max_new_per_run` | `10` | Hard cap on new packets per cycle |
| `backfill_days` | `7` | On a **cold** board, only package postings this recent |
| `tier` | `3` | Poll companies at this tier or better |

---

## How new roles are detected

Each poll diffs every matching posting against `inbox/seen.json`. An unseen
posting becomes a packet only if:

- the company **already has tracked entries** (a *warm* board) — anything unseen
  must have appeared since the last poll, so age is irrelevant; **or**
- the company is **cold** and the posting is within `backfill_days`

Cold-board backfill exists so day one doesn't open a hundred issues for roles
that have been open for months. Once a board is warm, nothing is ever dropped
for being old — which matters because posting dates aren't trustworthy
(Greenhouse falls back to `updated_at`, SmartRecruiters exposes none).

Everything matched but not packaged is recorded as `seeded`, so it never
resurfaces as new.

---

## State

`inbox/seen.json`, schema v2:

```json
{ "_schema": 2,
  "Anthropic": {
    "5251866008": {
      "applied": false,
      "status": "sent",
      "title": "Product Manager, Claude Tag",
      "first_seen": "2026-08-09T14:03:00Z",
      "issue": 42
    }}}
```

`status` moves `seeded | new → sent → applied`. It's written **last**, only
after the side effect it records has succeeded — so a crash costs a delayed
alert, never a duplicate issue.

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

59 tests, no network required.

---

## Known limits

- **Only Greenhouse exposes application form questions.** Ashby, Lever, Workday
  and SmartRecruiters don't publish their forms, so those packets carry the job and
  the link but no question list.
- **Detection speed is your poll interval.** Hourly is the default; see
  DESIGN.md §3.1 for why not faster.
- Boards change slugs occasionally. A company silently reporting 0 jobs for days
  usually means its token moved.
