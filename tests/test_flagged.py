"""Tracing a changelog entry back to the report that prompted it."""

import json
from datetime import date

from kasauti.archaeology.flagged import (
    Flag,
    IssueCache,
    cited,
    parse_repositories,
    write_flags,
)


class TestCited:
    def test_a_hash_number_is_an_issue(self):
        assert cited("Fixed the sign error (#412).") == [412]

    def test_the_spelled_out_forms_count(self):
        assert cited("see issue 88 and gh-91") == [88, 91]

    def test_several_citations_keep_their_order_without_duplicates(self):
        assert cited("closes #7, #12, and #7 again") == [7, 12]

    def test_prose_with_no_citation_yields_nothing(self):
        assert cited("Fixed a bug in vcovHC reported by James Pustejovsky.") == []

    def test_a_number_too_long_to_be_an_issue_is_ignored(self):
        assert cited("commit #1234567890") == []


class TestParseRepositories:
    def test_a_github_url_becomes_owner_and_name(self):
        found = parse_repositories("sandwich https://github.com/oh/sandwich")
        assert found == {"sandwich": "oh/sandwich"}

    def test_a_trailing_issues_path_is_stripped(self):
        found = parse_repositories("fixest https://github.com/lrberge/fixest/issues")
        assert found == {"fixest": "lrberge/fixest"}

    def test_a_non_github_url_is_not_a_repository(self):
        # Half the sampled packages name no GitHub repository at all, which is a
        # selection gate on every latency this module produces -- not something
        # to paper over by guessing a URL shape.
        assert parse_repositories("MASS https://www.stats.ox.ac.uk/pub/MASS4/") == {}

    def test_the_first_field_wins(self):
        # `URL` is printed before `BugReports`, so a package naming both keeps
        # the one it calls its home rather than its tracker.
        found = parse_repositories(
            "p https://github.com/owner/home\np https://github.com/owner/tracker"
        )
        assert found == {"p": "owner/home"}


class TestPlausibility:
    def make(self, fixed: date | None, flagged: date | None) -> Flag:
        return Flag(
            entry_id="p@1.0#0",
            package="p",
            version="1.0",
            fixed_on=fixed,
            repo="o/p",
            issue=7,
            flagged_on=flagged,
        )

    def test_a_report_before_its_release_is_usable(self):
        flag = self.make(date(2020, 6, 1), date(2020, 1, 1))
        assert flag.plausible
        assert flag.response_days == 152

    def test_a_report_after_its_release_is_not_an_issue_in_this_repository(self):
        # The check that must hold if the citation is real. A number failing it
        # is a version, a pull request, or somebody else's ticket, and the
        # latency it would produce is a plausible number about nothing.
        assert not self.make(date(2020, 1, 1), date(2020, 6, 1)).plausible

    def test_an_unresolved_issue_is_not_plausible_rather_than_zero(self):
        flag = self.make(date(2020, 1, 1), None)
        assert flag.response_days is None
        assert not flag.plausible


class TestIssueCache:
    def test_a_hit_is_fetched_once(self, tmp_path):
        calls = []

        def fetch(repo, number):
            calls.append((repo, number))
            return date(2019, 3, 4)

        cache = IssueCache(tmp_path / "issues.json")
        assert cache.get("o/p", 7, fetch=fetch) == date(2019, 3, 4)
        assert cache.get("o/p", 7, fetch=fetch) == date(2019, 3, 4)
        assert calls == [("o/p", 7)]

    def test_a_miss_is_cached_too(self, tmp_path):
        # Most misses are permanent -- the number was never an issue in this
        # repository -- so re-asking GitHub every run would spend the rate limit
        # on an answer already known.
        calls = []

        def fetch(repo, number):
            calls.append(number)
            return None

        cache = IssueCache(tmp_path / "issues.json")
        assert cache.get("o/p", 9, fetch=fetch) is None
        assert cache.get("o/p", 9, fetch=fetch) is None
        assert calls == [9]

    def test_the_cache_survives_a_reload(self, tmp_path):
        path = tmp_path / "issues.json"
        IssueCache(path).get("o/p", 7, fetch=lambda r, n: date(2019, 3, 4))
        again = IssueCache(path)
        assert again.get("o/p", 7, fetch=lambda r, n: None) == date(2019, 3, 4)
        assert json.loads(path.read_text())["o/p#7"] == "2019-03-04"


def test_implausible_rows_are_written_flagged_not_dropped(tmp_path):
    """The share of citations that were not issues has to stay visible.

    Dropping them would leave a table whose rows all look resolved and no way to
    tell how much of the changelog's citation habit is noise.
    """
    flags = [
        Flag("p@1.0#0", "p", "1.0", date(2020, 6, 1), "o/p", 7, date(2020, 1, 1)),
        Flag("p@1.0#1", "p", "1.0", date(2020, 1, 1), "o/p", 9, date(2020, 6, 1)),
    ]
    path = tmp_path / "flagged.csv"
    write_flags(flags, path)

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 3
    assert lines[1].endswith(",152,1")
    assert lines[2].endswith(",-152,0")
