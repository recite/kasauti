"""Durations, and what each one is conditional on."""

from dataclasses import dataclass
from datetime import date

from kasauti.archaeology.episodes import (
    BORN,
    CLOSED,
    LEFT_CENSORED,
    OBSERVED_START,
    RIGHT_CENSORED,
    build,
    documents,
    news_between,
)
from kasauti.archaeology.sweep import Change, Observation


@dataclass
class Entry:
    """The two fields the NEWS join reads off a parsed changelog entry."""

    version: str
    text: str


def seen(version: str, year: int, **quantities) -> Observation:
    return Observation(version, date(year, 1, 1), "OBSERVED", "", dict(quantities))


def missed(version: str, year: int, why: str = "build failed") -> Observation:
    return Observation(version, date(year, 1, 1), "GAP", why)


def absent(version: str, year: int) -> Observation:
    """A gap because the code did not exist yet, not because it would not build."""
    return Observation(
        version,
        date(year, 1, 1),
        "GAP",
        "run: no applicable method for 'vcovHC' applied to an object of class ...",
    )


def change(at: str, at_year: int, after: str, after_year: int, gaps: int = 0) -> Change:
    return Change(
        package="p",
        probe="probe.R",
        at=at,
        at_on=date(at_year, 1, 1),
        after=after,
        after_on=date(after_year, 1, 1),
        gaps=gaps,
        moved=["se"],
        max_reldiff=1.0,
    )


class TestCensoring:
    def test_the_first_episode_is_left_censored_at_the_buildability_floor(self):
        # The value was already in force when the sweep could first look, so its
        # length is a lower bound. `survival` reaches only 2022, so this is not a
        # rare corner -- it is where the package with the most candidates lives.
        history = [seen("1.0", 2010, se=1.0), seen("1.1", 2011, se=2.0)]
        first, _ = build([change("1.1", 2011, "1.0", 2010)], history, "p", "probe.R")
        assert first.start == LEFT_CENSORED
        assert first.opened == "1.0"

    def test_the_last_episode_is_right_censored(self):
        # Dropping these would condition on eventual change and shorten every
        # estimate: a value still holding may be right and permanent, or wrong
        # and undiscovered, and nothing here can tell.
        history = [seen("1.0", 2010, se=1.0), seen("1.1", 2011, se=2.0)]
        _, last = build([change("1.1", 2011, "1.0", 2010)], history, "p", "probe.R")
        assert last.end == RIGHT_CENSORED
        assert last.upper_days is None
        assert last.lower_days == 0

    def test_a_middle_episode_is_closed_at_both_ends(self):
        history = [
            seen("1.0", 2010, se=1.0),
            seen("1.1", 2011, se=2.0),
            seen("1.2", 2014, se=3.0),
        ]
        changes = [change("1.1", 2011, "1.0", 2010), change("1.2", 2014, "1.1", 2011)]
        _, middle, _ = build(changes, history, "p", "probe.R")
        assert (middle.start, middle.end) == (OBSERVED_START, CLOSED)
        assert middle.exact

    def test_a_stable_history_is_one_censored_episode(self):
        history = [seen("1.0", 2010, se=1.0), seen("1.1", 2011, se=1.0)]
        (only,) = build([], history, "p", "probe.R")
        assert only.start == LEFT_CENSORED
        assert only.end == RIGHT_CENSORED

    def test_a_first_episode_preceded_only_by_absent_code_is_born_not_censored(self):
        # The third time this distinction has paid: a bug in a method nobody has
        # written is not a bug. Calling it censored throws away a measured start
        # date and inflates the censoring rate the analysis has to apologise for.
        history = [
            absent("2.2-3", 2009),
            seen("2.2-4", 2010, se=1.0),
            seen("2.5-0", 2018, se=2.0),
        ]
        first, _ = build(
            [change("2.5-0", 2018, "2.2-4", 2010)], history, "sandwich", "probe.R"
        )
        assert first.start == BORN

    def test_a_build_failure_before_the_first_episode_still_censors_it(self):
        # A version that would not compile may well have held the value unseen,
        # so its start really is unknown. Only "the code was not there" is a date.
        history = [
            missed("1.0", 2009),
            seen("1.1", 2010, se=1.0),
            seen("1.2", 2012, se=2.0),
        ]
        first, _ = build([change("1.2", 2012, "1.1", 2010)], history, "p", "probe.R")
        assert first.start == LEFT_CENSORED

    def test_one_unexplained_gap_among_absent_ones_is_enough_to_censor(self):
        history = [
            absent("1.0", 2008),
            missed("1.1", 2009),
            seen("1.2", 2010, se=1.0),
            seen("1.3", 2012, se=2.0),
        ]
        first, _ = build([change("1.3", 2012, "1.2", 2010)], history, "p", "probe.R")
        assert first.start == LEFT_CENSORED

    def test_a_timeline_with_nothing_evaluable_yields_no_episodes(self):
        assert build([], [missed("1.0", 2010)], "p", "probe.R") == []


class TestDuration:
    def test_the_lower_bound_runs_to_the_last_release_known_to_hold_the_value(self):
        history = [
            seen("1.0", 2010, se=1.0),
            seen("1.1", 2011, se=2.0),
            seen("1.2", 2014, se=3.0),
        ]
        changes = [change("1.1", 2011, "1.0", 2010), change("1.2", 2014, "1.1", 2011)]
        _, middle, _ = build(changes, history, "p", "probe.R")
        assert middle.lower_days == (date(2011, 1, 1) - date(2011, 1, 1)).days

    def test_the_upper_bound_starts_from_the_last_release_holding_the_old_value(self):
        history = [
            seen("1.0", 2010, se=1.0),
            seen("1.1", 2011, se=2.0),
            seen("1.2", 2014, se=3.0),
        ]
        changes = [change("1.1", 2011, "1.0", 2010), change("1.2", 2014, "1.1", 2011)]
        _, middle, _ = build(changes, history, "p", "probe.R")
        assert middle.upper_days == (date(2014, 1, 1) - date(2010, 1, 1)).days

    def test_a_gap_inside_the_interval_makes_the_duration_inexact(self):
        history = [
            seen("1.0", 2010, se=1.0),
            missed("1.1", 2011),
            seen("1.2", 2012, se=2.0),
            seen("1.3", 2014, se=3.0),
        ]
        changes = [
            change("1.2", 2012, "1.0", 2010, gaps=1),
            change("1.3", 2014, "1.2", 2012),
        ]
        _, middle, _ = build(changes, history, "p", "probe.R")
        assert middle.upper_days > middle.lower_days


class TestDocumented:
    def test_a_named_function_counts(self):
        assert documents("Fix of a bug in vcovHC() reported by ...", ["vcovHC"])

    def test_a_different_function_does_not(self):
        # The flag is the outcome the whole sweep exists to measure, so a loose
        # join would inflate exactly the quantity under study.
        assert not documents("Fix of a bug in vcovCL().", ["vcovHC"])

    def test_an_r_method_of_the_function_counts(self):
        # R dispatches by suffix. `vcovHC.mlm()` in NEWS documents a change to
        # `vcovHC`, and that is the clearest documented bug in this whole corpus
        # -- a boundary rejecting a trailing dot would score it as undocumented.
        assert documents("bug in vcovHC.mlm() reported by ...", ["vcovHC"])
        assert documents("estfun.survreg was wrong under weights", ["estfun"])

    def test_a_name_inside_a_longer_identifier_does_not(self):
        assert not documents("myestfun changed", ["estfun"])
        assert not documents("estfuns were rewritten", ["estfun"])

    def test_a_method_of_some_other_function_does_not(self):
        assert not documents("summary.estfun changed", ["summary.lm"])

    def test_no_changelog_text_is_not_documentation(self):
        assert not documents("", ["vcovHC"])


class TestNewsBetween:
    ENTRIES = [
        Entry("2.34-1", "unrelated tidying"),
        Entry("2.35", "fixed frailty in survfit"),
        Entry("2.36-1", "later work"),
    ]

    def test_a_changelog_version_cran_never_shipped_still_counts(self):
        # `survival`'s NEWS is organised under headings like 2.35 that are not
        # releases. An exact-version join would score those as undocumented when
        # the maintainer did describe them.
        text = news_between(self.ENTRIES, "2.34-1", "2.35-2")
        assert "frailty" in text

    def test_entries_outside_the_interval_are_excluded(self):
        text = news_between(self.ENTRIES, "2.34-1", "2.35-2")
        assert "later work" not in text
        assert "unrelated tidying" not in text

    def test_an_open_lower_bound_takes_everything_up_to_the_change(self):
        text = news_between(self.ENTRIES, None, "2.35-2")
        assert "unrelated tidying" in text
        assert "later work" not in text


def test_the_documented_flag_reaches_the_episode():
    history = [seen("2.4-0", 2017, se=1.0), seen("2.5-0", 2018, se=2.0)]
    entries = [Entry("2.5-0", "Fix of a bug in vcovHC.mlm().")]
    first, _ = build(
        [change("2.5-0", 2018, "2.4-0", 2017)],
        history,
        "sandwich",
        "vcovhc_mlm.R",
        entries=entries,
        functions=["vcovHC"],
    )
    assert first.closed_documented
