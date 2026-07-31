"""Ordering unverified candidates by estimated paper reach."""

from datetime import date

from kasauti.archaeology.rank import rank, window_start

RELEASES = [
    ("1.0", date(2015, 1, 1)),
    ("1.1", date(2018, 1, 1)),
    ("1.2", date(2020, 1, 1)),
    ("1.3", date(2021, 1, 1)),
    ("1.4", date(2022, 1, 1)),
]

ARCHIVES = [date(y, 6, 1) for y in range(2010, 2025)]


class TestWindowStart:
    def test_a_named_introducing_version_dates_the_window(self):
        start, basis = window_start("", date(2022, 1, 1), RELEASES, "1.2")
        assert start == date(2020, 1, 1)
        assert "names the introducing version" in basis

    def test_regression_bounds_the_window_to_recent_releases(self):
        # "Fix regression in st_intersection" means the defect arrived recently.
        # Without this, sf 1.0-1 ranked second on the strength of the 48% of the
        # corpus predating its fix -- when the engine it regressed had shipped
        # three weeks earlier.
        start, basis = window_start("fix regression in foo", date(2022, 1, 1), RELEASES)
        assert start == date(2020, 1, 1)  # two releases back
        assert "regression" in basis

    def test_an_ordinary_entry_is_left_censored(self):
        start, basis = window_start("fixed a bug in foo", date(2022, 1, 1), RELEASES)
        assert start is None
        assert basis == "left-censored"

    def test_a_named_version_beats_the_regression_heuristic(self):
        start, _ = window_start("fix regression", date(2022, 1, 1), RELEASES, "1.0")
        assert start == date(2015, 1, 1)

    def test_a_regression_in_the_first_release_falls_back_to_it(self):
        start, _ = window_start("regression", date(2018, 6, 1), RELEASES)
        assert start == date(2015, 1, 1)


class TestRank:
    def test_a_long_window_can_beat_three_times_the_exposure(self):
        # The whole point: exposure alone chose five bugs that linked to zero
        # papers. Here the wide candidate has 3x the scripts, but its regression
        # window covers 2 archives of 15 against the other's 12, so it reaches
        # 60*2/15 = 8 against 20*12/15 = 16. Exposure is not reach.
        wide = ("a", "p", ["f"], 60, "fix regression in f", date(2022, 1, 1), None)
        long = ("b", "p", ["g"], 20, "fixed a bug in g", date(2022, 1, 1), None)
        ordered = rank([wide, long], {"p": RELEASES}, ARCHIVES)
        assert [c.entry_id for c in ordered] == ["b", "a"]
        assert [round(c.expected, 3) for c in ordered] == [16.0, 8.0]

    def test_censoring_is_reported_not_hidden(self):
        (censored,) = rank(
            [("a", "p", [], 10, "fixed a bug", date(2022, 1, 1), None)],
            {"p": RELEASES},
            ARCHIVES,
        )
        assert censored.censored
        (bounded,) = rank(
            [("a", "p", [], 10, "fixed a bug", date(2022, 1, 1), "1.2")],
            {"p": RELEASES},
            ARCHIVES,
        )
        assert not bounded.censored

    def test_an_undated_fix_reaches_nothing_rather_than_everything(self):
        # Nothing can be placed on a timeline without a fix date. Counting the
        # whole corpus would be the opposite of conservative.
        (only,) = rank(
            [("a", "p", [], 500, "fixed a bug", None, None)], {"p": RELEASES}, ARCHIVES
        )
        assert only.archives_in_window == 0
        assert only.expected == 0.0

    def test_reach_scales_exposure_by_the_in_window_share(self):
        (only,) = rank(
            [("a", "p", [], 100, "fixed a bug", date(2022, 1, 1), "1.3")],
            {"p": RELEASES},
            ARCHIVES,
        )
        # 2021-01-01 to 2022-01-01 covers one archive of fifteen.
        assert only.archives_in_window == 1
        assert only.expected == 100 / 15
