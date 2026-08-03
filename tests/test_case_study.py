"""A package added because a bug was found in it is not part of the sample.

`fixest` was not drawn. It is swept because a singleton-handling change was hit
on a live analysis, which is selection on the outcome: the probability that a
package enters this way is a function of whether it turned out to have a bug.
Pooling it with the designed sample would bias every weighted estimate upward,
and the bias would be invisible in the output.

So it carries the `case-study` stratum, and the guard is asserted here rather
than remembered.
"""

import csv
from pathlib import Path

import pytest

from kasauti.archaeology.sample import read_sample

ROOT = Path(__file__).resolve().parents[1]

CASE_STUDY = "case-study"
UNDRAWN = {"case-study", "screening"}


def sample():
    path = ROOT / "data/frame/sample.csv"
    if not path.exists():
        pytest.skip("`kasauti frame sample` has not been run")
    return read_sample(path)


def test_an_undrawn_package_carries_no_weight():
    """Zero weight, so an arithmetic slip cannot quietly include one."""
    for row in sample():
        if row.stratum in UNDRAWN:
            assert row.probability == 0.0
            assert row.weight == 0.0


def test_undrawn_packages_get_strata_of_their_own():
    """Never mixed into a designed cell, where a filter would miss them."""
    strata = {r.stratum for r in sample()}
    if not (strata & UNDRAWN):
        pytest.skip("no undrawn package is registered")
    assert strata - UNDRAWN, "the sample is nothing but undrawn packages"


def test_the_analysis_excludes_every_undrawn_stratum():
    """The script must drop them, not merely be able to.

    Read as text because the exclusion has to survive edits to the surrounding
    R, and a test that only checked the output would pass on a run where no
    undrawn package happened to have produced an episode.

    Both strata, not just `case-study`. The `screening` group is the one that
    matters more: `psych`, `estimatr`, and `survival` supply 12 of the 19
    changes in the pooled data, so a guard covering only the obvious case would
    leave the headline resting on packages the design never chose.
    """
    source = (ROOT / "analysis/estimands.R").read_text()
    assert 'c("case-study", "screening")' in source
    assert "changes[!changes$package %in% outside, ]" in source
    assert "episodes[!episodes$package %in% outside, ]" in source


def test_every_swept_package_is_either_drawn_or_a_declared_case_study():
    """Nothing gets swept off the books.

    A package with a timeline and no row in the sample would be neither weighted
    nor excluded -- it would simply be in the estimates, unaccounted for, which
    is the failure this whole stratum exists to prevent.
    """
    sweeps = ROOT / "sweeps"
    if not sweeps.exists():
        pytest.skip("nothing has been swept")
    swept = {p.name for p in sweeps.iterdir() if p.is_dir()}
    known = {r.package for r in sample()}

    unaccounted = swept - known
    assert not unaccounted, (
        f"swept but absent from data/frame/sample.csv: {sorted(unaccounted)}. "
        "Add it to the draw, or register it as case-study or screening."
    )


def test_the_sample_columns_survive_a_hand_edit():
    """A case study is appended by hand, so the header must still be the header."""
    path = ROOT / "data/frame/sample.csv"
    if not path.exists():
        pytest.skip("`kasauti frame sample` has not been run")
    with path.open() as handle:
        header = next(csv.reader(handle))
    assert header == [
        "package",
        "stratum",
        "probability",
        "weight",
        "corpus",
        "compiled",
        "releases",
    ]
