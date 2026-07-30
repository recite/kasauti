"""Changelog parsing and bug-to-corpus linkage."""

from datetime import date

import pytest

from concord.archaeology.harvest import Harvest, Release, _parse_cran_date
from concord.archaeology.link import (
    affected_functions,
    build_bugs,
    is_result_changing,
)
from concord.archaeology.parse import Entry, parse_news


def make_harvest(news, releases=()):
    return Harvest(
        package="pkg",
        ecosystem="cran",
        releases=[Release(v, d) for v, d in releases],
        news_text=news,
    )


class TestParseCranDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2024-09-15 21:50:01 UTC", date(2024, 9, 15)),
            ("2024-09-15", date(2024, 9, 15)),
            ("Mon Jul 19 23:28:55 2004; zeileis", date(2004, 7, 19)),
        ],
    )
    def test_recognises_the_formats_cran_uses(self, raw, expected):
        assert _parse_cran_date(raw) == expected

    def test_missing_or_unparseable_is_none(self):
        assert _parse_cran_date(None) is None
        assert _parse_cran_date("sometime last year") is None


class TestParseNews:
    def test_rd_sections(self):
        news = (
            r"\section{Changes in version 1.2-3 (2020-01-01)}{"
            r"\itemize{\item fixed an incorrect variance}}"
        )
        report = parse_news(make_harvest(news, [("1.2-3", date(2020, 1, 1))]))
        assert report.format == "rd"
        assert report.entries[0].version == "1.2-3"
        assert report.entries[0].released == date(2020, 1, 1)

    def test_all_caps_rd_heading(self):
        # lme4 writes \section{CHANGES IN VERSION 2.0-6}.
        news = r"\section{CHANGES IN VERSION 2.0-6}{\itemize{\item fixed the thing}}"
        assert parse_news(make_harvest(news)).entries[0].version == "2.0-6"

    def test_markdown_sections_with_trailing_parenthesis(self):
        # metafor writes "# metafor 5.0-1 (2026-04-26)".
        news = "# metafor 5.0-1 (2026-04-26)\n\n- fixed a wrong p-value\n"
        report = parse_news(make_harvest(news))
        assert report.format == "md"
        assert report.entries[0].version == "5.0-1"

    def test_changes_to_version_wording(self):
        # car writes "Changes to Version", not "Changes in version".
        news = "Changes to Version 3.1-4\n\n  o Fixed bugs in powerTransform.\n"
        report = parse_news(make_harvest(news))
        assert report.format == "txt"
        assert report.entries[0].version == "3.1-4"

    def test_bare_version_line(self):
        # mgcv's ChangeLog separates releases with a naked version number.
        news = "1.9-1\n\n* fixed an incorrect edf\n\n1.9-0\n\n* other change here\n"
        report = parse_news(make_harvest(news))
        assert report.format == "bare"
        assert {e.version for e in report.entries} == {"1.9-1", "1.9-0"}

    def test_gnu_changelog_dates_map_to_the_shipping_release(self):
        # nlme's ChangeLog dates every change but names no version. The change
        # shipped in the first release on or after that date.
        news = (
            "2020-06-01  A Maintainer  <a@b.c>\n\n"
            "\t* R/gnls.R: fix an incorrect standard error.\n"
        )
        harvest_result = make_harvest(
            news, [("3.1-100", date(2020, 1, 1)), ("3.1-101", date(2020, 7, 1))]
        )
        report = parse_news(harvest_result)
        assert report.format == "gnu"
        assert report.entries[0].version == "3.1-101"

    def test_change_after_every_known_release_is_unreleased(self):
        news = "2030-01-01  A  <a@b.c>\n\n\t* R/x.R: fix something incorrect.\n"
        report = parse_news(make_harvest(news, [("1.0", date(2020, 1, 1))]))
        assert report.entries[0].version == "unreleased"

    def test_unstructured_bullets_are_kept_not_collapsed(self):
        # MASS keeps a flat bullet list with no version headings at all. Those
        # changes are real even though none can be dated.
        news = (
            "Intro paragraph.\n\n- first change that is long enough\n"
            "- second change here\n"
        )
        report = parse_news(make_harvest(news))
        assert report.format == "unstructured"
        assert len(report.entries) >= 2
        assert report.undated == len(report.entries)

    def test_empty_news_yields_no_entries(self):
        report = parse_news(make_harvest("   "))
        assert report.entries == []
        assert report.version_coverage == 0.0

    def test_coverage_is_capped_at_one(self):
        news = "# 1.0\n\n- a change of sufficient length\n"
        report = parse_news(make_harvest(news, [("1.0", date(2020, 1, 1))]))
        assert report.version_coverage <= 1.0


class TestIsResultChanging:
    @pytest.mark.parametrize(
        "text",
        [
            "the variance was incorrect",
            "coxph gave the wrong answer",
            "fixed a bug in the standard errors",
            "p-values were erroneous",
        ],
    )
    def test_accepts_claims_of_a_wrong_number(self, text):
        assert is_result_changing(text)

    @pytest.mark.parametrize(
        "text",
        [
            "fixed a typo in the documentation",
            "corrected a broken url in the vignette",
            "improved the error message when x is missing",
            "added a new argument for weights",
            "the function is now faster",
        ],
    )
    def test_rejects_inert_and_non_claims(self, text):
        assert not is_result_changing(text)


class TestAffectedFunctions:
    def test_restricted_to_the_package_exports(self):
        # The base-R utilities a changelog mentions in passing must not count,
        # or `length` outranks every estimator in the ecosystem.
        text = "survfit uses both unique() and table() in various places"
        assert affected_functions(text, {"survfit", "coxph"}) == ["survfit"]

    def test_reads_backticked_names(self):
        text = "Bug fix in `vcovCL(..., type = 'HC2')` for `glm` objects"
        assert "vcovCL" in affected_functions(text, {"vcovCL", "vcovHC"})

    def test_reads_bare_prose_names(self):
        # survival writes "Fix a bug in survfit" far more often than "survfit()".
        text = "Fix a bug in survfit pointed out by a user"
        assert affected_functions(text, {"survfit", "coxph"}) == ["survfit"]

    def test_english_prose_is_not_mistaken_for_a_function(self):
        text = "the variance was incorrect for some models"
        assert affected_functions(text, {"coxph", "survfit"}) == []

    def test_display_functions_are_excluded(self):
        # A fix to a table formatter changes rendering, not coefficients.
        text = "fix display bug in etable() and in summary()"
        assert affected_functions(text, {"etable", "summary", "feols"}) == []


class TestBuildBugs:
    def test_ranks_by_distinct_scripts_exposed(self):
        entries = [
            Entry("p", "1.0", date(2020, 1, 1), "bug in rare() gave wrong values", 0),
            Entry("p", "1.1", date(2020, 2, 1), "bug in common() was incorrect", 0),
        ]
        exports = {"p": {"rare", "common"}}
        index = {"rare": {"a.R"}, "common": {"a.R", "b.R", "c.R"}}
        bugs, funnel = build_bugs(entries, exports, index)
        assert [b.functions[0] for b in bugs] == ["common", "rare"]
        assert bugs[0].total_exposed == 3
        assert funnel.result_changing == 2

    def test_funnel_narrows_and_records_each_drop(self):
        entries = [
            Entry("p", "1.0", None, "fixed a typo in the docs", 0),
            Entry("p", "1.0", None, "bug in notexported() was incorrect", 1),
            Entry("p", "1.0", None, "bug in uncalled() was incorrect", 2),
            Entry("p", "1.0", None, "bug in called() was incorrect", 3),
        ]
        bugs, funnel = build_bugs(
            entries, {"p": {"uncalled", "called"}}, {"called": {"a.R"}}
        )
        assert funnel.entries == 4
        assert funnel.result_changing == 3
        assert funnel.with_named_function == 2
        assert funnel.with_corpus_exposure == 1
        assert len(bugs) == 1

    def test_scripts_are_deduplicated_across_functions(self):
        entries = [
            Entry("p", "1.0", None, "bug in aa() and bb() were incorrect", 0),
        ]
        bugs, _ = build_bugs(
            entries, {"p": {"aa", "bb"}}, {"aa": {"x.R"}, "bb": {"x.R", "y.R"}}
        )
        assert bugs[0].total_exposed == 2
