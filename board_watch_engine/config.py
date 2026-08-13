"""Loading and validation for config/config.json and config/companies.json."""

from dataclasses import dataclass, field
from typing import List

from .models import Company, MatchRules
from .util import read_json

CADENCES = {"hourly": 60, "30min": 30, "15min": 15, "daily": 1440}


@dataclass
class Config:
    # scheduling
    cadence: str = "hourly"
    digest_time: str = "22:00"
    timezone: str = "UTC"

    # behaviour
    max_new_per_run: int = 10
    backfill_days: int = 7
    tier: int = 3
    model: str = "claude-sonnet-5"

    # delivery
    github_repo: str = ""  # "owner/name" — issues are opened here
    default_archetype: str = ""

    target_roles: List[str] = field(default_factory=list)

    @property
    def cadence_minutes(self):
        return CADENCES.get(self.cadence, 60)

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        c = cls()
        for f in (
            "cadence", "digest_time", "timezone", "model",
            "github_repo", "default_archetype",
        ):
            if d.get(f):
                setattr(c, f, str(d[f]))
        for f in ("max_new_per_run", "backfill_days", "tier"):
            if d.get(f) is not None:
                setattr(c, f, int(d[f]))
        if d.get("target_roles"):
            c.target_roles = list(d["target_roles"])
        return c

    def to_dict(self):
        return {
            "cadence": self.cadence,
            "digest_time": self.digest_time,
            "timezone": self.timezone,
            "max_new_per_run": self.max_new_per_run,
            "backfill_days": self.backfill_days,
            "tier": self.tier,
            "model": self.model,
            "github_repo": self.github_repo,
            "default_archetype": self.default_archetype,
            "target_roles": self.target_roles,
        }

    def validate(self):
        problems = []
        if self.cadence not in CADENCES:
            problems.append(
                "cadence %r is not one of %s" % (self.cadence, ", ".join(CADENCES))
            )
        if not _valid_hhmm(self.digest_time):
            problems.append("digest_time %r is not HH:MM" % self.digest_time)
        if self.max_new_per_run < 1:
            problems.append("max_new_per_run must be >= 1")
        if self.backfill_days < 0:
            problems.append("backfill_days must be >= 0")
        if self.github_repo and self.github_repo.count("/") != 1:
            problems.append("github_repo must be 'owner/name', got %r" % self.github_repo)
        return problems


def _valid_hhmm(s):
    parts = str(s).split(":")
    if len(parts) != 2:
        return False
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return 0 <= h <= 23 and 0 <= m <= 59


DEFAULT_CONFIG = Config()


@dataclass
class Board:
    """companies.json, parsed: the company list plus the match rules."""

    companies: List[Company] = field(default_factory=list)
    match: MatchRules = field(default_factory=MatchRules)

    def resolvable(self, tier, known_ats):
        """Companies we can actually poll at or below `tier`."""
        return [
            c for c in self.companies
            if c.ats in known_ats and c.tier <= tier
        ]

    def manual(self):
        """Companies whose board slug has not been resolved yet."""
        return [c for c in self.companies if c.ats == "manual"]


def load_config(paths):
    cfg = Config.from_dict(read_json(paths.config_file, {}))
    problems = cfg.validate()
    if problems:
        raise ConfigError(
            "config/config.json is invalid:\n  - " + "\n  - ".join(problems)
        )
    return cfg


def load_board(paths):
    raw = read_json(paths.companies_file)
    if raw is None:
        raise ConfigError(
            "config/companies.json not found at %s — run `board-watch scaffold` first"
            % paths.companies_file
        )
    companies = [Company.from_dict(c) for c in raw.get("companies", [])]
    if not companies:
        raise ConfigError("config/companies.json lists no companies")
    return Board(companies=companies, match=MatchRules.from_dict(raw.get("match")))


class ConfigError(Exception):
    """Raised for anything a user can fix by editing a config file."""
