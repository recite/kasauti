"""Turn change points into durations, and say what each duration is conditional on.

A sweep says *where* a package's answer moved. An **episode** is the span between
two consecutive change points: the stretch over which one value held. That is the
unit a duration model wants, and it carries its own censoring rather than needing
it reconstructed later.

Three kinds of episode, and conflating them is the easiest way to get a wrong
number:

* **Closed.** Opened by a change and closed by a later one. Its length is
  observed, up to the width of the two intervals bounding it.
* **Right-censored.** Still holding at the last release swept. The value may be
  correct and permanent, or wrong and undiscovered; nothing here can tell, and a
  model that drops these would condition on eventual change and shorten every
  estimate.
* **Left-censored.** Already in force at the oldest release that could be
  evaluated. Its start is before the buildability floor, so its length is a lower
  bound. `sandwich` reaches 2009 and `survival` only 2022, so this is not a rare
  corner -- it is where the package with the most candidates lives.
* **Born.** The releases before it did not fail to build; they failed because the
  code did not exist. That is not censoring, it is a start date. The distinction
  is the same one `ABSENT` taught the bisect -- a bug in a method nobody has
  written is not a bug -- and treating a birth as censored throws away a measured
  date and inflates the censoring rate the analysis has to apologise for.

The **documented** flag is the other half. A change point in a release whose NEWS
names an affected function is documented; one in a release whose NEWS says
something else, or says nothing, is not. That flag is the outcome the sweep exists
to make measurable, so it is computed here and never inferred downstream.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

#: How an episode ends.
CLOSED = "CLOSED"
RIGHT_CENSORED = "RIGHT_CENSORED"

#: How an episode begins.
OBSERVED_START = "OBSERVED"
LEFT_CENSORED = "LEFT_CENSORED"
BORN = "BORN"


@dataclass
class Episode:
    """One stretch over which a probe's answer held constant.

    Attributes:
        package: Package swept.
        probe: Probe that produced it.
        opened: Release at which the value first held.
        opened_on: Its release date.
        opened_after: Last release known to hold the previous value, or None when
            the episode was already in force at the floor.
        opened_after_on: Its release date.
        closed: Release at which the value stopped holding, or None.
        closed_on: Its release date.
        closed_after: Last release known to hold this value.
        closed_after_on: Its release date.
        start: `OBSERVED` or `LEFT_CENSORED`.
        end: `CLOSED` or `RIGHT_CENSORED`.
        releases: Evaluable releases spanned.
        opened_documented: Whether NEWS at the opening release names an affected
            function.
        closed_documented: Same, at the closing release.
    """

    package: str
    probe: str
    opened: str
    opened_on: date | None
    opened_after: str | None
    opened_after_on: date | None
    closed: str | None
    closed_on: date | None
    closed_after: str | None
    closed_after_on: date | None
    start: str
    end: str
    releases: int
    opened_documented: bool = False
    closed_documented: bool = False

    @property
    def lower_days(self) -> int | None:
        """Shortest duration consistent with the observations.

        The value certainly held from the opening release until the last release
        known to hold it, so that span is a floor whatever sits in the bounding
        intervals.

        Returns:
            Days, or None when either endpoint is undated.
        """
        end = self.closed_after_on or self.closed_on
        if self.opened_on is None or end is None:
            return None
        return (end - self.opened_on).days

    @property
    def upper_days(self) -> int | None:
        """Longest duration consistent with the observations.

        The change opening the episode happened somewhere after the last release
        holding the previous value, and the change closing it somewhere before
        the first release not holding this one. The widest span between those is
        the ceiling.

        Returns:
            Days, or None for a right-censored episode, whose length has no
            upper bound to report.
        """
        if self.end != CLOSED or self.closed_on is None:
            return None
        start = self.opened_after_on or self.opened_on
        if start is None:
            return None
        return (self.closed_on - start).days

    @property
    def exact(self) -> bool:
        """Whether the duration is pinned rather than bracketed.

        Returns:
            True when both bounding intervals are one release wide, so the lower
            and upper bounds describe the same transition.
        """
        return self.start == OBSERVED_START and self.end == CLOSED


def documents(news: str, functions: list[str]) -> bool:
    """Whether changelog text names any of these functions.

    Deliberately literal. A looser join -- "the release mentions a bug" -- would
    credit a maintainer for documenting a change they never described, which
    inflates exactly the quantity the sweep exists to measure.

    Args:
        news: Changelog text.
        functions: Function names the probe exercises.

    Returns:
        True if any function is named as a word in the text.
    """
    if not news:
        return False
    # A trailing dot is allowed and a leading one is not, because R dispatches
    # by suffix: `vcovHC.mlm()` in NEWS documents a change to `vcovHC`, which is
    # exactly the sandwich entry this study started from. Rejecting it would
    # score the clearest documented bug in the corpus as undocumented. A leading
    # dot is a different function, so `foo.estfun` is not `estfun`.
    return any(
        re.search(rf"(?<![\w.]){re.escape(name)}(?!\w)", news) for name in functions
    )


def born(observations: list) -> bool:
    """Whether the first evaluable release is the first release that could exist.

    The releases before it either could not be built -- so the value may well
    have been there and unseen -- or errored because the code was not written
    yet, in which case the episode has a real start date rather than a censored
    one. The bisect learned the same distinction as `ABSENT`: a bug in a method
    nobody has written is not a bug, and it bounds the search where a build
    failure only widens it.

    Args:
        observations: Every release run, in release order.

    Returns:
        True when every gap before the first observed release says the code was
        missing, and there is at least one such gap to say it.
    """
    from kasauti.archaeology.bisect import NOT_YET_IMPLEMENTED
    from kasauti.archaeology.sweep import OBSERVED

    preceding = []
    for observation in observations:
        if observation.state == OBSERVED:
            break
        preceding.append(observation)

    if not preceding:
        return False
    return all(
        any(marker in o.detail.lower() for marker in NOT_YET_IMPLEMENTED)
        for o in preceding
    )


def news_between(entries: list, after: str | None, at: str) -> str:
    """Changelog text belonging to the interval a change was located in.

    Not a lookup by release version, because a changelog's headings are often not
    releases -- `survival`'s NEWS is organised under versions like `2.35` that
    CRAN never shipped, and six of the nine fix versions on its shortlist have no
    tarball at all. Matching on exact version would score those as undocumented
    when the maintainer did in fact describe them.

    So every changelog version strictly above the last release holding the old
    value and at or below the first release holding the new one contributes.

    Args:
        entries: Parsed changelog entries, each with `version` and `text`.
        after: Last release known to hold the previous value, or None.
        at: First release observed to hold the new value.

    Returns:
        The concatenated text, empty when the interval holds no entries.
    """
    from kasauti.archaeology.screen import version_key

    high = version_key(at)
    low = version_key(after) if after else ()
    return "\n".join(
        entry.text for entry in entries if low < version_key(entry.version) <= high
    )


def build(
    changes: list,
    observations: list,
    package: str,
    probe: str,
    entries: list | None = None,
    functions: list[str] | None = None,
) -> list[Episode]:
    """Split one timeline into episodes.

    Args:
        changes: The timeline's change points, in release order.
        observations: Every release run, in release order.
        package: Package swept.
        probe: Probe run.
        entries: Parsed changelog entries, for the documented flag.
        functions: Functions the probe exercises, for the documented flag.

    Returns:
        The episodes, oldest first. An empty list when nothing was evaluable.
    """
    from kasauti.archaeology.sweep import OBSERVED

    evaluable = [o for o in observations if o.state == OBSERVED]
    if not evaluable:
        return []
    opening = BORN if born(observations) else LEFT_CENSORED

    entries = entries or []
    functions = functions or []
    versions = [o.version for o in evaluable]

    def documented(after: str | None, at: str | None) -> bool:
        if at is None or not functions:
            return False
        return documents(news_between(entries, after, at), functions)

    def spanned(start: str, end: str | None) -> int:
        first = versions.index(start)
        last = versions.index(end) if end in versions else len(versions)
        return max(last - first, 1)

    # The oldest evaluable release opens the first episode, and its start is
    # censored: the value was already in force when the sweep could first look,
    # so there is no change point to date it by and no NEWS interval to join.
    boundaries: list[tuple[str, date | None, str | None, date | None, bool]] = [
        (evaluable[0].version, evaluable[0].released, None, None, False)
    ]
    boundaries += [(c.at, c.at_on, c.after, c.after_on, True) for c in changes]

    episodes: list[Episode] = []
    for index, (opened, opened_on, after, after_on, observed) in enumerate(boundaries):
        following = boundaries[index + 1] if index + 1 < len(boundaries) else None
        closed, closed_on = (following[0], following[1]) if following else (None, None)
        closed_after, closed_after_on = (
            (following[2], following[3])
            if following
            else (evaluable[-1].version, evaluable[-1].released)
        )
        episodes.append(
            Episode(
                package=package,
                probe=probe,
                opened=opened,
                opened_on=opened_on,
                opened_after=after,
                opened_after_on=after_on,
                closed=closed,
                closed_on=closed_on,
                closed_after=closed_after,
                closed_after_on=closed_after_on,
                start=OBSERVED_START if observed else opening,
                end=CLOSED if following else RIGHT_CENSORED,
                releases=spanned(opened, closed),
                opened_documented=documented(after, opened) if observed else False,
                closed_documented=documented(closed_after, closed),
            )
        )
    return episodes


EPISODE_COLUMNS = [
    "package",
    "probe",
    "opened",
    "opened_on",
    "opened_after",
    "opened_after_on",
    "closed",
    "closed_on",
    "closed_after",
    "closed_after_on",
    "start",
    "end",
    "exact",
    "releases",
    "lower_days",
    "upper_days",
    "opened_documented",
    "closed_documented",
]


def write_episodes(episodes: list[Episode], path: Path) -> None:
    """Write the tidy episode table.

    Args:
        episodes: Episodes across every swept package and probe.
        path: Destination CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EPISODE_COLUMNS)
        writer.writeheader()
        for episode in sorted(
            episodes, key=lambda e: (e.package, e.probe, e.opened_on or date.min)
        ):
            writer.writerow(
                {
                    "package": episode.package,
                    "probe": episode.probe,
                    "opened": episode.opened,
                    "opened_on": episode.opened_on or "",
                    "opened_after": episode.opened_after or "",
                    "opened_after_on": episode.opened_after_on or "",
                    "closed": episode.closed or "",
                    "closed_on": episode.closed_on or "",
                    "closed_after": episode.closed_after or "",
                    "closed_after_on": episode.closed_after_on or "",
                    "start": episode.start,
                    "end": episode.end,
                    "exact": int(episode.exact),
                    "releases": episode.releases,
                    "lower_days": (
                        "" if episode.lower_days is None else episode.lower_days
                    ),
                    "upper_days": (
                        "" if episode.upper_days is None else episode.upper_days
                    ),
                    "opened_documented": int(episode.opened_documented),
                    "closed_documented": int(episode.closed_documented),
                }
            )
