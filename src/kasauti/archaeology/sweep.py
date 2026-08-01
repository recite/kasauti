"""Run one probe against every release of a package, and find where numbers moved.

The screening tier tests a claim a maintainer chose to write down. That makes the
changelog entry the sampling unit, and a changelog entry exists only if someone
noticed a bug, fixed it, **and** documented it. Every duration computed from that
frame is conditional on all three, and the conditioning is invisible in the
answer.

A sweep changes the sampling unit to `(package, release, probe)` -- chosen here,
with a known inclusion probability, and a census over releases within a package.
The changelog drops to a **label layer**, which turns "what fraction of
result-changing releases does NEWS document?" from an assumption into a
measurement.

Three things follow that the changelog route cannot give:

* **Undocumented changes become visible.** A release where a number moved and
  NEWS says nothing is exactly what a changelog-first funnel cannot see.
* **Introduction dates come out interval-censored for free.** The bracket between
  the last release holding the old value and the first holding the new one is
  what a survival model wants, and it needs no bisect.
* **A gap is not a data point.** A release that will not build, or builds and will
  not run, breaks the chain. Treating it as "no change" would manufacture
  stability out of a build failure and shorten every lifetime that spans it.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from kasauti.archaeology import library
from kasauti.archaeology.bisect import run_backend
from kasauti.archaeology.screen import DEFAULT_TOL, relative_difference

#: What a release contributed to the timeline.
OBSERVED = "OBSERVED"
GAP = "GAP"


@dataclass
class Observation:
    """One release, run.

    Attributes:
        version: The release.
        released: Its date.
        state: `OBSERVED` or `GAP`.
        detail: Why, for a gap.
        quantities: Numbers the probe returned, empty for a gap.
    """

    version: str
    released: date | None
    state: str
    detail: str = ""
    quantities: dict[str, float] = field(default_factory=dict)


@dataclass
class Change:
    """A point where the probe's answer moved.

    The pair `(after_last_good, at)` is an interval, not a point: the change
    happened somewhere in it, and where exactly is unknown when releases in
    between could not be evaluated. Recording it as an interval is what lets the
    analysis use interval-censored methods instead of pretending to a precision
    the sweep does not have.

    Attributes:
        package: Package swept.
        probe: Probe that produced it.
        at: First release observed to hold the new value.
        at_on: Its release date.
        after: Last release observed to hold the old value.
        after_on: Its release date.
        gaps: Releases between the two that could not be evaluated.
        moved: Quantities that differ.
        max_reldiff: Largest relative difference across them.
    """

    package: str
    probe: str
    at: str
    at_on: date | None
    after: str
    after_on: date | None
    gaps: int
    moved: list[str]
    max_reldiff: float

    @property
    def exact(self) -> bool:
        """Whether the change is pinned to one release.

        Returns:
            True when no unevaluable release sits inside the interval.
        """
        return self.gaps == 0

    @property
    def shape_only(self) -> bool:
        """Whether nothing shared moved and the returned object changed shape.

        `max_reldiff` is 0 for these, which reads as "nothing happened" and is
        the opposite of the truth: `estimatr` 0.6.0 began returning a standard
        error where 0.4.0 returned nothing at all. Flagged so a reader is never
        asked to infer a real change from a zero.

        Returns:
            True when every moved entry is an appearance or a disappearance.
        """
        return bool(self.moved) and all(
            name.startswith(("+", "-")) for name in self.moved
        )


@dataclass
class Timeline:
    """Everything one probe saw across one package's history.

    Attributes:
        package: Package swept.
        probe: Probe run.
        observations: Every release, in release order.
        changes: Points where the answer moved.
    """

    package: str
    probe: str
    observations: list[Observation] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)

    @property
    def observed(self) -> int:
        """How many releases produced numbers.

        Returns:
            The count of `OBSERVED` observations.
        """
        return sum(1 for o in self.observations if o.state == OBSERVED)

    @property
    def gaps(self) -> int:
        """How many releases could not be evaluated.

        Returns:
            The count of `GAP` observations.
        """
        return sum(1 for o in self.observations if o.state == GAP)

    def write(self, directory: Path) -> Path:
        """Write the timeline to JSON.

        Args:
            directory: Where sweeps for this package live.

        Returns:
            The path written.
        """
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{Path(self.probe).stem}.json"
        path.write_text(
            json.dumps(
                {
                    "package": self.package,
                    "probe": self.probe,
                    "observed": self.observed,
                    "gaps": self.gaps,
                    "observations": [
                        {
                            "version": o.version,
                            "released": o.released.isoformat() if o.released else None,
                            "state": o.state,
                            "detail": o.detail,
                            "quantities": o.quantities,
                        }
                        for o in self.observations
                    ],
                    "changes": [
                        {
                            "at": c.at,
                            "at_on": c.at_on.isoformat() if c.at_on else None,
                            "after": c.after,
                            "after_on": c.after_on.isoformat() if c.after_on else None,
                            "gaps": c.gaps,
                            "exact": c.exact,
                            "shape_only": c.shape_only,
                            "moved": c.moved,
                            "max_reldiff": c.max_reldiff,
                        }
                        for c in self.changes
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return path


def differences(
    old: dict[str, float], new: dict[str, float], tol: float
) -> tuple[list[str], float]:
    """Which quantities moved between two runs, and by how much.

    Args:
        old: Quantities from the earlier release.
        new: Quantities from the later one.
        tol: Relative difference above which a quantity counts as moved.

    Returns:
        A `(moved, max_reldiff)` pair. A quantity present in one run and not the
        other is reported as moved, prefixed `-` or `+`: what a function returns
        changing shape is a changed result by any reading a user would recognise.
    """
    shared = sorted(set(old) & set(new))
    moved = [k for k in shared if relative_difference(old[k], new[k]) >= tol]
    largest = max(
        (relative_difference(old[k], new[k]) for k in shared),
        default=0.0,
    )
    moved += [f"-{k}" for k in sorted(set(old) - set(new))]
    moved += [f"+{k}" for k in sorted(set(new) - set(old))]
    return moved, largest


def find_changes(
    package: str, probe: str, observations: list[Observation], tol: float
) -> list[Change]:
    """Locate every point where the probe's answer moved.

    Compares each observed release against the **last observed** release rather
    than the immediately preceding one, so a run of unevaluable versions widens
    the interval instead of splitting the timeline or being silently skipped.

    Args:
        package: Package swept.
        probe: Probe run.
        observations: Every release, in release order.
        tol: Relative difference above which a quantity counts as moved.

    Returns:
        The changes, in release order.
    """
    changes: list[Change] = []
    previous: Observation | None = None
    gaps = 0

    for observation in observations:
        if observation.state != OBSERVED:
            gaps += 1
            continue
        if previous is not None:
            moved, largest = differences(
                previous.quantities, observation.quantities, tol
            )
            if moved:
                changes.append(
                    Change(
                        package=package,
                        probe=probe,
                        at=observation.version,
                        at_on=observation.released,
                        after=previous.version,
                        after_on=previous.released,
                        gaps=gaps,
                        moved=moved,
                        max_reldiff=largest,
                    )
                )
        previous, gaps = observation, 0

    return changes


def sweep(
    package: str,
    probe: str,
    fixtures: Path,
    releases: list[tuple[str, date | None]],
    ledger: library.Ledger,
    tol: float = DEFAULT_TOL,
    timeout: int = 600,
    on_release=None,
) -> Timeline:
    """Run one probe against every release of a package.

    Args:
        package: Package to sweep.
        probe: Probe script, relative to the fixture directory.
        fixtures: The package's fixture directory.
        releases: `(version, released)` pairs, oldest first.
        ledger: Build ledger.
        tol: Relative difference above which a quantity counts as moved.
        timeout: Seconds allowed per run.
        on_release: Optional callback invoked with each `Observation`.

    Returns:
        The timeline.
    """
    timeline = Timeline(package=package, probe=probe)
    cmd = ["Rscript", "--vanilla", probe, f"${{{library.ROOT_VARIABLE}}}"]

    for version, released in releases:
        lib, detail = library.ensure(package, version, ledger, timeout=timeout)
        if lib is None:
            observation = Observation(version, released, GAP, f"build: {detail[:160]}")
        else:
            result = run_backend(
                fixtures, cmd, lib, timeout=timeout, data=fixtures / "data.csv"
            )
            observation = _observe(version, released, result)
        timeline.observations.append(observation)
        if on_release:
            on_release(observation)

    timeline.changes = find_changes(package, probe, timeline.observations, tol)
    return timeline


def _observe(version: str, released: date | None, result: dict | None) -> Observation:
    """Turn one backend run into an observation.

    A version that installs and then refuses to run is as much a gap as one that
    would not compile -- `psych` 1.5.8 does exactly that, its own code tripping a
    check R tightened in 4.2 -- and the reason travels either way.

    Args:
        version: The release.
        released: Its date.
        result: The run's result JSON, or None.

    Returns:
        The observation.
    """
    if result is None:
        return Observation(version, released, GAP, "produced no result")
    if result.get("status") != "ok":
        message = (result.get("error") or "").strip()[:160]
        return Observation(version, released, GAP, f"run: {message}")

    quantities = {
        k: float(v)
        for k, v in (result.get("quantities") or {}).items()
        if v is not None
    }
    if not quantities:
        return Observation(version, released, GAP, "returned no comparable quantity")
    return Observation(version, released, OBSERVED, "", quantities)


CHANGE_COLUMNS = [
    "package",
    "probe",
    "at",
    "at_on",
    "after",
    "after_on",
    "gaps",
    "exact",
    "shape_only",
    "n_moved",
    "max_reldiff",
    "moved",
]


def write_changes(changes: list[Change], path: Path) -> None:
    """Write the tidy change table.

    Args:
        changes: Changes across every swept package and probe.
        path: Destination CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHANGE_COLUMNS)
        writer.writeheader()
        for change in sorted(
            changes, key=lambda c: (c.package, c.probe, c.at_on or date.min)
        ):
            writer.writerow(
                {
                    "package": change.package,
                    "probe": change.probe,
                    "at": change.at,
                    "at_on": change.at_on or "",
                    "after": change.after,
                    "after_on": change.after_on or "",
                    "gaps": change.gaps,
                    "exact": int(change.exact),
                    "shape_only": int(change.shape_only),
                    "n_moved": len(change.moved),
                    "max_reldiff": f"{change.max_reldiff:.12g}",
                    "moved": ";".join(change.moved),
                }
            )
