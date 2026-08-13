"""Phase 1 unit tests. Stdlib unittest, no network.

    python3 -m unittest discover -s tests -v
"""

import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from board_watch_engine import SCHEMA_VERSION  # noqa: E402
from board_watch_engine.cli import main  # noqa: E402
from board_watch_engine.config import Config, ConfigError, load_board  # noqa: E402
from board_watch_engine.matching import (  # noqa: E402
    is_fresh, matches, needs_write_yourself, title_hit,
)
from board_watch_engine.models import Job, MatchRules  # noqa: E402
from board_watch_engine.paths import Paths  # noqa: E402
from board_watch_engine.scaffold import ensure_scaffold  # noqa: E402
from board_watch_engine import ats as ats_registry  # noqa: E402
from board_watch_engine import summary  # noqa: E402
from board_watch_engine.ats import amazon, microsoft, workday  # noqa: E402
from board_watch_engine.ats.base import FetchError  # noqa: E402
from board_watch_engine.state import (  # noqa: E402
    APPLIED, SEEDED, LockBusy, RunLock, SeenState, migrate,
)
from board_watch_engine.util import iso, now_utc, slugify, strip_html  # noqa: E402


class TempRoot(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="bw-test-")
        self.paths = Paths(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


# -- matching ----------------------------------------------------------------


class TestMatching(unittest.TestCase):
    def rules(self, **kw):
        return MatchRules.from_dict({
            "include_title": kw.get("include", ["product manager"]),
            "exclude_title": kw.get("exclude", []),
            "locations_allow": kw.get("locations", []),
            "require_any_keyword_in_description": kw.get("keywords", []),
        })

    def test_title_include(self):
        self.assertTrue(matches(Job(id="1", title="Product Manager"), self.rules()))
        self.assertFalse(matches(Job(id="1", title="Data Scientist"), self.rules()))

    def test_title_is_case_insensitive(self):
        self.assertTrue(matches(Job(id="1", title="PRODUCT MANAGER, AI"), self.rules()))

    def test_exclude_beats_include(self):
        r = self.rules(exclude=["intern"])
        self.assertFalse(matches(Job(id="1", title="Product Manager Intern"), r))

    def test_conjunction_operator(self):
        self.assertTrue(title_hit("member of technical staff, product",
                                  "member of technical staff && product"))
        self.assertFalse(title_hit("member of technical staff",
                                   "member of technical staff && product"))

    def test_location_allowlist(self):
        r = self.rules(locations="india,remote".split(","))
        self.assertTrue(matches(Job(id="1", title="Product Manager",
                                    location="Bangalore, India"), r))
        self.assertFalse(matches(Job(id="1", title="Product Manager",
                                     location="Zurich"), r))

    def test_remote_flag_satisfies_remote_allowlist(self):
        r = self.rules(locations=["remote"])
        self.assertTrue(matches(
            Job(id="1", title="Product Manager", location="Anywhere", remote=True), r))

    def test_empty_description_does_not_reject(self):
        """A blank description means it has not been fetched yet, not that it failed."""
        r = self.rules(keywords=["agents"])
        self.assertTrue(matches(Job(id="1", title="Product Manager", description=""), r))
        self.assertFalse(matches(
            Job(id="1", title="Product Manager", description="we build databases"), r))

    def test_write_yourself_detection(self):
        self.assertTrue(needs_write_yourself("Why do you want to work at Anthropic?"))
        self.assertTrue(needs_write_yourself("In your own words, describe..."))
        self.assertFalse(needs_write_yourself("Years of product experience"))

    def test_is_fresh(self):
        recent = iso(now_utc().replace(microsecond=0))
        self.assertTrue(is_fresh(Job(id="1", title="x", posted_at=recent), 7))
        self.assertFalse(is_fresh(Job(id="1", title="x", posted_at="2020-01-01T00:00:00Z"), 7))

    def test_unknown_posting_date_is_not_fresh(self):
        """SmartRecruiters exposes no date; treating unknown as fresh would
        package an entire board on day one."""
        self.assertFalse(is_fresh(Job(id="1", title="x", posted_at=None), 7))


# -- state -------------------------------------------------------------------


class TestMigration(unittest.TestCase):
    def test_v1_list_becomes_seeded_objects(self):
        data, changed = migrate({"Anthropic": ["1", "2"], "OpenAI": ["9"]})
        self.assertTrue(changed)
        self.assertEqual(data["_schema"], SCHEMA_VERSION)
        self.assertEqual(data["Anthropic"]["1"]["status"], SEEDED)
        self.assertFalse(data["Anthropic"]["1"]["applied"])
        self.assertIn("first_seen", data["Anthropic"]["1"])

    def test_spec_shape_bool_map(self):
        data, changed = migrate({"Anthropic": {"1": True, "2": False}})
        self.assertTrue(changed)
        self.assertEqual(data["Anthropic"]["1"]["status"], APPLIED)
        self.assertTrue(data["Anthropic"]["1"]["applied"])
        self.assertEqual(data["Anthropic"]["2"]["status"], SEEDED)

    def test_v2_is_left_alone(self):
        v2 = {"_schema": SCHEMA_VERSION,
              "Anthropic": {"1": {"status": "sent", "applied": False}}}
        data, changed = migrate(v2)
        self.assertFalse(changed)
        self.assertEqual(data, v2)

    def test_migration_is_idempotent(self):
        once, _ = migrate({"Anthropic": ["1"]})
        twice, changed = migrate(once)
        self.assertFalse(changed)
        self.assertEqual(once, twice)

    def test_garbage_does_not_raise(self):
        data, changed = migrate(["not", "a", "dict"])
        self.assertTrue(changed)
        self.assertEqual(data["_schema"], SCHEMA_VERSION)


class TestSeenState(TempRoot):
    def test_roundtrip(self):
        st = SeenState(os.path.join(self.root, "seen.json"))
        st.record("Anthropic", "1", "sent", title="PM", issue=42)
        st.save()

        again = SeenState.load(st.path)
        entry = again.get("Anthropic", "1")
        self.assertEqual(entry["issue"], 42)
        self.assertEqual(entry["status"], "sent")
        self.assertFalse(entry["applied"])

    def test_seed_does_not_overwrite(self):
        st = SeenState(os.path.join(self.root, "seen.json"))
        st.record("Anthropic", "1", "sent", issue=42)
        self.assertIsNone(st.seed("Anthropic", "1"))
        self.assertEqual(st.get("Anthropic", "1")["status"], "sent")

    def test_mark_applied_sets_both_fields(self):
        st = SeenState(os.path.join(self.root, "seen.json"))
        st.record("Anthropic", "1", "sent", issue=42)
        st.mark_applied("Anthropic", "1")
        entry = st.get("Anthropic", "1")
        self.assertTrue(entry["applied"])
        self.assertEqual(entry["status"], APPLIED)
        self.assertIn("applied_at", entry)

    def test_schema_key_is_not_a_company(self):
        st = SeenState(os.path.join(self.root, "seen.json"))
        st.record("Anthropic", "1", "sent")
        st.save()
        self.assertEqual(SeenState.load(st.path).companies(), ["Anthropic"])

    def test_atomic_write_leaves_no_temp_files(self):
        st = SeenState(os.path.join(self.root, "seen.json"))
        st.record("Anthropic", "1", "sent")
        st.save()
        leftovers = [f for f in os.listdir(self.root) if f.startswith(".tmp-")]
        self.assertEqual(leftovers, [])


class TestLock(TempRoot):
    def test_second_acquire_is_refused(self):
        path = os.path.join(self.root, "lock")
        with RunLock(path):
            with self.assertRaises(LockBusy):
                RunLock(path).acquire()

    def test_release_allows_reacquire(self):
        path = os.path.join(self.root, "lock")
        RunLock(path).acquire().release()
        RunLock(path).acquire().release()

    def test_stale_lock_is_broken(self):
        """A routine killed mid-run must not wedge the service permanently."""
        path = os.path.join(self.root, "lock")
        held = RunLock(path).acquire()
        old = time.time() - 7200
        os.utime(path, (old, old))
        RunLock(path, stale_after_minutes=1).acquire().release()
        held.acquired = False


# -- scaffold ----------------------------------------------------------------


class TestScaffold(TempRoot):
    def test_creates_full_tree(self):
        ensure_scaffold(self.paths)
        for d in self.paths.all_directories():
            self.assertTrue(os.path.isdir(d), d)
        for f in (self.paths.config_file, self.paths.companies_file,
                  self.paths.seen_file):
            self.assertTrue(os.path.exists(f), f)
        self.assertIsNotNone(self.paths.profile_file())

    def test_is_idempotent(self):
        ensure_scaffold(self.paths)
        self.assertEqual(ensure_scaffold(self.paths), [])

    def test_does_not_clobber_existing_config(self):
        ensure_scaffold(self.paths)
        with open(self.paths.config_file, "w") as f:
            json.dump({"cadence": "daily", "tier": 1}, f)
        ensure_scaffold(self.paths)
        with open(self.paths.config_file) as f:
            self.assertEqual(json.load(f)["cadence"], "daily")

    def test_seen_file_starts_at_v2(self):
        ensure_scaffold(self.paths)
        with open(self.paths.seen_file) as f:
            self.assertEqual(json.load(f)["_schema"], SCHEMA_VERSION)

    def test_default_company_list_is_loadable(self):
        ensure_scaffold(self.paths)
        board = load_board(self.paths)
        self.assertTrue(board.companies)
        self.assertTrue(board.match.include_title)


# -- workday adapter ---------------------------------------------------------


class TestWorkday(unittest.TestCase):
    """No network: get_json is swapped for a canned pager."""

    def setUp(self):
        self.real = workday.get_json
        self.calls = []

    def tearDown(self):
        workday.get_json = self.real

    def _pager(self, total, pages):
        """Mimic Workday: `total` on page 1, then 0 on every later page."""
        def fake(url, data=None, **kw):
            self.calls.append(data["offset"])
            off = data["offset"]
            page = pages[off // workday.PAGE] if off // workday.PAGE < len(pages) else []
            return {"total": total if off == 0 else 0, "jobPostings": page}
        return fake

    def _posting(self, n):
        return {"title": "Product Manager %d" % n,
                "externalPath": "/job/Mumbai/PM-%d_SR-%d" % (n, n),
                "locationsText": "Mumbai", "postedOn": "Posted 2 Days Ago",
                "bulletFields": ["SR-%d" % n]}

    def test_token_must_have_three_parts(self):
        for bad in ("fractal", "fractal/wd1", "", None):
            with self.assertRaises(FetchError):
                workday.fetch(bad)

    def test_paginates_past_the_first_page(self):
        """Regression: `total` is only sent on page 1 — reading it on later
        pages sees 0 and terminates the loop after two pages."""
        pages = [[self._posting(i) for i in range(p * 20, p * 20 + 20)] for p in range(3)]
        pages.append([self._posting(60)])
        workday.get_json = self._pager(61, pages)

        jobs = workday.fetch("fractal/wd1/Careers")
        self.assertEqual(len(jobs), 61)
        self.assertEqual(self.calls, [0, 20, 40, 60])

    def test_stops_on_short_page(self):
        workday.get_json = self._pager(0, [[self._posting(i) for i in range(5)]])
        self.assertEqual(len(workday.fetch("a/b/c")), 5)
        self.assertEqual(self.calls, [0])

    def test_respects_page_cap(self):
        full = [self._posting(i) for i in range(20)]
        workday.get_json = self._pager(10000, [full] * 100)
        jobs = workday.fetch("a/b/c")
        self.assertEqual(len(self.calls), workday.MAX_PAGES)
        self.assertTrue(len(jobs) <= workday.MAX_PAGES * workday.PAGE)

    def test_deduplicates_across_pages(self):
        dup = [self._posting(1)]
        workday.get_json = self._pager(0, [dup, dup])
        self.assertEqual(len(workday.fetch("a/b/c")), 1)

    def test_maps_fields(self):
        workday.get_json = self._pager(0, [[self._posting(7)]])
        j = workday.fetch("fractal/wd1/Careers")[0]
        self.assertEqual(j.id, "SR-7")          # req id, not the slug
        self.assertEqual(j.location, "Mumbai")
        self.assertIn("fractal.wd1.myworkdayjobs.com/Careers", j.apply_url)
        self.assertIsNone(j.questions)          # form not exposed

    def test_search_is_forwarded(self):
        seen = {}

        def fake(url, data=None, **kw):
            seen.update(data)
            return {"total": 0, "jobPostings": []}
        workday.get_json = fake
        workday.fetch("a/b/c", search="product manager")
        self.assertEqual(seen["searchText"], "product manager")

    def test_relative_dates(self):
        self.assertIsNotNone(workday._approx_date("Posted Today"))
        self.assertIsNotNone(workday._approx_date("Posted 3 Days Ago"))
        # '30+' means "at least 30" — guessing 30 would let a months-old req
        # pass a freshness window it should fail.
        self.assertIsNone(workday._approx_date("Posted 30+ Days Ago"))
        self.assertIsNone(workday._approx_date(""))

    def test_registered(self):
        self.assertIn("workday", ats_registry.known())
        self.assertIn("workday", ats_registry.HONOURS_SEARCH)
        self.assertNotIn("workday", ats_registry.HAS_POSTING_DATE)


# -- amazon adapter ----------------------------------------------------------


class TestAmazon(unittest.TestCase):
    def setUp(self):
        self.real = amazon.get_json
        self.calls = []

    def tearDown(self):
        amazon.get_json = self.real

    def _posting(self, n):
        return {"id_icims": str(10000 + n), "id": "uuid-%d" % n,
                "title": "Senior Product Manager %d" % n,
                "normalized_location": "Seattle, Washington, USA",
                "job_path": "/en/jobs/%d/spm-%d" % (10000 + n, n),
                "url_next_step": "https://account.amazon.jobs/jobs/%d/apply" % (10000 + n),
                "description": "<p>Build things</p>",
                "basic_qualifications": "5+ years",
                "preferred_qualifications": "MBA",
                "job_family": "Product Management - Technical",
                "posted_date": "August 11, 2026"}

    def _pager(self, hits, pages):
        def fake(url, **kw):
            self.calls.append(url)
            off = int(re.search(r"offset=(\d+)", url).group(1))
            idx = off // amazon.PAGE
            return {"hits": hits, "jobs": pages[idx] if idx < len(pages) else []}
        return fake

    def test_uses_icims_id_not_uuid(self):
        """The UUID churns between crawls; id_icims is the stable requisition."""
        amazon.get_json = self._pager(1, [[self._posting(1)]])
        self.assertEqual(amazon.fetch()[0].id, "10001")

    def test_description_merges_all_three_fields(self):
        amazon.get_json = self._pager(1, [[self._posting(1)]])
        desc = amazon.fetch()[0].description
        for fragment in ("Build things", "5+ years", "MBA"):
            self.assertIn(fragment, desc)

    def test_paginates_and_stops_on_hits(self):
        pages = [[self._posting(i) for i in range(p * 100, p * 100 + 100)] for p in range(2)]
        amazon.get_json = self._pager(200, pages)
        self.assertEqual(len(amazon.fetch()), 200)
        self.assertEqual(len(self.calls), 2)

    def test_stops_on_short_page(self):
        amazon.get_json = self._pager(999, [[self._posting(i) for i in range(3)]])
        self.assertEqual(len(amazon.fetch()), 3)
        self.assertEqual(len(self.calls), 1)

    def test_respects_page_cap(self):
        full = [self._posting(i) for i in range(100)]
        amazon.get_json = self._pager(10 ** 6, [full] * 50)
        amazon.fetch()
        self.assertEqual(len(self.calls), amazon.MAX_PAGES)

    def test_blank_search_falls_back_to_a_default(self):
        """An unbounded base_query would pull tens of thousands of reqs."""
        amazon.get_json = self._pager(0, [[]])
        amazon.fetch(search="")
        self.assertIn("base_query=" + amazon.DEFAULT_SEARCH, self.calls[0])

    def test_search_is_url_encoded(self):
        amazon.get_json = self._pager(0, [[]])
        amazon.fetch(search="product manager")
        self.assertIn("base_query=product+manager", self.calls[0])

    def test_parses_posted_date(self):
        self.assertEqual(amazon._parse_date("August 11, 2026"), "2026-08-11T00:00:00Z")
        self.assertIsNone(amazon._parse_date("11 Aug 26"))
        self.assertIsNone(amazon._parse_date(None))

    def test_registered_with_dates_and_search(self):
        self.assertIn("amazon", ats_registry.known())
        self.assertIn("amazon", ats_registry.HAS_POSTING_DATE)
        self.assertIn("amazon", ats_registry.HONOURS_SEARCH)
        self.assertNotIn("amazon", ats_registry.ENRICHERS)  # descriptions inline


# -- microsoft adapter -------------------------------------------------------


class TestMicrosoft(unittest.TestCase):
    def setUp(self):
        self.real = microsoft.get_json
        self.calls = []

    def tearDown(self):
        microsoft.get_json = self.real

    def _position(self, n):
        return {"id": 197039355692891 + n, "displayJobId": str(200043247 + n),
                "atsJobId": str(200043247 + n),
                "name": "Senior Product Manager %d" % n,
                "locations": ["United States, Washington, Redmond"],
                "standardizedLocations": ["Redmond, WA, US"],
                "postedTs": 1784240758, "department": "Product Management",
                "workLocationOption": "onsite",
                "positionUrl": "/careers/job/%d" % (197039355692891 + n)}

    def _pager(self, count, pages):
        def fake(url, **kw):
            self.calls.append(url)
            start = int(re.search(r"start=(\d+)", url).group(1))
            idx = start // microsoft.PAGE
            return {"data": {"count": count,
                             "positions": pages[idx] if idx < len(pages) else []}}
        return fake

    def test_uses_display_job_id(self):
        """displayJobId is the requisition recruiters quote; `id` is internal."""
        microsoft.get_json = self._pager(1, [[self._position(0)]])
        self.assertEqual(microsoft.fetch()[0].id, "200043247")

    def test_prefers_standardized_location(self):
        microsoft.get_json = self._pager(1, [[self._position(0)]])
        self.assertEqual(microsoft.fetch()[0].location, "Redmond, WA, US")

    def test_url_points_at_the_apply_host(self):
        """jobs.careers.microsoft.com/global/en/job/<id> now redirects to a
        generic landing page; only the apply host resolves to the posting."""
        microsoft.get_json = self._pager(1, [[self._position(0)]])
        job = microsoft.fetch()[0]
        self.assertTrue(job.url.startswith("https://apply.careers.microsoft.com/careers/job/"))
        self.assertEqual(job.apply_url, job.url)

    def test_paginates_by_row_offset(self):
        pages = [[self._position(i) for i in range(p * 10, p * 10 + 10)] for p in range(3)]
        microsoft.get_json = self._pager(30, pages)
        self.assertEqual(len(microsoft.fetch()), 30)
        self.assertEqual([re.search(r"start=(\d+)", c).group(1) for c in self.calls],
                         ["0", "10", "20"])

    def test_stops_on_short_page(self):
        microsoft.get_json = self._pager(999, [[self._position(i) for i in range(4)]])
        self.assertEqual(len(microsoft.fetch()), 4)
        self.assertEqual(len(self.calls), 1)

    def test_respects_page_cap(self):
        full = [self._position(i) for i in range(10)]
        microsoft.get_json = self._pager(10 ** 5, [full] * 100)
        microsoft.fetch()
        self.assertEqual(len(self.calls), microsoft.MAX_PAGES)

    def test_blank_search_falls_back(self):
        microsoft.get_json = self._pager(0, [[]])
        microsoft.fetch(search="")
        self.assertIn("query=product%20manager", self.calls[0])

    def test_epoch_dates(self):
        self.assertEqual(microsoft._epoch(1784240758), "2026-07-16T22:25:58Z")
        self.assertIsNone(microsoft._epoch(None))
        self.assertIsNone(microsoft._epoch("not-a-number"))

    def test_no_description_available(self):
        """No per-position endpoint responds, so Microsoft cannot be filtered
        by require_any_keyword_in_description."""
        microsoft.get_json = self._pager(1, [[self._position(0)]])
        self.assertEqual(microsoft.fetch()[0].description, "")
        self.assertNotIn("microsoft", ats_registry.ENRICHERS)

    def test_registered(self):
        self.assertIn("microsoft", ats_registry.known())
        self.assertIn("microsoft", ats_registry.HAS_POSTING_DATE)
        self.assertIn("microsoft", ats_registry.HONOURS_SEARCH)


# -- cli ---------------------------------------------------------------------


class TestCli(TempRoot):
    def test_scaffold_then_status(self):
        self.assertEqual(main(["--root", self.root, "scaffold"]), 0)
        self.assertEqual(main(["--root", self.root, "status"]), 0)
        self.assertTrue(os.path.exists(self.paths.seen_file))

    def test_scaffold_is_idempotent_through_cli(self):
        main(["--root", self.root, "scaffold"])
        before = sorted(os.listdir(self.root))
        main(["--root", self.root, "scaffold"])
        self.assertEqual(sorted(os.listdir(self.root)), before)

    def test_state_v1_is_upgraded_transparently_on_load(self):
        """The CLI no longer has a migrate command; SeenState.load handles a
        stale schema on its own so an old file can never be misread."""
        ensure_scaffold(self.paths)
        with open(self.paths.seen_file, "w") as f:
            json.dump({"Anthropic": ["1", "2"]}, f)

        state = SeenState.load(self.paths.seen_file)
        self.assertTrue(state.dirty)
        self.assertEqual(state.get("Anthropic", "1")["status"], SEEDED)
        state.save()
        self.assertFalse(SeenState.load(self.paths.seen_file).dirty)

    def test_verbose_accepted_before_and_after_subcommand(self):
        for argv in (["--root", self.root, "-v", "status"],
                     ["--root", self.root, "status", "-v"]):
            self.assertEqual(main(argv), 0, argv)

    def test_root_accepted_after_subcommand(self):
        self.assertEqual(main(["status", "--root", self.root]), 0)

    def test_poll_without_config_is_a_clean_error(self):
        self.assertEqual(main(["--root", self.root, "poll", "--dry-run"]), 2)


# -- config ------------------------------------------------------------------


class TestConfig(TempRoot):
    def test_defaults(self):
        c = Config()
        self.assertEqual(c.cadence, "hourly")
        self.assertEqual(c.cadence_minutes, 60)
        self.assertEqual(c.validate(), [])

    def test_roundtrip(self):
        c = Config.from_dict({"cadence": "15min", "tier": 1, "max_new_per_run": 3})
        self.assertEqual(c.cadence_minutes, 15)
        self.assertEqual(Config.from_dict(c.to_dict()).to_dict(), c.to_dict())

    def test_validation_catches_bad_values(self):
        self.assertTrue(Config.from_dict({"cadence": "yearly"}).validate())
        self.assertTrue(Config.from_dict({"digest_time": "25:00"}).validate())
        self.assertTrue(Config.from_dict({"github_repo": "no-slash"}).validate())
        self.assertTrue(Config.from_dict({"max_new_per_run": 0}).validate())

    def test_missing_companies_file_is_a_config_error(self):
        with self.assertRaises(ConfigError):
            load_board(self.paths)

    def test_board_filters_by_tier_and_adapter(self):
        ensure_scaffold(self.paths)
        with open(self.paths.companies_file, "w") as f:
            json.dump({"companies": [
                {"name": "A", "ats": "greenhouse", "token": "a", "tier": 1},
                {"name": "B", "ats": "greenhouse", "token": "b", "tier": 3},
                {"name": "C", "ats": "manual", "url": "x", "tier": 1},
            ], "match": {"include_title": ["product"]}}, f)
        board = load_board(self.paths)
        names = [c.name for c in board.resolvable(1, {"greenhouse"})]
        self.assertEqual(names, ["A"])
        self.assertEqual([c.name for c in board.manual()], ["C"])


# -- util --------------------------------------------------------------------


class TestSummary(TempRoot):
    def _state(self):
        ensure_scaffold(self.paths)
        return SeenState.load(self.paths.seen_file)

    def test_seeded_records_are_counted(self):
        st = self._state()
        st.seed("Anthropic", "1")
        st.seed("Anthropic", "2")
        st.record("Sierra", "9", "new")

        counts, companies = summary.tally(st, now_utc())
        self.assertEqual(counts[SEEDED], 2)
        self.assertEqual(counts["new"], 1)
        self.assertEqual(companies, ["Anthropic", "Sierra"])

    def test_applied_counted_on_the_day_it_was_applied(self):
        st = self._state()
        st.record("Anthropic", "1", "sent")
        st.mark_applied("Anthropic", "1")
        counts, _ = summary.tally(st, now_utc())
        self.assertEqual(counts[APPLIED], 1)
        self.assertEqual(counts["sent"], 0)

    def test_other_days_are_excluded(self):
        st = self._state()
        st.record("Anthropic", "1", "new")
        st.get("Anthropic", "1")["first_seen"] = "2020-01-01T00:00:00Z"
        counts, companies = summary.tally(st, now_utc())
        self.assertEqual(counts["new"], 0)
        self.assertEqual(companies, [])

    def test_upsert_replaces_rather_than_appends(self):
        st = self._state()
        st.seed("Anthropic", "1")
        cfg = Config()

        summary.upsert(self.paths, st, cfg)
        st.seed("Anthropic", "2")
        path, changed = summary.upsert(self.paths, st, cfg)
        self.assertTrue(changed)

        with open(path) as f:
            body = f.read()
        today = now_utc().strftime("%Y-%m-%d")
        self.assertEqual(body.count("| " + today + " |"), 1)
        self.assertIn("| 2 |", body)  # both seeded records, one row

    def test_upsert_is_a_noop_when_nothing_changed(self):
        st = self._state()
        st.seed("Anthropic", "1")
        cfg = Config()
        summary.upsert(self.paths, st, cfg)
        _, changed = summary.upsert(self.paths, st, cfg)
        self.assertFalse(changed)

    def test_header_present_and_includes_seeded(self):
        st = self._state()
        path, _ = summary.upsert(self.paths, st, Config())
        with open(path) as f:
            body = f.read()
        self.assertIn("| Seeded |", body)
        self.assertIn("# Application ledger", body)

    def test_company_cell_truncates(self):
        st = self._state()
        for i in range(9):
            st.seed("Company%d" % i, str(i))
        row = summary.row_for(st, Config(), now_utc())
        self.assertIn("+3 more", row["Companies"])


class TestLogPath(TempRoot):
    def test_log_file_is_per_day_ddmmyyyy(self):
        from datetime import datetime, timezone
        dt = datetime(2026, 8, 9, 14, 30, tzinfo=timezone.utc)
        self.assertTrue(self.paths.log_file(dt).endswith("09082026.log"))


class TestUtil(unittest.TestCase):
    def test_strip_html(self):
        self.assertEqual(strip_html("<p>Hello<br/>World</p>"), "Hello\nWorld")
        self.assertEqual(strip_html("<ul><li>One</li><li>Two</li></ul>"),
                         "- One\n  - Two")
        self.assertEqual(strip_html("&amp;&lt;"), "&<")
        self.assertEqual(strip_html(None), "")

    def test_strip_html_drops_scripts(self):
        self.assertEqual(strip_html("<script>evil()</script><p>Safe</p>"), "Safe")

    def test_slugify(self):
        self.assertEqual(slugify("Product Manager, Claude Code"),
                         "product-manager-claude-code")
        self.assertEqual(slugify("A" * 100, maxlen=10), "a" * 10)


if __name__ == "__main__":
    unittest.main()
