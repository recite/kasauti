"""A census over releases, rather than over what a maintainer wrote down."""

import json
from datetime import date
from pathlib import Path

import pytest

from kasauti.archaeology.sweep import (
    GAP,
    OBSERVED,
    Observation,
    Timeline,
    _observe,
    differences,
    find_changes,
)

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-8


def seen(version: str, year: int, **quantities) -> Observation:
    """An observed release holding these numbers."""
    return Observation(version, date(year, 1, 1), OBSERVED, "", dict(quantities))


def missed(version: str, year: int, why: str = "build failed") -> Observation:
    """A release that could not be evaluated."""
    return Observation(version, date(year, 1, 1), GAP, why)


class TestDifferences:
    def test_a_moved_quantity_is_named(self):
        moved, largest = differences({"se": 1.0}, {"se": 2.0}, TOL)
        assert moved == ["se"]
        assert largest == pytest.approx(0.5)

    def test_agreement_moves_nothing(self):
        assert differences({"se": 1.0}, {"se": 1.0}, TOL) == ([], 0.0)

    def test_a_quantity_that_appears_or_vanishes_counts(self):
        moved, _ = differences({"a": 1.0, "b": 2.0}, {"a": 1.0, "c": 3.0}, TOL)
        assert moved == ["-b", "+c"]


class TestFindChanges:
    def test_a_stable_history_has_no_change_points(self):
        history = [seen("1.0", 2010, se=1.0), seen("1.1", 2011, se=1.0)]
        assert find_changes("p", "probe.R", history, TOL) == []

    def test_the_change_is_dated_to_the_first_release_holding_the_new_value(self):
        history = [
            seen("1.0", 2010, se=1.0),
            seen("1.1", 2011, se=1.0),
            seen("1.2", 2012, se=2.0),
        ]
        (change,) = find_changes("p", "probe.R", history, TOL)
        assert (change.after, change.at) == ("1.1", "1.2")
        assert change.at_on == date(2012, 1, 1)
        assert change.exact

    def test_a_gap_widens_the_interval_rather_than_splitting_the_timeline(self):
        # The rule the whole design rests on. A release that will not build is
        # not evidence of stability, and comparing only adjacent releases would
        # either drop the change or date it to the wrong side of the gap.
        history = [
            seen("1.0", 2010, se=1.0),
            missed("1.1", 2011),
            missed("1.2", 2012),
            seen("1.3", 2013, se=2.0),
        ]
        (change,) = find_changes("p", "probe.R", history, TOL)
        assert (change.after, change.at) == ("1.0", "1.3")
        assert change.gaps == 2
        assert not change.exact

    def test_a_gap_never_becomes_a_change_of_its_own(self):
        # Treating "could not evaluate" as a value would put a change point at
        # every build failure and manufacture bugs out of a toolchain.
        history = [
            seen("1.0", 2010, se=1.0),
            missed("1.1", 2011),
            seen("1.2", 2012, se=1.0),
        ]
        assert find_changes("p", "probe.R", history, TOL) == []

    def test_a_history_that_is_entirely_gaps_yields_nothing(self):
        history = [missed("1.0", 2010), missed("1.1", 2011)]
        assert find_changes("p", "probe.R", history, TOL) == []

    def test_every_change_is_recorded_not_just_the_first(self):
        history = [
            seen("1.0", 2010, se=1.0),
            seen("1.1", 2011, se=2.0),
            seen("1.2", 2012, se=3.0),
        ]
        assert [c.at for c in find_changes("p", "probe.R", history, TOL)] == [
            "1.1",
            "1.2",
        ]


class TestObserve:
    def test_a_clean_run_is_observed(self):
        result = {"status": "ok", "quantities": {"se": 1.0}}
        found = _observe("1.0", date(2010, 1, 1), result)
        assert found.state == OBSERVED
        assert found.quantities == {"se": 1.0}

    def test_a_version_that_builds_and_will_not_run_is_a_gap(self):
        # `psych` 1.5.8 installs cleanly and then trips a check R tightened in
        # 4.2. Buildable and unusable are different facts and both are gaps.
        result = {"status": "error", "error": "the condition has length > 1"}
        found = _observe("1.5.8", date(2015, 8, 30), result)
        assert found.state == GAP
        assert "length > 1" in found.detail

    def test_a_run_that_returned_no_number_is_a_gap_not_a_value(self):
        result = {"status": "ok", "quantities": {"se": None}}
        assert _observe("1.0", None, result).state == GAP

    def test_no_result_at_all_is_a_gap(self):
        assert _observe("1.0", None, None).state == GAP


class TestTimeline:
    def test_observed_and_gaps_are_counted_separately(self):
        timeline = Timeline(
            package="p",
            probe="probe.R",
            observations=[seen("1.0", 2010, se=1.0), missed("1.1", 2011)],
        )
        assert (timeline.observed, timeline.gaps) == (1, 1)

    def test_a_timeline_writes_every_release_including_the_gaps(self, tmp_path):
        # The gaps are the coverage statement. A timeline that stored only what
        # it could evaluate would look like a complete history of the package.
        timeline = Timeline(
            package="sandwich",
            probe="vcovhc_mlm.R",
            observations=[seen("2.4-0", 2017, se=1.0), missed("2.2-1", 2009)],
        )
        path = timeline.write(tmp_path)
        payload = json.loads(path.read_text())
        assert path.name == "vcovhc_mlm.json"
        assert len(payload["observations"]) == 2
        assert payload["gaps"] == 1


def test_the_sandwich_sweep_recovers_the_bisect_by_a_different_method():
    """One change point in nine years, exactly where the bisect put it.

    The bisect drove the record's own reproducer down a binary search and
    concluded: introduced 2.2-4, fixed 2.5-0, arrived with the feature. The sweep
    knows nothing of that -- it runs a generic probe against every release and
    reports where numbers moved. If the two disagree, one of them is wrong.
    """
    path = ROOT / "sweeps/sandwich/vcovhc_mlm.json"
    if not path.exists():
        pytest.skip("the sandwich sweep has not been run")
    payload = json.loads(path.read_text())

    changes = payload["changes"]
    assert len(changes) == 1, "sandwich's history holds exactly one change here"
    assert changes[0]["at"] == "2.5-0"
    assert changes[0]["after"] == "2.4-0"
    assert changes[0]["exact"], "no unevaluable release sits inside the interval"

    states = {o["version"]: o for o in payload["observations"]}
    assert states["2.2-4"]["state"] == OBSERVED
    for version in ("2.2-1", "2.2-2", "2.2-3"):
        # The bisect called these ABSENT: no `mlm` method existed yet. The sweep
        # sees the same thing from the other side, as a gap whose reason says so.
        assert states[version]["state"] == GAP
        assert "no applicable method" in states[version]["detail"]
