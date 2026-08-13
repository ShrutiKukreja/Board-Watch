# Board-Watch — Technical Design

**Status:** Draft for review · **Date:** 2026-08-09 · **Supersedes:** `jobwatch/README.md`

---

## 1. Problem

A qualified candidate loses roles to latency, not to merit. Postings are reviewed
in arrival order; being in the first ~50 applicants materially changes whether a
resume is read. But applying well takes ~30 minutes per role — re-typing the same
twelve logistics answers, re-tailoring a resume, re-drafting the same three essays.

Board-Watch collapses that to ~2 minutes without lowering application quality, and
does it while the user is anywhere — phone, no laptop, no local machine running.

**Explicit non-goal:** automated submission. Every application is reviewed and
submitted by the user.

---

## 2. Product shape

```
Hourly:  poll ATS APIs → detect new matching roles → build an application packet
         → open a GitHub issue → GitHub notifies the phone

User:    tap issue → tap-copy each answer → attach resume → submit

Auto:    ATS confirmation email detected → issue auto-closed → packet archived

22:00:   daily ledger row + push notification
```

Three user inputs, total: **resume, target role, a private GitHub repo.**
No API keys. No secrets. No server.

---

## 3. Architecture

| Layer | Choice | Rationale |
|---|---|---|
| **Compute** | Claude routine (cloud cron) | Laptop-independent. Verified working in this account. |
| **Storage** | Private GitHub repo | Free, versioned, auditable, no database, syncs everywhere. |
| **Delivery** | GitHub Issues | Deep-linking push, tap-to-copy code blocks, open/closed *is* the state. |
| **Applied detection** | Gmail connector (read) | ATS confirmation emails close issues automatically. Optional. |
| **Digest** | Claude `PushNotification` | Text-only; used where there is nothing to link to. |
| **Distribution** | Claude Code plugin + marketplace | Two commands to install; no per-user infrastructure. |

```
┌──────────────────────────────────────────┐
│  Claude Routine (cloud, hourly)          │
│  ├─ clone private repo                   │
│  ├─ poll ATS APIs        (deterministic) │
│  ├─ diff vs seen.json    (deterministic) │
│  ├─ tailor + draft       (LLM)           │
│  ├─ open GitHub issues                   │
│  └─ commit + push                        │
└──────────────────────────────────────────┘
         │                     ▲
         ▼                     │
  ┌─────────────┐      ┌───────────────┐
  │ GitHub repo │      │ Gmail (read)  │
  │ + Issues    │      │ confirmations │
  └─────────────┘      └───────────────┘
         │
         ▼  push notification + deep link
     ┌────────┐
     │ Phone  │
     └────────┘
```

### 3.1 Rejected alternatives

| Option | Why not |
|---|---|
| GitHub Actions as poller | ~2,880 billable min/mo at 15-min cadence on a private repo (~$9.50). Cron lag 5–20 min, no SLA. |
| `CronCreate` | Session-only, in-memory, fires only when REPL idle, 7-day expiry. |
| `scheduled-tasks` MCP | Requires the desktop app to be open. |
| macOS `launchd` | Dies when the Mac sleeps. |
| Composio | Requires every user to create a third-party account. |
| Gmail app password + SMTP/IMAP | Grants full account access; a secret to store; superseded by the connector. |
| Hooks as scheduler | Only fire during a Claude Code session. No event exists when idle. |

Hooks remain useful at the edges — a `SessionStart` hook surfacing open issues — but
are not load-bearing.

---

## 4. Repository layout

**One repo. Engine and data share a root** — the routine clones it, runs from it,
and commits back to it. Deviations from the original spec are flagged in §4.1.

```
Board-Watch/                     # ← repo root IS the data root
├── DESIGN.md
├── README.md
├── board_watch_engine/          # the engine — stdlib only, no runtime deps
│   ├── cli.py                   # poll | seed | scaffold | status
│   ├── poll.py                  # the pipeline
│   ├── state.py                 # seen.json v2 + run lock
│   ├── scaffold.py  config.py  matching.py
│   ├── models.py  paths.py  util.py  logging_setup.py
│   └── ats/                     # greenhouse · ashby · lever · smartrecruiters · workday
├── tests/
├── config/
│   ├── config.json              # cadence, digest time, tz, caps, model
│   ├── companies.json           # ATS mapping + match filters
│   └── profile/
│       └── <name>.md            # ★ SINGLE SOURCE OF TRUTH
├── resume/
│   ├── source/                  # original upload; parsed once, then archived
│   └── archetypes/              # AI-PM.pdf, Platform-PM.pdf — pre-positioned
├── inbox/
│   ├── new/                     # packet built, issue not yet opened
│   ├── sent/                    # issue open, awaiting application
│   ├── applied/                 # issue closed
│   └── seen.json                # ★ state of record
├── outbox/                      # ephemeral bespoke PDFs; deleted on close
├── summary/
│   └── MMM-yy.md                # one row per day, upserted every run
└── logs/
    └── ddMMyyyy.log             # one file per day
```

All paths resolve from a single root (`board_watch_engine/paths.py`), chosen as
`--root` > `$BOARD_WATCH_ROOT` > cwd. Nothing else in the engine builds a path,
so splitting data into a second repo later costs one flag, not a refactor.

### 4.1 Deviations from the original spec

| Spec | Built | Why |
|---|---|---|
| `summary/mmm-dd.md` (step 8) | `summary/MMM-yy.md` | Step 1 said monthly; daily files fragment the ledger. Monthly file, daily rows. |
| "pending folder" (step 5) | `inbox/new/` | Step 1 named `new`. Directory *is* status — no separate field to desync. |
| `seen.json: {company: {id: bool}}` | Object per job | Needs issue number, packet path, first-seen. `applied` stays the primary field. |
| `jobwatch/` + `profile/` as separate trees | Folded into the single repo | Two roots meant two sources of truth for the company list and the profile. `jobwatch/` is retired; `board_watch_engine/` supersedes it. |

---

## 5. State

### 5.1 `seen.json` v2

```json
{
  "Anthropic": {
    "4567890": {
      "applied": false,
      "status": "sent",
      "title": "Product Manager, Claude Code",
      "first_seen": "2026-08-09T14:03:00Z",
      "issue": 42,
      "packet": "2026-08-09_anthropic_product-manager-claude-code",
      "archetype": "AI-PM"
    }
  }
}
```

`status` ∈ `seeded | new | sent | applied`. `seeded` entries never produce packets —
they are the pre-existing board contents captured at init.

### 5.2 Migration v1 → v2

Existing file is `{company: [id, id, ...]}` with real seeded history worth keeping.

```
for company, ids in v1:
    for id in ids:
        v2[company][id] = {applied: false, status: "seeded", first_seen: <mtime>}
```

Run once, idempotent, guarded by a `_schema: 2` key.

### 5.3 Ordering guarantee

`seen.json` is written **last**, only after the GitHub issue is created. If issue
creation fails, the job stays unseen and is retried next hour. The failure mode is a
delayed alert, never a duplicate issue.

---

## 6. Pipeline

### 6.1 `poll` (hourly)

| # | Stage | LLM? | Notes |
|---|---|---|---|
| 1 | `acquire_lock` | — | PID + timestamp; stale after 2× cadence |
| 2 | `ensure_scaffold` | — | Creates any missing folder/file (spec step 1) |
| 3 | `ingest_closures` | — | Closed issues → `applied/`, delete outbox PDF |
| 4 | `ingest_confirmations` | — | Gmail search → auto-close matches (§8) |
| 5 | `fetch_boards` | — | Parallel, 12 threads, per-ATS adapters |
| 6 | `match` | — | Title include/exclude, location, description keywords |
| 7 | `diff` | — | Against `seen.json` |
| 8 | `enrich` | — | Greenhouse only: full description + form questions |
| 9 | `build_packet` | **yes** | Select bullets, draft answers |
| 10 | `publish` | — | Create GitHub issue |
| 11 | `commit_state` | — | Write `seen.json`, commit, push to `main` |

Stages 1–8 and 10–11 are deterministic Python. Only stage 9 uses the model, and only
when there is at least one new job — most runs skip it entirely.

### 6.2 The ledger — `summary/MMM-yy.md`

One row per day, **upserted by `poll` on every run** rather than appended, so the
day's figures stay current across all 24 hourly cycles and re-running never
duplicates a row.

```
| Date | Role | New | Seeded | Sent | Applied | Companies |
| 2026-08-09 | AI Product Manager | 4 | 158 | 3 | 2 | Anthropic, Sierra +2 more |
```

`Seeded` is counted deliberately. Baselining a board is the single largest event
in the ledger's life; omitting it makes day one read as though nothing happened.

Rows are attributed by timestamp: `applied_at` for the Applied column,
`first_seen` for the rest — so a job counts on the day it actually moved.

### 6.2.1 `digest` (22:00 local)

Reads the day's row and pushes it. Notification:
`"4 new roles today · 2 applied · 3 still open"`.

### 6.3 `init` (once)

Resume → parse → `profile/<name>.md`. Target role → generate `companies.json`.
Ask the §9.2 questionnaire. Render archetype resumes. **Seed `seen.json`** so the first
poll does not open 100 issues. Validate GitHub write access.

---

## 7. Issue format

The issue is the entire mobile UI. Format is load-bearing.

```
Title:  4567890 | Anthropic | Product Manager, Claude Code
Labels: board-watch · ats:greenhouse · region:usa
```

Body:

1. **Apply** — the `apply_url`, first line, tappable.
2. **Resume** — `Use archetype: **AI-PM**`, or for bespoke packets, two labelled links:
   - 📄 View → `github.com/{o}/{r}/blob/main/outbox/{id}.pdf`
   - ⤓ Download → `github.com/{o}/{r}/raw/main/outbox/{id}.pdf`
3. **Answers** — one section per form question. **Each answer inside a fenced code
   block**, which renders a tap-to-copy button on GitHub. This is the single most
   important UX detail in the system.
4. **Write-yourself flags** — questions matching the `WRITE_YOURSELF` pattern get
   🚫 and raw material instead of a draft. Companies asking for no AI assistance are
   respected.

### 7.1 Link rules

- **Never** `raw.githubusercontent.com` — token-authenticated, expires, 404s on private repos.
- **Always** `github.com/{owner}/{repo}/raw/{branch}/{path}` — session-cookie auth, triggers download.

---

## 8. Applied detection

Primary path is automatic. Every major ATS sends a confirmation email on submission.

```
search_threads(query = 'newer_than:2d ("thank you for applying"
                OR "application received" OR "we received your application")')
  → extract company + role
  → fuzzy match against open board-watch issues
  → confident match: close issue, move packet, delete outbox PDF
  → ambiguous: leave open, list in digest
```

Fallbacks, in order: manual issue close; the 22:00 digest nudging still-open issues.

**Known weakness:** two open roles at the same company make matching ambiguous.
Mitigation is recency plus job ID in the packet filename — to be validated against
real mail in Phase 5.

Gmail is **read-only** here. It sends nothing. It is optional; without it the system
works with manual issue closing.

---

## 9. Configuration

### 9.1 Required (3)

| Input | Form |
|---|---|
| Resume | PDF/DOCX dropped in `resume/source/` |
| Target role | Plain English — `"AI Product Manager"` |
| Private repo | Created during `init` |

### 9.2 The logistics questionnaire (~8, one-time)

**Not derivable from any resume**, and mandatory on nearly every ATS form:

work authorization per region · visa sponsorship required · notice period ·
current & expected comp per currency · relocation · preferred locations ·
EEO self-identification preference · "how did you hear about us" default

Without these, generated answers have blanks in exactly the required fields.

### 9.3 Defaults

`cadence: hourly` · `digest: 22:00 local` · `max_new_issues_per_run: 10` ·
`model: claude-sonnet-5` · `regions: all`

### 9.4 Generated, never asked

`profile/<name>.md` · `companies.json` · match filters · seeded `seen.json` ·
folder scaffold · archetype resumes

---

## 10. Resume model

```
resume/source/resume.pdf     parsed once at init, archived, never read again
        ↓
config/profile/<name>.md     ★ single source of truth — a superset of every
                               bullet, project and metric; larger than 2 pages
        ↓
resume/archetypes/*.pdf      2–3 role variants, generated at init,
                               saved to the user's phone once
        ↓
outbox/<jobid>.pdf           bespoke, rare, ephemeral, deleted on close
```

**Tailoring is selection, not generation.** The model chooses which real bullets to
surface and in what order. It may not invent experience. This keeps the profile
authoritative and the output truthful.

**Why archetypes are the default.** Delivering a file to a phone mid-application costs
~6 taps and has a failure point in every path. A pre-positioned archetype costs 2 taps
and cannot fail. Recruiters skim a resume for role fit and keywords, which an archetype
captures; the per-job intelligence pays off in the *answers*, which need no file
handling at all.

**Bespoke packets** retain a small tailoring manifest (bullets selected, order) in
`applied/`. The PDF is deleted, but remains byte-reproducible from profile + manifest —
which matters when an interviewer references your resume six weeks later. Store the
inputs, not the outputs. This also bounds repo growth.

---

## 11. Failure model

| Failure | Behaviour |
|---|---|
| ATS API down | Logged per company, others continue, retry next hour |
| Issue creation fails | Job stays unseen, retried; **never duplicates** |
| Overlapping runs | Lock file; stale locks broken after 2× cadence |
| First run floods | `init` seeds; `max_new_issues_per_run` caps regardless |
| Gmail unavailable | Auto-close degrades to manual close; core unaffected |
| Board slug changes | Company silently reports zero; digest flags any company at 0 for 7 days |
| Repo growth | Outbox pruned on close; `applied/` archived yearly |

---

## 12. Security & privacy

- **No secrets anywhere.** No API keys, no passwords, no tokens in the repo.
- `profile/<name>.md` contains PII and comp expectations. **Private repo is mandatory** —
  `init` refuses to configure a public repo.
- Issue closure is authenticated by GitHub. There is no spoofing surface (contrast the
  email-reply design, where anyone knowing a job ID could forge a status change).
- Gmail scope is read + draft. Nothing is sent.
- ATS endpoints polled are the same public JSON their own careers pages consume.

---

## 13. Cost

| Item | Cost |
|---|---|
| Compute (routine) | ~14–24 runs/day, mostly no-ops |
| LLM | Only on new jobs — a few per day |
| GitHub (private repo + issues) | $0 |
| Infrastructure | $0 |

Cheap-loop/expensive-loop separation is deliberate: polling and diffing are ~40s of
deterministic Python; only packet-building invokes the model.

---

## 14. Open risks

Ordered by impact. Each is cheap to resolve; none blocks Phase 1.

| # | Risk | Resolution |
|---|---|---|
| R1 | Routine cron granularity — all existing routines are daily; hourly unverified | Create a throwaway hourly trigger, observe 3 fires |
| R2 | Gmail connector OAuth refresh in an unattended routine, days later | Test with a daily trigger before depending on it (Phase 5) |
| R3 | Confirmation-email → issue matching accuracy | Validate against real mail, Phase 5 |
| R4 | GitHub mobile app PDF blob rendering | 5-minute manual test; `/raw/` link is the fallback |
| R5 | Routine writes to `main` vs a `claude/*` branch | Two existing routines carry an `outcomes` branch config; must push direct to `main` |
| R6 | PDF generation in the routine | Archetypes render at `init`, off the hot path. Prefer pure-Python (`fpdf2`); fall back to a GitHub Action renderer |
| R7 | Ashby/Lever/SmartRecruiters expose no form questions | Upstream limitation. Issue links to the form and says so. Greenhouse only. |

---

## 15. Phases

Each phase is independently testable and leaves something that works.

| # | Phase | Done when |
|---|---|---|
| 1 | **Engine + config schema** | Scaffold created, `seen.json` migrated, poller runs locally, no LLM, no issues |
| 2 | **`init` wizard** | Resume → profile; role → `companies.json`; questionnaire; archetypes; seeded |
| 3 | **Packet building** | Answers drafted from profile; write-yourself flags respected |
| 4 | **GitHub issues** | Issue opens with copy-blocks and correct links; verified on a phone |
| 5 | **Applied detection** | Confirmation email auto-closes; packet moves; outbox pruned |
| 6 | **Routine + digest** | Hourly trigger live; 22:00 ledger row + push |
| 7 | **Plugin packaging** | Marketplace repo; clean install on a second account |

R1 and R5 should be checked during Phase 1 — both are cheap and both would change
Phase 6.

---

## 16. Reused from `jobwatch/watch.py`

Roughly a third of the engine exists and is sound:

- Four ATS adapters — Greenhouse, Ashby, Lever, SmartRecruiters
- Greenhouse enrichment, including the real application form questions
- `matches()` — title include/exclude with `&&`, location, description keywords
- `WRITE_YOURSELF` — the no-AI-assistance question detector
- `strip_html`, `slugify`, threaded fetch

Refactored into the new layout, not rewritten. Removed: ntfy, macOS notifications,
the flat `inbox/` packet writer, `--tier` (folded into config).
