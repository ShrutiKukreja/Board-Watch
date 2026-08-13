"""Logging to both stderr and logs/YYYY-MM.log.

The routine's own transcript is ephemeral, so the file log in the repo is the
only durable record of what ran and what each board reported.
"""

import logging
import os


def setup(paths, dt, verbose=False, to_file=True):
    logger = logging.getLogger("board_watch_engine")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    for h in logger.handlers[:]:
        logger.removeHandler(h)
        h.close()  # otherwise a re-init leaks the open log file descriptor
    logger.propagate = False

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(message)s"))
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(console)

    if to_file:
        os.makedirs(paths.logs_dir, exist_ok=True)
        fh = logging.FileHandler(paths.log_file(dt))
        fh.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                              datefmt="%Y-%m-%dT%H:%M:%SZ")
        )
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)

    return logger


def get():
    return logging.getLogger("board_watch_engine")
