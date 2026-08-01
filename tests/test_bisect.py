"""Finding when a bug was introduced by running old versions."""

from datetime import date

from kasauti.archaeology.bisect import (
    ABSENT,
    BUGGY,
    FIXED,
    UNEVALUABLE,
    Probe,
    classify_run,
    search,
)

VERSIONS = [(f"1.{i}", date(2000 + i, 1, 1)) for i in range(12)]


def introduced_at(n: int):
    """Evaluator for a bug present from version 1.n onwards."""
    return lambda v, d: Probe(v, d, BUGGY if int(v.split(".")[1]) >= n else FIXED)


class TestSearch:
    def test_brackets_the_transition(self):
        found = search(VERSIONS, introduced_at(7))
        assert found.last_fixed.version == "1.6"
        assert found.first_buggy.version == "1.7"
        assert found.bracketed

    def test_costs_a_logarithmic_number_of_probes(self):
        # The whole point of bisecting rather than scanning: an R source install
        # takes minutes, so 4 probes over 12 versions is the difference between
        # a coffee break and an afternoon.
        assert len(search(VERSIONS, introduced_at(7)).probes) <= 5

    def test_an_unbuildable_version_widens_the_bracket_rather_than_deciding_it(self):
        # The old end of a version range is where source packages stop building.
        # Treating "cannot evaluate" as "not buggy" would date every
        # introduction to the last version that happened to compile.
        def evaluate(version, released):
            n = int(version.split(".")[1])
            if n in (5, 6):
                return Probe(version, released, UNEVALUABLE, "no build")
            return Probe(version, released, BUGGY if n >= 7 else FIXED)

        found = search(VERSIONS, evaluate)
        assert found.last_fixed.version == "1.4"
        assert found.first_buggy.version == "1.7"
        assert [p.version for p in found.unevaluable] == ["1.5", "1.6"]

    def test_buggy_all_the_way_back_is_not_bracketed(self):
        # The bug predates every version that still builds, so its introduction
        # was not measured -- it was merely not found, and the two must not be
        # reported the same way.
        found = search(VERSIONS, lambda v, d: Probe(v, d, BUGGY))
        assert found.first_buggy.version == "1.0"
        assert found.last_fixed is None
        assert not found.bracketed

    def test_nothing_evaluable_terminates(self):
        # The first version of this search walked outside the live window, so a
        # run of unevaluable versions left `low` and `high` unchanged and it
        # never terminated. It ran for ten minutes before being killed.
        found = search(VERSIONS, lambda v, d: Probe(v, d, UNEVALUABLE, "x"))
        assert not found.bracketed
        assert len(found.probes) == len(VERSIONS)

    def test_the_recorded_date_is_the_first_buggy_release(self):
        # Not the midpoint of the bracket: a date that is provably too late
        # narrows the exposure window, where an interpolated one inflates it.
        found = search(VERSIONS, introduced_at(7))
        assert found.introduced_on == date(2007, 1, 1)


class TestClassifyRun:
    BUGGY_REF = {"status": "ok", "quantities": {"se": 1.0, "t": 10.0}}
    FIXED_REF = {"status": "ok", "quantities": {"se": 2.0, "t": 5.0}}

    def test_matching_the_buggy_reference(self):
        observed = {"status": "ok", "quantities": {"se": 1.0, "t": 10.0}}
        assert classify_run(observed, self.BUGGY_REF, self.FIXED_REF)[0] == BUGGY

    def test_matching_the_fixed_reference(self):
        observed = {"status": "ok", "quantities": {"se": 2.0, "t": 5.0}}
        assert classify_run(observed, self.BUGGY_REF, self.FIXED_REF)[0] == FIXED

    def test_matching_neither_is_unevaluable_not_the_nearer_one(self):
        # An old version can differ from both for reasons unrelated to this
        # defect -- a changed default, a renamed argument. Assigning it to
        # whichever it resembles would invent a transition.
        observed = {"status": "ok", "quantities": {"se": 7.0, "t": 99.0}}
        outcome, detail = classify_run(observed, self.BUGGY_REF, self.FIXED_REF)
        assert outcome == UNEVALUABLE
        assert "neither" in detail

    def test_a_backend_that_errored_is_unevaluable(self):
        observed = {"status": "error", "error": "could not load package"}
        assert classify_run(observed, self.BUGGY_REF, self.FIXED_REF)[0] == UNEVALUABLE

    def test_no_result_at_all_is_unevaluable(self):
        assert classify_run(None, self.BUGGY_REF, self.FIXED_REF)[0] == UNEVALUABLE

    def test_references_that_agree_cannot_discriminate(self):
        # If the case's two reference outputs are identical on every shared
        # quantity, it cannot tell the versions apart and saying so is the only
        # honest answer.
        same = {"status": "ok", "quantities": {"se": 1.0}}
        outcome, detail = classify_run(same, same, same)
        assert outcome == UNEVALUABLE
        assert "indistinguishable" in detail


class TestAbsentIsNotUnevaluable:
    def test_a_missing_method_means_the_bug_had_not_arrived(self):
        # The sandwich bisect turned on this. `vcovHC` had no `mlm` method
        # before 2.2-4, so three versions errored -- and calling that
        # "unevaluable" left the bisect unbracketed after 19 probes. A bug in a
        # method nobody has written yet is not a bug.
        observed = {
            "status": "error",
            "error": "no applicable method for 'vcovHC' applied to an object of "
            "class \"c('mlm', 'lm')\"",
        }
        outcome, detail = classify_run(
            observed,
            {"status": "ok", "quantities": {"se": 1.0}},
            {"status": "ok", "quantities": {"se": 2.0}},
        )
        assert outcome == ABSENT
        assert "no applicable method" in detail

    def test_an_unexplained_error_stays_unevaluable(self):
        observed = {"status": "error", "error": "segfault in native code"}
        outcome, _ = classify_run(
            observed,
            {"status": "ok", "quantities": {"se": 1.0}},
            {"status": "ok", "quantities": {"se": 2.0}},
        )
        assert outcome == UNEVALUABLE

    def test_absent_bounds_the_search_like_fixed(self):
        def evaluate(version, released):
            n = int(version.split(".")[1])
            if n >= 7:
                return Probe(version, released, BUGGY)
            return Probe(version, released, ABSENT, "no applicable method")

        found = search(VERSIONS, evaluate)
        assert found.bracketed
        assert found.last_fixed.version == "1.6"
        assert found.first_buggy.version == "1.7"

    def test_arriving_with_the_feature_is_reported_distinctly(self):
        # "It was wrong when written" is a stronger and different claim from
        # "someone broke a working function", and the two must not be conflated.
        def absent_below(version, released):
            n = int(version.split(".")[1])
            return Probe(version, released, BUGGY if n >= 7 else ABSENT, "")

        assert search(VERSIONS, absent_below).arrived_with_the_feature
        assert not search(VERSIONS, introduced_at(7)).arrived_with_the_feature


def test_a_reproducer_that_swallows_errors_cannot_be_bisected():
    """Named as a limit of the case, not of the version under test.

    sandwich 3.0-2's backend wraps its call in `try(silent = TRUE)` and writes
    NA on failure. Against a version predating `vcovCL` that yields a clean run
    with every quantity null -- indistinguishable from a version where the code
    exists and broke. The bisect says so rather than guessing.
    """
    observed = {"status": "ok", "quantities": {"se": None, "t": None}}
    outcome, detail = classify_run(
        observed,
        {"status": "ok", "quantities": {"se": 1.0, "t": 10.0}},
        {"status": "ok", "quantities": {"se": 2.0, "t": 5.0}},
    )
    assert outcome == UNEVALUABLE
    assert "swallow" in detail
