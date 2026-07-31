"""Package selection: CRAN Task Views intersected with corpus usage."""

import json

import pytest

from kasauti.archaeology.taskviews import (
    INFERENTIAL_VIEWS,
    NON_INFERENTIAL,
    VIEW_PACKAGE,
    Selection,
    load_views,
    read_selection,
    select,
    write_selection,
)

MEMBERS = {
    "Econometrics": ["lfe", "plm", "sandwich"],
    "Spatial": ["ggplot2", "sf"],
    "Survival": ["sandwich", "survival"],
}
USAGE = {
    "lfe": 222,
    "plm": 189,
    "sandwich": 421,
    "ggplot2": 1426,
    "sf": 108,
    "survival": 96,
}


class TestSelect:
    def test_ranks_by_corpus_usage(self):
        chosen = [s.package for s in select(MEMBERS, USAGE, minimum=1)]
        assert chosen == ["sandwich", "lfe", "plm", "sf", "survival"]

    def test_records_every_view_listing_a_package(self):
        (sandwich,) = [s for s in select(MEMBERS, USAGE, 1) if s.package == "sandwich"]
        assert sandwich.views == ["Econometrics", "Survival"]

    def test_usage_threshold_excludes_the_long_tail(self):
        chosen = {s.package for s in select(MEMBERS, USAGE, minimum=150)}
        assert chosen == {"sandwich", "lfe", "plm"}

    def test_non_inferential_packages_are_dropped_however_used(self):
        # ggplot2 is the corpus's most-used package and is genuinely part of the
        # Spatial toolkit, so no choice of views excludes it. A bug in it cannot
        # change a coefficient.
        assert "ggplot2" not in {s.package for s in select(MEMBERS, USAGE, 1)}

    def test_a_package_no_corpus_archive_loads_is_not_selected(self):
        assert select({"Econometrics": ["obscura"]}, USAGE, minimum=1) == []


class TestLoadViews:
    def test_cached_membership_is_used_without_fetching(self, tmp_path):
        path = tmp_path / "views.json"
        path.write_text(json.dumps(MEMBERS))
        assert load_views(path) == MEMBERS


class TestSelectionRoundTrip:
    def test_written_selection_reads_back_identical(self, tmp_path):
        original = select(MEMBERS, USAGE, minimum=1)
        path = tmp_path / "packages.csv"
        write_selection(original, path)
        assert read_selection(path) == original

    def test_a_package_in_no_view_round_trips(self, tmp_path):
        path = tmp_path / "packages.csv"
        write_selection([Selection(package="x", views=[], usage=3)], path)
        assert read_selection(path)[0].views == []


class TestViewPackagePattern:
    @pytest.mark.parametrize(
        ("href", "expected"),
        [
            ("../packages/sandwich/index.html", ["sandwich"]),
            ("../packages/data.table/index.html", ["data.table"]),
            ("../views/Econometrics.html", []),
        ],
    )
    def test_matches_package_links_only(self, href, expected):
        assert VIEW_PACKAGE.findall(href) == expected


def test_curation_is_stated_at_the_level_of_categories_not_packages():
    # The whole point of the rewrite: judgment lives in two short, auditable
    # exclusion lists, not in a remembered list of packages to include.
    assert len(INFERENTIAL_VIEWS) < 50
    assert len(NON_INFERENTIAL) < 100
    assert len(set(INFERENTIAL_VIEWS)) == len(INFERENTIAL_VIEWS)
