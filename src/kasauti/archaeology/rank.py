"""Rank unverified candidates by how many papers they could actually have moved.

Five records were verified before this module existed, chosen by corpus exposure,
and every one of them linked to **zero** papers. Exposure was the wrong criterion,
and the reason is arithmetic rather than bad luck: a bug can only have corrupted an
archive that was published while the bug was live. A candidate with 200 exposed
scripts and a three-week live window has less paper-level consequence than one with
20 scripts and a decade.

So the ranking here multiplies exposure by the share of the corpus that falls inside
the window, and the interesting part is establishing the window's left edge:

* The changelog sometimes names the version that introduced the defect, which the
  release history turns into a date.
* Failing that, the word **regression** is a strong bound the earlier passes threw
  away. "Fix regression in `st_intersection`" means the defect arrived recently, so
  the window is a release or two, not the package's whole history. Ranked without
  it, `sf` 1.0-1 scored second on the strength of the 48% of the corpus predating
  2021-06-29 -- when the `s2` engine it regressed had shipped three weeks earlier.
* Otherwise the window is left-censored and the estimate is an upper bound, which
  is flagged rather than hidden.

The output is a shortlist ordering, not a prediction. It is worth no more than the
exposure counts feeding it, which are themselves upper bounds until probed.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import date

#: Language marking a defect as recently introduced rather than long-standing.
#: `INERT` and `RESULT_CHANGING` in `link.py` decide whether an entry is a bug;
#: this decides how long it had been one.
REGRESSION = ("regression", "recently introduced", "introduced in", "new bug in")

#: How many releases back a bare "regression" is assumed to reach. Two rather than
#: one because a regression is often noticed a release after it ships.
REGRESSION_RELEASES = 2


@dataclass
class Candidate:
    """One unverified candidate with its estimated paper reach.

    Attributes:
        entry_id: Changelog entry.
        package: Owning package.
        functions: Affected functions.
        scripts: Corpus scripts calling an affected function, an upper bound.
        fixed_on: Release date of the fix.
        window_from: Left edge of the live window, None when censored.
        window_basis: How the left edge was established, for the audit trail.
        archives_in_window: Dated corpus archives published while the bug was live.
        expected: Exposure scaled by the in-window share of the corpus.
    """

    entry_id: str
    package: str
    functions: list[str]
    scripts: int
    fixed_on: date | None
    window_from: date | None
    window_basis: str
    archives_in_window: int
    expected: float

    @property
    def censored(self) -> bool:
        """Whether the window has no known left edge.

        Returns:
            True when the estimate is an upper bound rather than a bracket.
        """
        return self.window_from is None


def window_start(
    text: str,
    fixed_on: date | None,
    releases: list[tuple[str, date | None]],
    introduced_version: str | None = None,
) -> tuple[date | None, str]:
    """Establish when a defect became live.

    Args:
        text: The entry's prose.
        fixed_on: Release date of the fix.
        releases: The package's `(version, released)` history, oldest first.
        introduced_version: Version the changelog blames, if it names one.

    Returns:
        A `(start, basis)` pair. `start` is None when the window is
        left-censored, and `basis` records which rule applied.
    """
    dated = [(v, d) for v, d in releases if d]
    if introduced_version:
        for version, released in dated:
            if version == introduced_version:
                return released, "changelog names the introducing version"

    if fixed_on and any(mark in text.lower() for mark in REGRESSION):
        earlier = [d for _, d in dated if d < fixed_on]
        if len(earlier) >= REGRESSION_RELEASES:
            return earlier[-REGRESSION_RELEASES], "entry calls it a regression"
        if earlier:
            return earlier[0], "entry calls it a regression"

    return None, "left-censored"


def rank(
    candidates: list[tuple[str, str, list[str], int, str, date | None, str | None]],
    releases: dict[str, list[tuple[str, date | None]]],
    archive_dates: list[date],
) -> list[Candidate]:
    """Order candidates by estimated paper reach.

    Args:
        candidates: Tuples of `(entry_id, package, functions, scripts, text,
            fixed_on, introduced_version)`.
        releases: Package name to its `(version, released)` history.
        archive_dates: Publication dates of every dated corpus archive, sorted.

    Returns:
        Candidates sorted by `expected` descending.
    """
    total = len(archive_dates)
    out = []
    for entry_id, package, functions, scripts, text, fixed_on, introduced in candidates:
        start, basis = window_start(
            text, fixed_on, releases.get(package, []), introduced
        )
        if fixed_on is None:
            # Without a fix date nothing can be placed on the timeline. Zero
            # would read as "no papers"; the honest report is "not determinable".
            count = 0
        else:
            upper = bisect.bisect_left(archive_dates, fixed_on)
            lower = bisect.bisect_left(archive_dates, start) if start else 0
            count = max(0, upper - lower)
        out.append(
            Candidate(
                entry_id=entry_id,
                package=package,
                functions=functions,
                scripts=scripts,
                fixed_on=fixed_on,
                window_from=start,
                window_basis=basis,
                archives_in_window=count,
                expected=scripts * count / total if total else 0.0,
            )
        )
    out.sort(key=lambda c: (-c.expected, c.entry_id))
    return out
