"""Which packages get swept, and at what probability."""

from pathlib import Path

from kasauti.archaeology.sample import (
    Candidate,
    draw,
    read_sample,
    stratify,
    write_sample,
)

ROOT = Path(__file__).resolve().parents[1]


def candidates(n: int, compiled_every: int = 2) -> list[Candidate]:
    """`n` packages with descending corpus usage, alternating compilation."""
    return [
        Candidate(
            package=f"pkg{i:03d}",
            corpus=n - i,
            strong=i,
            compiled=(i % compiled_every == 0),
            releases=10 + i,
        )
        for i in range(n)
    ]


class TestStratify:
    def test_the_most_used_packages_are_taken_with_certainty(self):
        # A study of statistical software that sampled away MASS would be
        # answering a different question from the one asked.
        strata = stratify(candidates(60), per_stratum=3, certainty=8)
        head = strata[0]
        assert head.name == "certainty"
        assert head.probability == 1.0
        assert [c.package for c in head.members] == [f"pkg{i:03d}" for i in range(8)]

    def test_compilation_splits_every_usage_tier(self):
        # The strongest available predictor of whether a release builds at all.
        # A draw that came out mostly unbuildable would show up as a finding
        # about bug rates rather than as a failure of the design.
        names = {s.name for s in stratify(candidates(60), per_stratum=3)}
        assert "high/compiled" in names
        assert "high/pure-R" in names
        assert "low/pure-R" in names

    def test_a_cell_smaller_than_the_quota_is_taken_whole(self):
        few = [
            Candidate("a", 10, 1, True, 5),
            Candidate("b", 9, 1, False, 5),
            Candidate("c", 8, 1, False, 5),
        ]
        strata = stratify(few, per_stratum=10, certainty=1)
        for stratum in strata:
            assert stratum.take == len(stratum.members)
            assert stratum.probability == 1.0


class TestDraw:
    def test_the_same_seed_gives_the_same_sample(self):
        # A sample nobody else can reproduce is a convenience sample with extra
        # steps, which is the mistake this module exists to stop repeating.
        strata = stratify(candidates(60), per_stratum=3)
        first = [s.package for s in draw(strata, seed=7)]
        again = [s.package for s in draw(strata, seed=7)]
        assert first == again

    def test_a_different_seed_gives_a_different_sample(self):
        strata = stratify(candidates(60), per_stratum=3)
        assert [s.package for s in draw(strata, seed=7)] != [
            s.package for s in draw(strata, seed=8)
        ]

    def test_the_weight_is_the_reciprocal_of_the_probability(self):
        # Without it a package-level quantity cannot be weighted back to the
        # frame, and the sample would have to be reported as if it were the
        # population.
        for row in draw(stratify(candidates(60), per_stratum=3)):
            assert row.weight == 1.0 / row.probability

    def test_certainty_packages_carry_weight_one(self):
        drawn = draw(stratify(candidates(60), per_stratum=3, certainty=8))
        certain = [s for s in drawn if s.stratum == "certainty"]
        assert len(certain) == 8
        assert all(s.weight == 1.0 for s in certain)

    def test_every_stratum_contributes(self):
        strata = stratify(candidates(60), per_stratum=3)
        drawn = draw(strata)
        assert {s.stratum for s in drawn} == {s.name for s in strata}


class TestRoundTrip:
    def test_a_written_sample_reads_back_identical(self, tmp_path):
        drawn = draw(stratify(candidates(40), per_stratum=2))
        path = tmp_path / "sample.csv"
        write_sample(drawn, path)
        found = read_sample(path)
        assert len(found) == len(drawn)
        assert {s.package for s in found} == {s.package for s in drawn}
        assert found[0].compiled in (True, False)


def test_the_drawn_sample_covers_the_packages_already_swept():
    """The certainty stratum must contain what has already been measured.

    `sandwich`, `lmtest`, and `plm` were swept before the design existed, chosen
    by which fixtures happened to be written. If the design excluded them their
    results could not enter the estimates, and re-deriving them under the design
    would be pure waste.
    """
    import pytest

    path = ROOT / "data/frame/sample.csv"
    if not path.exists():
        pytest.skip("`kasauti frame sample` has not been run")
    drawn = {s.package: s for s in read_sample(path)}

    for package in ("sandwich", "lmtest", "plm"):
        assert package in drawn, f"{package} was swept but is outside the design"
        assert drawn[package].stratum == "certainty"
