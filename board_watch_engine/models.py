"""Data shapes passed between pipeline stages."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Question:
    """One field on an application form. Greenhouse is the only ATS that exposes these."""

    label: str
    required: bool = False
    type: str = ""
    options: List[str] = field(default_factory=list)

    @property
    def is_free_text(self):
        return self.type == "textarea" or (
            self.type == "input_text" and len(self.label) > 40
        )


@dataclass
class Job:
    id: str
    title: str
    location: str = ""
    url: str = ""
    apply_url: str = ""
    description: str = ""
    team: str = ""
    compensation: str = ""
    posted_at: Optional[str] = None  # ISO-8601, when the ATS exposes it
    remote: bool = False
    questions: Optional[List[Question]] = None  # None = ATS does not expose the form
    board_token: str = ""  # needed for the second Greenhouse call
    error: str = ""


@dataclass
class Company:
    name: str
    ats: str
    token: str = ""
    region: str = ""
    tier: int = 3
    url: str = ""
    note: str = ""
    # Server-side narrowing, for boards too large to enumerate. Only Workday
    # honours it; see ats.HONOURS_SEARCH.
    search: str = ""

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d.get("name", ""),
            ats=d.get("ats", ""),
            token=d.get("token", ""),
            region=d.get("region", ""),
            tier=int(d.get("tier", 3)),
            url=d.get("url", ""),
            note=d.get("note", ""),
            search=d.get("search", ""),
        )


@dataclass
class MatchRules:
    include_title: List[str] = field(default_factory=list)
    exclude_title: List[str] = field(default_factory=list)
    locations_allow: List[str] = field(default_factory=list)
    require_any_keyword_in_description: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        low = lambda xs: [str(x).lower() for x in (xs or [])]  # noqa: E731
        return cls(
            include_title=low(d.get("include_title")),
            exclude_title=low(d.get("exclude_title")),
            locations_allow=low(d.get("locations_allow")),
            require_any_keyword_in_description=low(
                d.get("require_any_keyword_in_description")
            ),
        )


@dataclass
class Hit:
    """A matched job paired with the company it came from."""

    company: Company
    job: Job
