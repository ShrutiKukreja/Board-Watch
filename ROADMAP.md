# Board-Watch — Phase-wise Delivery Plan

**Updated:** 2026-08-13 · **Design:** [DESIGN.md](DESIGN.md) · **Usage:** [README.md](README.md)

Each phase is independently testable and leaves something that works. No phase
depends on a later one.

---

## Status at a glance

| # | Phase | Delivers | Status |
|---|---|---|---|
| **1** | Engine + config schema | Detection works end to end, locally | ✅ **Done** |
| **1.5** | Raw packet writer | Detected jobs persist to disk | ⬜ Not started |
| **2** | `init` wizard | Anyone can set up in one command | ⬜ Not started |
| **3** | Packet building (LLM) | Tailored resume + drafted answers | ⬜ Not started |
| **4** | GitHub issues | Roles reach your phone | ⬜ Not started |
| **5** | Applied detection | Tracking maintains itself | ⬜ Not started |
| **6** | Routine + digest | Runs without your laptop | ⬜ Not started |
| **7** | Plugin packaging | Others can install it | ⬜ Not started |

**Usable to you after Phase 4. Usable by anyone else after Phase 7.**

---

## Phase 1 — Engine + config schema ✅

The deterministic core: find new roles, decide which matter, remember them.

**Delivered**

- `board_watch_engine/` — stdlib only, no runtime dependencies, Python 3.8+
- **7 ATS adapters** — greenhouse (incl. form questions), ashby, lever,
  smartrecruiters, workday, amazon, microsoft
- Matching — title include/exclude with `&&`, location allowlist, description keywords
- Warm/cold board detection with `backfill_days`; per-run cap
- `seen.json` v2 — per-job objects, atomic writes, transparent schema upgrade
- Self-healing run lock (stale after 2× cadence)
- Idempotent scaffold; config load + validation
- CLI — `poll` · `seed` · `scaffold` · `status`
- Daily ledger (`summary/MMM-yy.md`), upserted per run, counts seeded
- Per-day logs (`logs/ddMMyyyy.log`)
- **78 unit tests**, no network required

**Verified** — 34 boards live, ~4,300 postings, zero errors. Existing 158-job
baseline migrated intact.

**Carried into 1.5** — see below.

---

## Phase 1.5 — Raw packet writer ⬜

**Why this exists:** `poll` currently enriches a new role — pulling the full
description and, on Greenhouse, every form question — then **discards it**.
The job is marked `new` in `seen.json`, so the next poll skips it and the
enrichment is lost. Recoverable only while the posting stays open.

There is a live queue of deferred roles that will hit this.

**Deliverables**

- Write `inbox/new/<date>_<company>_<role>/job.md` — description, metadata, links
- Write `questions.md` for Greenhouse roles
- No LLM involved; pure serialisation of what `poll` already fetched

**Done when** — a non-dry-run poll leaves a readable packet on disk for every
new role, and re-running does not duplicate it.

**Size** — small. Makes Phase 3 purely additive.

---

## Phase 2 — `init` wizard ⬜

Turns three inputs into a working configuration. This is the phase that makes
the product usable by someone other than you.

**Deliverables**

- Resume (PDF/DOCX) → `config/profile/<name>.md`
- Target role in plain English → `config/companies.json` + match filters
- **The logistics questionnaire** — the ~8 answers no resume contains: work
  authorization per region, visa sponsorship, notice period, comp expectations,
  relocation, preferred locations, EEO preference, "how did you hear about us"
- Archetype resumes → `resume/archetypes/*.pdf`
- Seed `seen.json`; validate GitHub write access

**Done when** — a fresh clone plus a resume produces a configured, seeded repo
with no manual file editing.

**Note** — largely a no-op for the existing setup, which already has a populated
profile and company list. Its value is onboarding *other* people.

---

## Phase 3 — Packet building (LLM) ⬜

**Deliverables**

- Select resume bullets from the profile superset — **selection, never
  generation**; the model may not invent experience
- Draft an answer per form question, sourced from the profile
- Respect `WRITE_YOURSELF` — supply raw material, not a draft, where the company
  asks for no AI assistance
- Leave blanks where the profile has no answer, and say which field is missing
- Emit the **tailoring manifest** (bullets chosen, order) so output is
  reproducible after the PDF is deleted

**Done when** — a packet contains answers good enough to paste without editing,
and every claim traces to a line in the profile.

**Depends on** — 1.5 (packets on disk), 2 (a populated profile).

---

## Phase 4 — GitHub issues ⬜

The phase that makes it useful on a phone.

**Deliverables**

- Issue per role: `{job_id} | {Company} | {Role}`, labelled by ATS and region
- Body: apply link · archetype to use · **each answer in its own fenced code
  block** (GitHub renders a tap-to-copy button — the single most important UX
  detail in the system)
- Link rules: `blob` to view, `/raw/` to download. **Never**
  `raw.githubusercontent.com` — token-authenticated, 404s on private repos
- `new/` → `sent/`; issue number recorded in `seen.json`
- `seen.json` written **last**, after issue creation succeeds

**Done when** — a role lands on your phone and you can apply from it without
opening a laptop. Verified on a real device, both with and without the GitHub app.

---

## Phase 5 — Applied detection ⬜

**Deliverables**

- Gmail `search_threads` for ATS confirmation emails (`newer_than:2d`)
- Fuzzy-match company + role against open issues
- Confident match → close issue, move packet to `applied/`, delete outbox PDF
- Ambiguous → leave open, surface in the digest
- Manual issue close as the fallback path

**Done when** — applying to a role closes its issue with no action from you.

**Known weakness** — two open roles at the same company make matching ambiguous.
Mitigation is recency plus job ID in the packet filename; needs validation
against real mail.

**Also unlocks** — ingesting job-alert emails from Google and Meta, which is the
answer to those two unresolved boards.

---

## Phase 6 — Routine + digest ⬜

**Deliverables**

- Hourly Claude routine: clone → poll → commit → push
- 22:00 digest — ledger row + `PushNotification`
- Direct push to `main` (not a `claude/*` branch)

**Done when** — roles arrive with the laptop closed, for a week, unattended.

**Must verify first** (both cheap, both would change this phase):
- **R1** — routine cron granularity. Every existing routine is daily; hourly is unproven.
- **R5** — two existing routines write to a `claude/*` branch via `outcomes`.
  This one must push to `main` or state never lands.

---

## Phase 7 — Plugin packaging ⬜

**Deliverables**

- `.claude-plugin/plugin.json` + marketplace repo
- Slash commands: `/board-watch:init`, `:poll`, `:prep`, `:status`
- Optional `SessionStart` hook surfacing open issues
- Install docs

**Done when** — a second account installs with two commands and reaches a
working poll without reading source.

---

## Cross-cutting backlog

Not phase-bound. Ordered by value.

| Item | Why | Size |
|---|---|---|
| **Per-company match overrides** | Lets a company carry its own `include_title` / `locations_allow`. The only thing that makes Amazon (459 matches) and Microsoft (63) usable. | ~30 lines |
| **Git + first commit** | Repo is not under version control. `companies.json` has been broken twice already. | minutes |
| **Match scoring** | Rank the queue instead of boolean pass/fail — matters once `max_new_per_run` decides what you see first. | medium |
| **Interview tracking** | State stops at `applied`. Recruiter replies → interview → offer is the rest of the funnel. | Phase 8 |
| **Google / Meta** | Bot-protected; no adapter. Route via job-alert emails once Phase 5 exists. | small, after 5 |

---

## Open risks

| # | Risk | Resolve by |
|---|---|---|
| R1 | Routine cron granularity — hourly unproven | Throwaway trigger, observe 3 fires |
| R2 | Gmail connector OAuth refresh in an unattended routine | Daily trigger test before Phase 5 depends on it |
| R3 | Confirmation-email → issue matching accuracy | Validate against real mail, Phase 5 |
| R4 | GitHub mobile app PDF rendering | 5-minute device test; `/raw/` link is the fallback |
| R5 | Routine writes to a branch, not `main` | Check `outcomes` config, Phase 6 |
| R6 | PDF generation in the routine | Archetypes render at `init`, off the hot path |
| R7 | Only Greenhouse exposes form questions | Upstream limit. Ashby, Lever, Workday, Microsoft, Amazon expose none. |
| R8 | Concurrent routine runs bypass the local lock | Distributed guard if R1 shows overlap is possible |

---

## Recommended order

```
1.5  →  3  →  4      you have a working system on your phone
 ↓
 6                    it runs without you
 ↓
 5                    it tracks itself
 ↓
 2  →  7              anyone else can use it
```

Phase 2 is deliberately late: `init` should be built once a packet's real
requirements are known, rather than guessing at them.
