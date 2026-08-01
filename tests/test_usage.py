"""Usage measured without reference to any one field."""

import json

import pytest

from kasauti.archaeology import usage
from kasauti.archaeology.usage import Usage, load_usage, read_usage, write_usage


class TestReverseDependencyCounts:
    def test_strong_dependencies_are_counted_apart_from_suggestions(self, monkeypatch):
        # A suggestion is a much weaker claim about whether code ever runs, so
        # folding it into one total would overstate how much a package is relied
        # on -- exactly the confusion the measure exists to avoid.
        lines = "\n".join(
            [
                "Imports sandwich",
                "Depends sandwich",
                "LinkingTo Rcpp",
                "Suggests sandwich",
            ]
        )

        class Result:
            stdout = lines
            stderr = ""

        monkeypatch.setattr(usage.subprocess, "run", lambda *a, **k: Result())
        counts = usage.fetch_reverse_dependencies()
        assert counts["sandwich"] == {"strong": 2, "suggests": 1}
        assert counts["Rcpp"] == {"strong": 1, "suggests": 0}

    def test_an_empty_database_is_an_error_not_an_empty_frame(self, monkeypatch):
        # Silently returning zero counts would put every package in the smallest
        # usage stratum and look like a finding about the ecosystem.
        class Result:
            stdout = ""
            stderr = "could not reach CRAN"

        monkeypatch.setattr(usage.subprocess, "run", lambda *a, **k: Result())
        with pytest.raises(RuntimeError, match="produced nothing"):
            usage.fetch_reverse_dependencies()


class TestCache:
    def test_measurements_are_fetched_once_and_reused(self, tmp_path, monkeypatch):
        # A frame that shifts because CRAN gained a package last Tuesday is not a
        # frame. Every count has to be reproducible from the repository.
        cache = tmp_path / "usage.json"
        cache.write_text(
            json.dumps(
                {
                    "window": "2024-01-01:2024-12-31",
                    "reverse": {"sandwich": {"strong": 191, "suggests": 40}},
                    "downloads": {"sandwich": 2223521},
                }
            )
        )
        monkeypatch.setattr(
            usage, "fetch_reverse_dependencies", lambda: pytest.fail("no network")
        )
        monkeypatch.setattr(
            usage, "fetch_downloads", lambda *a, **k: pytest.fail("no network")
        )

        found = load_usage(["sandwich"], "2024-01-01:2024-12-31", cache)
        assert found["sandwich"].strong == 191
        assert found["sandwich"].downloads == 2223521

    def test_a_package_the_service_never_heard_of_is_zero_not_missing(
        self, tmp_path, monkeypatch
    ):
        cache = tmp_path / "usage.json"
        cache.write_text(json.dumps({"window": "w", "reverse": {}, "downloads": {}}))
        monkeypatch.setattr(usage, "fetch_downloads", lambda *a, **k: {})

        found = load_usage(["nosuchpkg"], "w", cache)
        assert found["nosuchpkg"].downloads == 0
        assert found["nosuchpkg"].strong == 0


class TestRoundTrip:
    def test_a_written_table_reads_back_identical(self, tmp_path):
        rows = [
            Usage("lfe", corpus=222, strong=4, suggests=1, downloads=135470),
            Usage("MASS", corpus=459, strong=2139, suggests=800, downloads=2668008),
        ]
        path = tmp_path / "cran_usage.csv"
        write_usage(rows, path)
        found = read_usage(path)
        assert found["lfe"] == rows[0]
        assert found["MASS"] == rows[1]

    def test_the_table_is_ordered_by_corpus_usage(self, tmp_path):
        path = tmp_path / "cran_usage.csv"
        write_usage(
            [Usage("a", corpus=1), Usage("b", corpus=9)],
            path,
        )
        assert list(read_usage(path)) == ["b", "a"]


def test_the_field_measure_and_the_ecosystem_measure_disagree():
    """The reason this module exists, asserted rather than asserted about.

    `lfe` is the seventh most used package in the social-science corpus and has
    four reverse dependencies on all of CRAN. A frame built on ecosystem
    centrality alone would never see it -- which is the same package the README
    records as having been forgotten when the frame was built from memory.
    """
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "data/frame/cran_usage.csv"
    if not path.exists():
        pytest.skip("`kasauti frame usage` has not been run")
    table = read_usage(path)

    lfe = table["lfe"]
    assert lfe.corpus > 200
    assert lfe.strong < 20, (
        "lfe has gained reverse dependencies; the illustration still holds only "
        "if it remains ecosystem-peripheral and corpus-central"
    )
