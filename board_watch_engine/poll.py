"""The poll pipeline.

Phase 1 implements the deterministic stages only:

    acquire_lock -> ensure_scaffold -> fetch_boards -> match -> diff -> commit_state

Stages that need the model (packet building) or an external surface (GitHub
issues, Gmail confirmations) land in later phases. New jobs are therefore
recorded with status `new` and deliberately *not* advanced to `sent` — there is
nothing to deliver them yet, and marking them sent would lose them.
"""

import concurrent.futures as cf
import os
from dataclasses import dataclass, field
from typing import List

from . import ats as ats_registry
from . import summary
from .logging_setup import get as log
from .matching import is_fresh, matches
from .models import Hit
from .scaffold import ensure_scaffold
from .state import NEW, SEEDED, SeenState
from .util import now_utc


@dataclass
class BoardResult:
    company: str
    total: int = 0
    matched: int = 0
    fresh: int = 0
    error: str = ""


@dataclass
class PollResult:
    boards: List[BoardResult] = field(default_factory=list)
    new_hits: List[Hit] = field(default_factory=list)
    seeded: int = 0
    capped: int = 0
    manual: List[str] = field(default_factory=list)
    dry_run: bool = False
    seed_mode: bool = False

    @property
    def errors(self):
        return [b for b in self.boards if b.error]

    @property
    def polled(self):
        return len(self.boards)

    def summary_line(self):
        if self.seed_mode:
            return "Seeded %d postings across %d boards." % (self.seeded, self.polled)
        if not self.new_hits:
            return "No new roles."
        return "%d new role%s." % (
            len(self.new_hits), "" if len(self.new_hits) == 1 else "s"
        )


def poll(paths, cfg, board, dry_run=False, seed=False, tier=None, workers=12):
    """Run one poll cycle. Caller owns the lock."""
    logger = log()
    tier = cfg.tier if tier is None else tier

    created = ensure_scaffold(paths)
    if created:
        logger.info("scaffold: created %s", ", ".join(created))

    state = SeenState.load(paths.seen_file)
    if state.dirty:
        logger.info("state: migrated seen.json to schema v2")

    targets = board.resolvable(tier, ats_registry.known())
    manual = board.manual()
    result = PollResult(dry_run=dry_run, seed_mode=seed,
                        manual=[c.name for c in manual])

    logger.info(
        "polling %d board%s at tier <= %d (%d unresolved)",
        len(targets), "" if len(targets) == 1 else "s", tier, len(manual),
    )

    for company, jobs, err in _fetch_all(targets, workers):
        br = BoardResult(company=company.name, total=len(jobs))
        if err:
            br.error = str(err)
            logger.warning("  x %-24s %s", company.name, err)₹
            result.boards.append(br)
            continue

        hits = [j for j in jobs if matches(j, board.match)]
        br.matched = len(hits)
        unknown = [j for j in hits if not state.knows(company.name, j.id)]

        if seed:
            for j in hits:
                if state.seed(company.name, j.id, title=j.title,
                              posted_at=j.posted_at):
                    result.seeded += 1
        else:
            fresh = [j for j in unknown if _wanted(j, cfg, state, company)]
            br.fresh = len(fresh)
            for j in fresh:
                result.new_hits.append(Hit(company=company, job=j))
            # Anything matched but not selected is still recorded, so it never
            # resurfaces as "new" on a later run.
            for j in unknown:
                if j not in fresh:
                    state.seed(company.name, j.id, title=j.title,
                               posted_at=j.posted_at)
                    result.seeded += 1

        logger.info(
            "  . %-24s %3d jobs, %2d match, %s",
            company.name, br.total, br.matched,
            ("%d NEW" % br.fresh) if br.fresh else "no change",
        )
        result.boards.append(br)

    # Cap before enrichment — the extra request per job is the expensive part.
    if len(result.new_hits) > cfg.max_new_per_run:
        result.capped = len(result.new_hits) - cfg.max_new_per_run
        result.new_hits = result.new_hits[: cfg.max_new_per_run]
        logger.warning(
            "capped at %d new roles this run (%d deferred to next cycle)",
            cfg.max_new_per_run, result.capped,
        )

    for hit in result.new_hits:
        _enrich(hit)
        if not dry_run:
            state.record(
                hit.company.name, hit.job.id, NEW,
                title=hit.job.title, posted_at=hit.job.posted_at,
            )

    if dry_run:
        logger.info("dry run — seen.json not written")
    else:
        if state.dirty:
            state.save()
            logger.info("state: wrote %s", paths.seen_file)
        # Upserted every run, not appended, so the day's row stays current
        # across all 24 polls rather than accumulating duplicates.
        path, changed = summary.upsert(paths, state, cfg)
        if changed:
            logger.info("ledger: updated %s", os.path.relpath(path, paths.root))

    return result


def _wanted(job, cfg, state, company):
    """Whether an unseen posting should become a packet.

    Backfill only applies while the board is cold. Once a company has tracked
    entries, every genuinely new posting is wanted regardless of age.
    """
    if state.data.get(company.name):
        return True
    return is_fresh(job, cfg.backfill_days)


def _enrich(hit):
    """Fetch the description and, on Greenhouse, the real form questions."""
    logger = log()
    before = hit.job.questions
    ats_registry.enrich(hit.company.ats, hit.job)
    if hit.job.error:
        logger.warning(
            "  ! enrich failed %s %s: %s",
            hit.company.name, hit.job.id, hit.job.error,
        )
    elif before is None and hit.job.questions is not None:
        logger.debug(
            "  + %s %s: %d form questions",
            hit.company.name, hit.job.id, len(hit.job.questions),
        )
    return hit


def _fetch_all(targets, workers):
    """Poll every board in parallel; yield (company, jobs, error)."""
    if not targets:
        return []

    def work(company):
        try:
            jobs = ats_registry.fetch(
                company.ats, company.token, search=company.search
            )
            return company, jobs, None
        except Exception as e:  # noqa: BLE001 — one bad board must not stop the run
            return company, [], e

    with cf.ThreadPoolExecutor(min(workers, len(targets))) as ex:
        return list(ex.map(work, targets))


def seed_only(paths, cfg, board, tier=None):
    """Baseline every currently-open posting without producing packets."""
    return poll(paths, cfg, board, dry_run=False, seed=True, tier=tier)


def stats(state):
    counts = state.counts()
    return {
        "tracked": sum(counts.values()),
        "seeded": counts.get(SEEDED, 0),
        "new": counts.get(NEW, 0),
        "today": now_utc().strftime("%Y-%m-%d"),
    }
