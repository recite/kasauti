"""Which functions to probe, chosen by the corpus rather than by memory."""

from pathlib import Path

import pytest

from kasauti.archaeology.battery import apportion, build, read_frame, write_batteries

ROOT = Path(__file__).resolve().parents[1]

#: `(function, owners, scripts)`, as `read_frame` yields them.
FRAME = [
    ("length", ["Matrix"], 3268),
    ("felm", ["lfe"], 245),
    ("vcovHC", ["sandwich", "plm"], 76),
    ("tidy", ["broom"], 60),
    ("plm", ["plm"], 30),
    ("getfe", ["lfe"], 30),
    ("obscure", ["lfe"], 0),
]

USAGE = {"sandwich": 421, "plm": 189, "lfe": 222, "Matrix": 65, "broom": 40}


class TestFilters:
    def test_a_base_r_name_is_not_a_probe(self):
        # `Matrix` exports `length`, and the frame credits it with 3,268 scripts.
        # Unfiltered, its battery would be base-R primitives and nothing else.
        battery = build("Matrix", FRAME, shadowed={"length"}, excluded=set())
        assert [p.function for p in battery.probes] == []

    def test_a_non_computing_name_is_not_a_probe(self):
        battery = build("broom", FRAME, shadowed=set(), excluded={"tidy"})
        assert [p.function for p in battery.probes] == []

    def test_a_function_nobody_calls_does_not_qualify(self):
        battery = build("lfe", FRAME, shadowed=set(), excluded=set(), usage=USAGE)
        assert "obscure" not in [p.function for p in battery.probes]

    def test_the_most_called_function_leads(self):
        battery = build("lfe", FRAME, shadowed=set(), excluded=set(), usage=USAGE)
        assert battery.probes[0].function == "felm"


class TestApportion:
    def test_an_uncontested_name_keeps_its_whole_count(self):
        assert apportion(245, ["lfe"], "lfe", USAGE) == 245.0

    def test_a_contested_name_splits_by_corpus_usage(self):
        # `vcovHC` belongs to sandwich in the corpus far more often than to plm,
        # and crediting both with all 76 put plm's battery on somebody else's
        # function.
        assert apportion(76, ["sandwich", "plm"], "sandwich", USAGE) == pytest.approx(
            76 * 421 / 610
        )
        assert apportion(76, ["sandwich", "plm"], "plm", USAGE) == pytest.approx(
            76 * 189 / 610
        )

    def test_the_split_conserves_the_total(self):
        owners = ["sandwich", "plm"]
        assert sum(apportion(76, owners, name, USAGE) for name in owners) == (
            pytest.approx(76)
        )

    def test_owners_nobody_loads_split_evenly(self):
        assert apportion(10, ["a", "b"], "a", {}) == 5.0


class TestApportionmentChangesTheChoice:
    def test_a_contested_name_can_fall_below_the_package_own_function(self):
        # The whole reason apportionment exists. plm's battery led with vcovHC
        # at a face value of 76; apportioned it is 23.5 and `plm()` at 30 wins.
        battery = build("plm", FRAME, shadowed=set(), excluded=set(), usage=USAGE)
        assert battery.probes[0].function == "plm"

    def test_a_contested_name_the_package_dominates_survives(self):
        # And the reason dropping contested names outright is wrong: it cost
        # `lme4` its `lmer`, the one function anyone sweeps `lme4` for.
        battery = build("sandwich", FRAME, shadowed=set(), excluded=set(), usage=USAGE)
        assert battery.probes[0].function == "vcovHC"


class TestCoverage:
    def test_coverage_is_the_share_of_this_package_calls_the_battery_reaches(self):
        battery = build(
            "lfe", FRAME, shadowed=set(), excluded=set(), usage=USAGE, size=1
        )
        assert battery.calls == pytest.approx(275.0)
        assert battery.coverage == pytest.approx(245 / 275)

    def test_a_package_the_corpus_never_calls_has_zero_coverage_not_an_error(self):
        battery = build("nobody", FRAME, shadowed=set(), excluded=set())
        assert battery.coverage == 0.0
        assert battery.probes == []


class TestArtifact:
    def test_every_candidate_is_written_chosen_or_not(self, tmp_path):
        # A battery is a coverage claim, and a claim whose alternatives are
        # invisible cannot be argued with.
        battery = build(
            "lfe", FRAME, shadowed=set(), excluded=set(), usage=USAGE, size=1
        )
        path = tmp_path / "batteries.csv"
        write_batteries([battery], path)

        lines = path.read_text().strip().splitlines()
        assert len(lines) - 1 == len(battery.offered)
        assert sum("," + "1," in line for line in lines[1:]) >= 1


def test_the_real_frame_yields_the_package_own_functions():
    """Read against the checked-in frame, because the filters exist for it.

    Before the shadow set was applied here, the top of `Matrix`'s battery was
    `length`, `names`, `rep`, and `is.na` -- 3,268 scripts of base R credited to
    a linear-algebra package.
    """
    path = ROOT / "data/frame/sampling_frame.csv"
    if not path.exists():
        pytest.skip("`kasauti frame build` has not been run")
    frame = read_frame(path)

    names = {name for name, _, _ in frame}
    assert "felm" in names, "the frame no longer holds lfe's headline function"

    lfe = build("lfe", frame, shadowed=set(), excluded=set(), usage={"lfe": 222})
    assert lfe.probes[0].function == "felm"
