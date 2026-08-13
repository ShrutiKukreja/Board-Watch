"""Command-line entry point.

    python3 -m board_watch_engine poll [--dry-run] [--tier N]
    python3 -m board_watch_engine seed
    python3 -m board_watch_engine scaffold
    python3 -m board_watch_engine status

The repo root is both the code and the data root, so commands normally need no
arguments. --root exists for tests and for pointing at a second data repo.
"""

import argparse
import sys

from . import __version__
from .config import ConfigError, load_board, load_config
from .logging_setup import setup as setup_logging
from .paths import Paths
from .poll import poll
from .scaffold import describe, ensure_scaffold
from .state import LockBusy, lock_for
from .util import now_utc


def build_parser():
    p = argparse.ArgumentParser(
        prog="board-watch",
        description="Poll ATS job boards and build application packets.",
    )
    p.add_argument("--version", action="version", version="board-watch " + __version__)
    p.add_argument("--root", help="data root (default: $BOARD_WATCH_ROOT or cwd)")
    p.add_argument("-v", "--verbose", action="store_true")

    # Repeated on every subcommand so `poll -v` works as well as `-v poll`.
    # SUPPRESS keeps an omitted flag from clobbering the top-level value.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=argparse.SUPPRESS,
                        help="data root (default: $BOARD_WATCH_ROOT or cwd)")
    common.add_argument("-v", "--verbose", action="store_true",
                        default=argparse.SUPPRESS)

    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("poll", parents=[common], help="one poll cycle")
    sp.add_argument("--dry-run", action="store_true",
                    help="report findings, write nothing")
    sp.add_argument("--tier", type=int, help="poll companies at this tier or better")

    ss = sub.add_parser("seed", parents=[common],
                        help="baseline every open posting, produce no packets")
    ss.add_argument("--tier", type=int)

    sub.add_parser("scaffold", parents=[common],
                   help="create any missing folders and config")
    sub.add_parser("status", parents=[common], help="what is tracked right now")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.command:
        build_parser().print_help()
        return 0

    paths = Paths(args.root)
    logger = setup_logging(
        paths, now_utc(), verbose=args.verbose,
        to_file=args.command in ("poll", "seed"),
    )

    try:
        return _dispatch(args, paths, logger)
    except ConfigError as e:
        logger.error("%s", e)
        return 2
    except LockBusy as e:
        logger.error("%s", e)
        return 3
    except KeyboardInterrupt:
        logger.error("interrupted")
        return 130


def _dispatch(args, paths, logger):
    if args.command == "scaffold":
        created = ensure_scaffold(paths)
        if created:
            logger.info("created:\n  %s", "\n  ".join(created))
        else:
            logger.info("nothing to create — scaffold is complete at %s", paths.root)
        return 0

    if args.command == "status":
        return _status(paths, logger)

    cfg = load_config(paths)
    board = load_board(paths)

    with lock_for(paths, cfg):
        result = poll(
            paths, cfg, board,
            dry_run=getattr(args, "dry_run", False),
            seed=args.command == "seed",
            tier=args.tier,
        )

    _report(result, logger)
    return 1 if result.errors and not result.boards else 0


def _status(paths, logger):
    d = describe(paths)
    logger.info("root            %s", d["root"])
    logger.info("schema          v%s", d["schema"])
    logger.info("companies       %d", d["companies_tracked"])
    logger.info("jobs tracked    %d", d["jobs_tracked"])
    if d["by_status"]:
        logger.info("by status       %s", _fmt_counts(d["by_status"]))
    profile = paths.profile_file()
    logger.info("profile         %s", profile or "(none — run init)")
    return 0


def _report(result, logger):
    logger.info("")
    logger.info(result.summary_line())

    for hit in result.new_hits:
        j, c = hit.job, hit.company
        logger.info("")
        logger.info("  %s — %s", c.name, j.title)
        if j.location:
            logger.info("     %s", j.location)
        logger.info("     %s", j.apply_url or j.url)
        if j.questions:
            required = sum(1 for q in j.questions if q.required)
            logger.info("     %d form questions (%d required)",
                        len(j.questions), required)
        elif j.questions is None:
            logger.info("     form questions not exposed by %s", c.ats)

    if result.capped:
        logger.info("")
        logger.info("%d further role%s deferred to the next cycle.",
                    result.capped, "" if result.capped == 1 else "s")

    if result.errors:
        logger.info("")
        logger.info("%d board%s failed: %s", len(result.errors),
                    "" if len(result.errors) == 1 else "s",
                    ", ".join(b.company for b in result.errors))

    if result.manual:
        logger.info("")
        logger.info("%d unresolved board%s (need a slug in companies.json): %s",
                    len(result.manual), "" if len(result.manual) == 1 else "s",
                    ", ".join(result.manual))


def _fmt_counts(counts):
    return ", ".join("%s=%d" % kv for kv in sorted(counts.items()))


if __name__ == "__main__":
    sys.exit(main())
