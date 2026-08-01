"""The bug record's lifecycle, and resolving scripts to papers."""

from datetime import date

import pytest
import yaml

from kasauti.archaeology.bugs import (
    Bug,
    BugError,
    Exposure,
    advance,
    discover_bugs,
    load_bug,
    render_index,
    validate,
    write_bug,
)
from kasauti.archaeology.link import looks_vendored, probe_exposure
from kasauti.archaeology.papers import (
    Paper,
    PaperLinkage,
    link_scripts,
    load_dataverse_index,
    repo_id_from_path,
    zenodo_paper,
)


def make_bug(tmp_path, **kwargs) -> Bug:
    defaults = {
        "id": "pkg-1.0-thing",
        "package": "pkg",
        "fixed_in": "1.0",
        "conditions": "only with weights",
    }
    directory = tmp_path / defaults["id"]
    directory.mkdir(exist_ok=True)
    return Bug(**{**defaults, "directory": directory, **kwargs})


class TestValidation:
    def test_conditions_are_mandatory(self, tmp_path):
        # Without conditions the exposure count cannot be narrowed, and an
        # un-narrowed count has overstated reach every time it was checked.
        with pytest.raises(BugError, match="conditions is required"):
            validate(make_bug(tmp_path, conditions="   "))

    def test_id_must_match_its_directory(self, tmp_path):
        bug = make_bug(tmp_path)
        bug.id = "something-else"
        with pytest.raises(BugError, match="does not match its directory"):
            validate(bug)

    def test_verified_needs_a_case_beside_it(self, tmp_path):
        bug = make_bug(tmp_path, status="VERIFIED", magnitude="sign flip")
        with pytest.raises(BugError, match=r"no case\.yaml"):
            validate(bug)

    def test_verified_needs_a_recorded_magnitude(self, tmp_path):
        bug = make_bug(tmp_path, status="VERIFIED")
        (bug.directory / "case.yaml").write_text("id: x\n")
        with pytest.raises(BugError, match="magnitude is empty"):
            validate(bug)

    def test_verified_with_case_and_magnitude_passes(self, tmp_path):
        bug = make_bug(tmp_path, status="VERIFIED", magnitude="sign flip")
        (bug.directory / "case.yaml").write_text("id: x\n")
        validate(bug)

    def test_verified_does_not_require_a_probe_count(self, tmp_path):
        # Verification and exposure-counting are independent axes. Requiring a
        # probe count here made a VERIFIED record unloadable until probed,
        # which is the deadlock this test pins down.
        bug = make_bug(tmp_path, status="VERIFIED", magnitude="sign flip")
        (bug.directory / "case.yaml").write_text("id: x\n")
        assert bug.exposure.scripts_meeting_probe is None
        validate(bug)

    def test_probed_does_require_a_probe_count(self, tmp_path):
        with pytest.raises(BugError, match="no probe count"):
            validate(make_bug(tmp_path, status="PROBED"))

    def test_linked_requires_a_paper_count(self, tmp_path):
        bug = make_bug(
            tmp_path, status="LINKED", exposure=Exposure(scripts_meeting_probe=3)
        )
        with pytest.raises(BugError, match="no paper count"):
            validate(bug)

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("status", "MAYBE", "unknown status"),
            ("category", "NONSENSE", "unknown category"),
            ("severity", "CATASTROPHIC", "unknown severity"),
        ],
    )
    def test_rejects_unknown_enumerations(self, tmp_path, field, value, match):
        with pytest.raises(BugError, match=match):
            validate(make_bug(tmp_path, **{field: value}))


class TestLifecycle:
    def test_status_advances(self, tmp_path):
        bug = make_bug(tmp_path)
        assert advance(bug, "PROBED").status == "PROBED"

    def test_status_does_not_go_backwards(self, tmp_path):
        bug = make_bug(tmp_path, status="LINKED")
        assert advance(bug, "PROBED").status == "LINKED"

    def test_a_verdict_can_always_be_recorded(self, tmp_path):
        # Re-probing a verified bug must not demote it, and a verdict must be
        # settable regardless of how far the pipeline got.
        bug = make_bug(tmp_path)
        assert advance(bug, "NOT_REPRODUCED").status == "NOT_REPRODUCED"

    def test_censored_when_the_introducing_version_is_unknown(self, tmp_path):
        assert make_bug(tmp_path).censored
        assert not make_bug(tmp_path, introduced_on=date(2020, 1, 1)).censored

    def test_rank_orders_by_severity_then_exposure(self, tmp_path):
        low_wide = make_bug(
            tmp_path, severity="LOW", exposure=Exposure(scripts_meeting_probe=500)
        )
        high_narrow = make_bug(
            tmp_path, severity="HIGH", exposure=Exposure(scripts_meeting_probe=1)
        )
        assert high_narrow.rank > low_wide.rank

    def test_narrowed_falls_back_to_the_function_count(self):
        assert Exposure(scripts_calling_function=76).narrowed == 76
        assert (
            Exposure(scripts_calling_function=76, scripts_meeting_probe=1).narrowed == 1
        )


class TestRoundTrip:
    def test_write_then_load(self, tmp_path):
        bug = make_bug(
            tmp_path,
            fixed_on=date(2018, 8, 17),
            functions=["vcovHC"],
            condition_probe=r"lm\s*\(\s*cbind\s*\(",
            severity="HIGH",
            exposure=Exposure(scripts_calling_function=76, scripts_meeting_probe=1),
        )
        write_bug(bug)
        loaded = load_bug(bug.directory)
        assert loaded.fixed_on == date(2018, 8, 17)
        assert loaded.condition_probe == r"lm\s*\(\s*cbind\s*\("
        assert loaded.exposure.scripts_meeting_probe == 1

    def test_write_refuses_an_invalid_record(self, tmp_path):
        with pytest.raises(BugError):
            write_bug(make_bug(tmp_path, conditions=""))

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(BugError, match=r"no bug\.yaml"):
            load_bug(tmp_path)

    def test_unparseable_date_raises(self, tmp_path):
        directory = tmp_path / "pkg-1.0-thing"
        directory.mkdir()
        (directory / "bug.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "pkg-1.0-thing",
                    "package": "pkg",
                    "fixed_in": "1.0",
                    "conditions": "x",
                    "fixed_on": "not-a-date",
                }
            )
        )
        with pytest.raises(BugError, match="cannot parse date"):
            load_bug(directory)


class TestIndex:
    def test_negative_results_are_kept_and_shown(self, tmp_path):
        bug = make_bug(
            tmp_path, status="NOT_REPRODUCED", magnitude="no difference observed"
        )
        rendered = render_index([bug])
        assert "Did not survive verification" in rendered
        assert "no difference observed" in rendered

    def test_censored_papers_are_flagged(self, tmp_path):
        bug = make_bug(tmp_path, exposure=Exposure(papers_in_window=4))
        rendered = render_index([bug])
        assert "4*" in rendered
        assert "left-censored" in rendered

    def test_discover_is_ranked_and_empty_root_is_fine(self, tmp_path):
        assert discover_bugs(tmp_path / "nope") == []


class TestProbeExposure:
    def test_narrows_to_matching_scripts(self, tmp_path):
        wide = tmp_path / "wide.R"
        wide.write_text("m <- lm(y ~ x)\nvcovHC(m)\n")
        narrow = tmp_path / "narrow.R"
        narrow.write_text("m <- lm(cbind(y1, y2) ~ x)\nvcovHC(m)\n")
        index = {"vcovHC": {str(wide), str(narrow)}}

        result = probe_exposure(["vcovHC"], r"lm\s*\(\s*cbind\s*\(", index)
        assert len(result.calling) == 2
        assert result.matching == [str(narrow)]
        assert result.narrowing == 0.5

    def test_no_probe_reports_every_caller(self, tmp_path):
        # "We could not narrow this" must not be rendered as "all of them
        # qualify" -- both counts come back equal and the probe string is empty.
        script = tmp_path / "a.R"
        script.write_text("vcovHC(m)\n")
        result = probe_exposure(["vcovHC"], None, {"vcovHC": {str(script)}})
        assert result.matching == result.calling
        assert result.probe == ""

    def test_vendored_library_code_is_excluded(self, tmp_path):
        # A QJE archive in the corpus bundles scikit-learn's own test suite along
        # with 3,838 other site-packages files. Counting `test_supervised.py` as
        # a paper exercising the buggy function gets it exactly backwards: that
        # is the library testing itself.
        analysis = tmp_path / "analysis.py"
        analysis.write_text("nmi(a, b)\n")
        vendored = tmp_path / "test_supervised.py"
        vendored.write_text("nmi(a, b)\n")
        result = probe_exposure(["nmi"], None, {"nmi": {str(analysis), str(vendored)}})
        assert result.calling == [str(analysis)]
        assert result.vendored == [str(vendored)]

    @pytest.mark.parametrize(
        "name",
        [
            "test_supervised.py",
            "__init___106.py",
            "__config__.py",
            "setup.py",
            "conftest.py",
            "_version.py",
        ],
    )
    def test_library_filenames_are_recognised(self, name):
        assert looks_vendored(f"/archive/{name}")

    @pytest.mark.parametrize(
        "name", ["analysis.R", "main.py", "figures.R", "estimate_effects.py"]
    )
    def test_analysis_filenames_are_kept(self, name):
        assert not looks_vendored(f"/archive/{name}")

    def test_unreadable_scripts_are_counted_not_matched(self, tmp_path):
        missing = str(tmp_path / "gone.R")
        result = probe_exposure(["vcovHC"], "cbind", {"vcovHC": {missing}})
        assert result.unreadable == [missing]
        assert result.matching == []


class TestPaperResolution:
    def test_parses_both_corpus_sources(self):
        assert repo_id_from_path("outputs/scripts/dataverse/TBKLWV/a.R") == (
            "dataverse",
            "TBKLWV",
        )
        assert repo_id_from_path("outputs/scripts/zenodo/10012820/a.R") == (
            "zenodo",
            "10012820",
        )

    def test_unknown_source_resolves_to_nothing(self):
        assert repo_id_from_path("outputs/scripts/icpsr/1234/a.R") is None

    def test_zenodo_doi_is_derived_without_an_api_call(self):
        paper = zenodo_paper("10012820")
        assert paper.doi == "https://doi.org/10.5281/zenodo.10012820"

    def test_dataverse_index_reads_softverse_tables(self, tmp_path):
        (tmp_path / "ajps_datasets.csv").write_text(
            "identifier,persistentUrl,publisher,publicationDate\n"
            "DVN/ABC123,https://doi.org/10.7910/DVN/ABC123,"
            "Harvard Dataverse,2015-04-06\n"
        )
        index = load_dataverse_index(tmp_path)
        assert index["ABC123"].published == date(2015, 4, 6)
        assert index["ABC123"].journal == "ajps"

    def test_link_reports_unresolvable_scripts_rather_than_dropping_them(self):
        linkage = link_scripts(
            ["outputs/scripts/icpsr/1/a.R", "outputs/scripts/zenodo/999/a.R"], {}
        )
        assert len(linkage.papers) == 1
        assert linkage.unresolved == ["outputs/scripts/icpsr/1/a.R"]
        assert linkage.by_source == {"zenodo": 1}

    def test_a_dataverse_id_absent_from_the_index_is_unresolved(self):
        linkage = link_scripts(["outputs/scripts/dataverse/NOPE/a.R"], {})
        assert linkage.papers == []
        assert len(linkage.unresolved) == 1


class TestWindow:
    def test_published_after_the_fix_is_out_of_window(self):
        # The real sandwich finding: the one exposed script was published in
        # 2023, five years after the 2018 fix.
        paper = Paper("x", "zenodo", published=date(2023, 10, 17))
        assert not paper.in_window(date(2018, 8, 17), None)

    def test_published_before_the_fix_is_in_window_when_censored(self):
        paper = Paper("x", "zenodo", published=date(2017, 1, 1))
        assert paper.in_window(date(2018, 8, 17), None)

    def test_before_the_introducing_version_is_out_of_window(self):
        paper = Paper("x", "zenodo", published=date(2015, 1, 1))
        assert not paper.in_window(date(2018, 8, 17), date(2016, 1, 1))

    def test_undated_archives_are_never_in_window(self):
        # Counting them would inflate the numerator with archives that cannot
        # be placed on the timeline at all.
        assert not Paper("x", "zenodo").in_window(date(2018, 8, 17), None)


class TestAnalysisLag:
    def test_a_lag_moves_an_archive_into_the_window(self):
        # The real sandwich 3.0-2 row. Published six weeks after the fix, so out
        # of window on publication date -- but an analysis run any earlier than
        # that was done while the bug was live.
        paper = Paper("HWVUER", "dataverse", published=date(2022, 7, 28))
        fixed = date(2022, 6, 15)
        assert not paper.in_window(fixed, None)
        assert paper.in_window(fixed, None, lag_years=1)

    def test_the_left_edge_moves_too(self):
        # A lag shifts the analysis backwards, so it can fall out of the window
        # on the *early* side once the introducing version is known. Applying
        # the lag to only one edge would manufacture exposure.
        paper = Paper("x", "zenodo", published=date(2017, 6, 1))
        assert paper.in_window(date(2018, 1, 1), date(2016, 1, 1))
        assert not paper.in_window(date(2018, 1, 1), date(2016, 1, 1), lag_years=2)

    def test_an_undated_archive_stays_out_at_every_lag(self):
        paper = Paper("x", "zenodo")
        assert all(not paper.in_window(date(2020, 1, 1), None, lag) for lag in range(4))

    def test_a_leap_day_does_not_raise(self):
        # 2020-02-29 has no counterpart in 2019; walking back a day is a
        # rounding choice, losing the archive is a bug.
        paper = Paper("x", "zenodo", published=date(2020, 2, 29))
        assert paper.analysed_on(1) == date(2019, 2, 28)

    def test_an_undated_fix_yields_no_curve_rather_than_zeros(self):
        # Zero would read as "no papers affected"; the truth is "not
        # determinable", which is the same conflation papers_in_window avoids.
        linkage = PaperLinkage(
            [Paper("x", "zenodo", published=date(2020, 1, 1))], [], {}
        )
        assert linkage.window_curve(None, None) is None

    def test_the_curve_is_monotone_when_the_window_is_censored(self):
        # With no left edge, a longer lag can only move archives in, never out.
        papers = [
            Paper(str(y), "zenodo", published=date(y, 6, 1)) for y in (2019, 2021, 2023)
        ]
        curve = PaperLinkage(papers, [], {}).window_curve(date(2022, 1, 1), None)
        assert curve is not None
        counts = [curve[lag] for lag in sorted(curve)]
        assert counts == sorted(counts)


def test_every_verified_record_still_runs_through_the_shared_harness():
    """The split moved the runner out; this is what would notice if it broke.

    kasauti no longer owns `schema`, `loader`, `runner`, `compare`, `oracles`, or
    `report` -- they live in milaan, because a version regression and a
    cross-implementation comparison are the same kind of object. A verified
    record is required to carry a `case.yaml`, so if the dependency ever stops
    resolving, this fails loudly rather than the suite quietly finding no cases.
    """
    from milaan.loader import discover_cases

    from kasauti.archaeology.bugs import discover_bugs
    from kasauti.cli import ROOT

    verified = {b.id for b in discover_bugs(ROOT / "bugs") if b.status == "VERIFIED"}
    discovered = {
        c.directory.relative_to(ROOT / "bugs").as_posix()
        for c in discover_cases(ROOT / "bugs")
    }
    assert verified, "no verified records found"
    assert verified <= discovered
    assert all(c.family == "version_regression" for c in discover_cases(ROOT / "bugs"))


class TestLifetime:
    def test_lifetime_needs_both_ends(self, tmp_path):
        # Null, never zero: a bug whose start was never established did not
        # live for no time, and reporting 0 would put it at the safe end of a
        # distribution it does not belong in.
        assert make_bug(tmp_path, fixed_on=date(2022, 6, 15)).lifetime_days is None
        assert make_bug(tmp_path, introduced_on=date(2020, 1, 1)).lifetime_days is None

    def test_lifetime_is_measured_in_days(self, tmp_path):
        bug = make_bug(
            tmp_path, introduced_on=date(2020, 1, 1), fixed_on=date(2022, 6, 15)
        )
        assert bug.lifetime_days == 896

    def test_evidence_defaults_to_unknown_and_round_trips(self, tmp_path):
        bug = make_bug(tmp_path)
        assert bug.introduction_evidence == "unknown"
        bug.introduced_in = "2.4-0"
        bug.introduced_on = date(2015, 1, 1)
        bug.introduction_evidence = "bisected"
        write_bug(bug)
        assert load_bug(bug.directory).introduction_evidence == "bisected"

    def test_a_dated_introduction_closes_the_window(self, tmp_path):
        # The whole reason to bisect: papers_in_window currently means
        # "published before the fix" with no lower bound at all.
        assert make_bug(tmp_path).censored
        assert not make_bug(tmp_path, introduced_on=date(2015, 1, 1)).censored
