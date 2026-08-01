"""Testing a changelog claim without first committing to publishing it."""

import json
from datetime import date
from pathlib import Path

import pytest

from kasauti.archaeology.screen import (
    MOVED,
    NOT_TRIGGERED,
    UNEVALUABLE,
    Request,
    Screen,
    bracket,
    judge,
    relative_difference,
    version_key,
)

ROOT = Path(__file__).resolve().parents[1]

RELEASES = [
    ("2.3-4", date(2015, 9, 24)),
    ("2.4-0", date(2017, 8, 1)),
    ("2.5-0", date(2018, 8, 17)),
]


def ok(quantities: dict, control: bool = True, says: str = "the condition held"):
    """A backend result that ran and declared its control."""
    return {
        "status": "ok",
        "quantities": quantities,
        "diagnostics": {"control": control, "control_says": says},
    }


class TestBracket:
    def test_the_release_immediately_before_the_fix(self):
        before, after, exact = bracket(RELEASES, "2.5-0")
        assert before == ("2.4-0", date(2017, 8, 1))
        assert after == ("2.5-0", date(2018, 8, 17))
        assert exact

    def test_a_fix_version_cran_never_shipped_is_straddled(self):
        # `survival`'s NEWS is organised under headings like 2.35 that are not
        # releases, and six of nine fix versions on its shortlist have no archive
        # tarball. Discarding those claims would drop the package with the most
        # candidates; straddling them keeps the claim testable and says so.
        before, after, exact = bracket(RELEASES, "2.4-5")
        assert before == ("2.4-0", date(2017, 8, 1))
        assert after == ("2.5-0", date(2018, 8, 17))
        assert not exact

    def test_the_first_release_has_nothing_before_it(self):
        assert bracket(RELEASES, "2.3-4")[0] is None

    def test_a_version_after_every_release_has_nothing_after_it(self):
        assert bracket(RELEASES, "9.9-9")[1] is None


class TestVersionKey:
    def test_hyphenated_components_order_numerically(self):
        # `1.5-13` sorts before `1.5-9` as a string, and after it as a version.
        assert version_key("1.5-13") > version_key("1.5-9")

    def test_a_four_component_version_orders(self):
        assert version_key("2.4.6.26") > version_key("2.4.3")


class TestJudge:
    def test_a_changed_quantity_is_moved(self):
        verdict, detail, moved, largest = judge(ok({"se": 1.0}), ok({"se": 2.0}))
        assert verdict == MOVED
        assert moved == ["se"]
        assert largest == pytest.approx(0.5)
        assert "1 of 1" in detail

    def test_agreement_is_not_triggered_rather_than_refuted(self):
        # The distinction the whole tier turns on. A fixture that saw nothing
        # move has not shown the changelog was wrong; it has shown its own
        # fixture did not reach the code.
        verdict, detail, moved, _ = judge(ok({"se": 1.0}), ok({"se": 1.0}))
        assert verdict == NOT_TRIGGERED
        assert moved == []
        assert "did not reach the defect" in detail

    def test_only_the_affected_quantities_are_listed(self):
        _, _, moved, _ = judge(
            ok({"within": 1.0, "cross": 1.0}), ok({"within": 1.0, "cross": -1.0})
        )
        assert moved == ["cross"]

    def test_a_difference_below_the_band_is_noise(self):
        verdict, _, _, _ = judge(ok({"se": 1.0}), ok({"se": 1.0 + 1e-12}))
        assert verdict == NOT_TRIGGERED

    def test_a_quantity_that_appears_counts_as_a_change(self):
        # What a function returns changing shape is a changed result by any
        # reading a user would recognise.
        verdict, detail, moved, _ = judge(ok({"se": 1.0}), ok({"se": 1.0, "df": 7.0}))
        assert verdict == MOVED
        assert moved == ["+df"]
        assert "appeared or vanished" in detail


class TestTheControl:
    def test_a_fixture_with_no_control_cannot_say_nothing_moved(self):
        result = {"status": "ok", "quantities": {"se": 1.0}, "diagnostics": {}}
        verdict, detail, _, _ = judge(result, result)
        assert verdict == UNEVALUABLE
        assert "no positive control" in detail

    def test_a_failed_control_is_unevaluable_not_untriggered(self):
        # Reporting NOT_TRIGGERED here would record "the changelog's condition
        # produced no change" when what happened is that the condition was never
        # set up.
        stated = "lm(cbind(y, y2) ~ .) is a multivariate lm"
        verdict, detail, _, _ = judge(
            ok({"se": 1.0}, control=False, says=stated),
            ok({"se": 1.0}, control=False, says=stated),
        )
        assert verdict == UNEVALUABLE
        assert stated in detail

    def test_both_versions_must_pass_the_control(self):
        verdict, detail, _, _ = judge(ok({"se": 1.0}, control=False), ok({"se": 2.0}))
        assert verdict == UNEVALUABLE
        assert detail.startswith("before:")


class TestUnevaluable:
    def test_a_run_that_errored(self):
        errored = {"status": "error", "error": "object 'y2' not found"}
        verdict, detail, _, _ = judge(errored, ok({"se": 1.0}))
        assert verdict == UNEVALUABLE
        assert "y2" in detail

    def test_a_missing_run(self):
        assert judge(None, ok({"se": 1.0}))[0] == UNEVALUABLE

    def test_a_function_absent_from_the_predecessor_is_named_as_such(self):
        # Not a defect that was fixed -- a feature that arrived. The shortlist
        # misread the entry, and the screen says which way.
        errored = {
            "status": "error",
            "error": 'could not find function "vcovCL"',
        }
        verdict, detail, _, _ = judge(errored, ok({"se": 1.0}))
        assert verdict == UNEVALUABLE
        assert "does not exist in this version" in detail

    def test_two_runs_sharing_no_quantity(self):
        verdict, detail, _, _ = judge(ok({"a": 1.0}), ok({"b": 1.0}))
        assert verdict == UNEVALUABLE
        assert "share no comparable quantity" in detail


class TestRelativeDifference:
    def test_two_near_zeros_are_equal(self):
        # Comparing a denormal against an exact zero otherwise reports a huge
        # relative difference between two numbers that are zero for every use.
        assert relative_difference(0.0, 1e-14) == 0.0

    def test_a_sign_flip_is_a_large_difference(self):
        assert relative_difference(1.0, -1.0) == pytest.approx(2.0)


class TestArtifact:
    def test_a_screen_round_trips_through_json(self, tmp_path):
        screen = Screen(
            entry_id="sandwich@2.5-0#7",
            package="sandwich",
            before="2.4-0",
            after="2.5-0",
            before_on=date(2017, 8, 1),
            verdict=MOVED,
            moved=["vcovHC.y:x1.y2:x1"],
        )
        path = screen.write(tmp_path)
        found = json.loads(path.read_text())
        assert path.name == "sandwich-2.5-0-7.json"
        assert found["before_on"] == "2017-08-01"
        assert found["after_on"] is None
        assert found["moved"] == ["vcovHC.y:x1.y2:x1"]

    def test_the_slug_survives_the_punctuation_in_an_entry_id(self):
        assert (
            Request("psych@2.4.4#42", "psych", "2.4.4", "x.R").slug == "psych-2.4.4-42"
        )


def test_the_sandwich_screen_separates_the_cross_block_from_the_within_block():
    """The screen must recover a finding that was established by hand.

    `sandwich` 2.5-0 corrupted only the cross-equation blocks of `vcovHC.mlm`;
    the within-equation diagonal is bit-identical, which is the substantive half
    of that record and the part a changelog reader over-reads. If a mechanical
    dump plus a relative-difference comparison cannot recover that split, the
    screening tier is not measuring what the hand-built record measured.
    """
    path = ROOT / "screens/sandwich/sandwich-2.5-0-7.json"
    if not path.exists():
        pytest.skip("the sandwich screen has not been run")
    found = json.loads(path.read_text())

    assert found["verdict"] == MOVED

    def cross(quantity: str) -> bool:
        _, left, right = quantity.split(".")
        return left.split(":")[0] != right.split(":")[0]

    moved = set(found["moved"])
    every = set(found["quantities"]["after"])
    assert moved == {q for q in every if cross(q)}
    assert not any(cross(q) for q in every - moved)
