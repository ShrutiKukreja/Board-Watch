"""Every filesystem location the engine touches, resolved from one data root.

In deployment the data root *is* the private repo the routine clones, so the
default is the current working directory. Precedence:

    --root <path>  >  $BOARD_WATCH_ROOT  >  cwd
"""

import os


class Paths:
    def __init__(self, root=None):
        self.root = os.path.abspath(
            root or os.environ.get("BOARD_WATCH_ROOT") or os.getcwd()
        )

    def _j(self, *parts):
        return os.path.join(self.root, *parts)

    # config -----------------------------------------------------------------
    @property
    def config_dir(self):
        return self._j("config")

    @property
    def config_file(self):
        return self._j("config", "config.json")

    @property
    def companies_file(self):
        return self._j("config", "companies.json")

    @property
    def profile_dir(self):
        return self._j("config", "profile")

    # resume -----------------------------------------------------------------
    @property
    def resume_source_dir(self):
        return self._j("resume", "source")

    @property
    def archetypes_dir(self):
        return self._j("resume", "archetypes")

    # packets ----------------------------------------------------------------
    @property
    def inbox_dir(self):
        return self._j("inbox")

    @property
    def new_dir(self):
        return self._j("inbox", "new")

    @property
    def sent_dir(self):
        return self._j("inbox", "sent")

    @property
    def applied_dir(self):
        return self._j("inbox", "applied")

    @property
    def seen_file(self):
        return self._j("inbox", "seen.json")

    @property
    def outbox_dir(self):
        return self._j("outbox")

    # bookkeeping ------------------------------------------------------------
    @property
    def summary_dir(self):
        return self._j("summary")

    def summary_file(self, dt):
        """summary/MMM-yy.md — one file per month, one row per day."""
        return os.path.join(self.summary_dir, dt.strftime("%b-%y") + ".md")

    @property
    def logs_dir(self):
        return self._j("logs")

    def log_file(self, dt):
        """logs/ddMMyyyy.log — one file per day, appended to by every run."""
        return os.path.join(self.logs_dir, dt.strftime("%d%m%Y") + ".log")

    @property
    def lock_file(self):
        return self._j(".board-watch.lock")

    # ------------------------------------------------------------------------
    DIRECTORIES = (
        "config_dir",
        "profile_dir",
        "resume_source_dir",
        "archetypes_dir",
        "inbox_dir",
        "new_dir",
        "sent_dir",
        "applied_dir",
        "outbox_dir",
        "summary_dir",
        "logs_dir",
    )

    def all_directories(self):
        return [getattr(self, name) for name in self.DIRECTORIES]

    def profile_file(self):
        """The single source of truth. Named after whoever init found in the resume."""
        if not os.path.isdir(self.profile_dir):
            return None
        names = sorted(
            f for f in os.listdir(self.profile_dir)
            if f.endswith(".md") and not f.startswith(".")
        )
        return os.path.join(self.profile_dir, names[0]) if names else None

    def __repr__(self):
        return "Paths(root=%r)" % self.root
