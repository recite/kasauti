"""Choose which functions to probe, from what the corpus calls rather than from memory.

A sweep can only see a change in code it exercises, so the probe battery is the
coverage statement of the whole design. Picking those functions by hand would put
back exactly the judgment the package frame was rebuilt to remove -- and the cost
of that mistake is already measured: a frame named from memory omitted `lfe`,
which turned out to hold the most-exposed candidate in the study.

So a package's battery is its **most-called exported functions in the corpus**,
read off `sampling_frame.csv`. That inherits the discipline `taskviews.py` argues
for one level up: cast wide, filter narrow, and let an external source decide what
is in.

Three filters, all of them already load-bearing elsewhere in this project and all
of them the same lesson:

* **Base R's names are base R's.** `Matrix` exports `length`, `names`, `rep`, and
  `is.na`; the frame credits it with 3,268 scripts calling `length`. Unfiltered,
  `Matrix`'s battery would be four base-R primitives and nothing else.
* **Non-computing names are not procedures.** Extraction and formatting cannot
  change an estimate, so probing them measures nothing.
* **A contested name is apportioned, not credited whole and not thrown away.**
  `vcovHC` is exported by both `sandwich` and `plm`, and the frame credits its 76
  scripts to each; left alone, `plm`'s battery led with a function whose corpus
  reach is mostly somebody else's. Dropping contested names instead cost `lme4`
  its `lmer` -- 36 scripts, the single function anyone sweeps `lme4` for --
  because `lmerTest` re-exports the name. So the scripts are split between owners
  in proportion to how many corpus archives load each. `plm` gets 23 of `vcovHC`
  and falls below its own `plm()`; `lme4` keeps `lmer`.

  This is an apportionment, not an attribution: which package a bare call meant
  is not knowable from the call site, and settling that is what the load evidence
  does downstream. It is used to rank and to state coverage, and every contested
  name is written out flagged so the assumption is visible.

What survives is reported with its corpus reach, so "this battery covers 38% of
the calls this package receives" is a number rather than a hope.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Probe:
    """One function a battery would exercise.

    Attributes:
        package: Owning package.
        function: Exported name.
        scripts: Corpus scripts calling it, apportioned when contested.
        owners: Every frame package exporting the name.
    """

    package: str
    function: str
    scripts: float
    owners: list[str]

    @property
    def contested(self) -> bool:
        """Whether more than one frame package exports this name.

        Returns:
            True when ownership is ambiguous from the call site alone.
        """
        return len(self.owners) > 1


@dataclass
class Battery:
    """The functions chosen for one package, and what they leave out.

    Attributes:
        package: Package the battery is for.
        probes: Chosen functions, most-called first.
        offered: Every candidate that survived the filters.
        calls: Corpus scripts calling anything this package exports, after
            filtering -- the denominator for coverage.
    """

    package: str
    probes: list[Probe]
    offered: list[Probe]
    calls: float

    @property
    def covered(self) -> float:
        """Corpus scripts the chosen probes reach.

        Returns:
            The summed script counts of the chosen probes.
        """
        return sum(p.scripts for p in self.probes)

    @property
    def coverage(self) -> float:
        """Share of this package's filtered corpus calls the battery reaches.

        The honest bound on what a sweep of this package can see. A change in a
        function no probe calls is invisible, and saying so with a number is the
        difference between a limitation and an excuse.

        Returns:
            `covered / calls`, or 0 when the package is never called.
        """
        return self.covered / self.calls if self.calls else 0.0


def read_frame(path: Path, language: str = "R") -> list[tuple[str, list[str], int]]:
    """Read the corpus-ranked procedure frame.

    Args:
        path: `sampling_frame.csv`.
        language: Which language's rows to keep.

    Returns:
        `(function, owners, scripts)` triples, most-called first.
    """
    rows = []
    with path.open() as handle:
        for row in csv.DictReader(handle):
            if row["language"] != language:
                continue
            owners = [name for name in row["packages"].split(";") if name]
            rows.append((row["fname"], owners, int(row["scripts"])))
    rows.sort(key=lambda r: (-r[2], r[0]))
    return rows


def apportion(scripts: int, owners: list[str], package: str, usage: dict) -> float:
    """Split a contested name's scripts between the packages that export it.

    In proportion to how many corpus archives load each owner. Crude, and
    deliberately so: it uses only counts already in the repository, and it
    replaces two worse options -- crediting every owner with the whole count, or
    discarding the name entirely.

    Args:
        scripts: Corpus scripts calling the name.
        owners: Frame packages exporting it.
        package: The one being apportioned to.
        usage: Package name to corpus archives loading it.

    Returns:
        This package's share. The whole count when it is the only owner, and an
        equal split when no owner is loaded by any archive.
    """
    if len(owners) <= 1:
        return float(scripts)
    weights = {name: max(usage.get(name, 0), 0) for name in owners}
    total = sum(weights.values())
    if total == 0:
        return scripts / len(owners)
    return scripts * weights.get(package, 0) / total


def build(
    package: str,
    frame: list[tuple[str, list[str], int]],
    shadowed: set[str],
    excluded: set[str],
    usage: dict | None = None,
    size: int = 3,
    minimum: float = 1.0,
) -> Battery:
    """Choose a package's probe battery.

    Args:
        package: Package to build a battery for.
        frame: Output of `read_frame`.
        shadowed: Names base R or a non-inferential package owns.
        excluded: Names that extract or format rather than compute.
        usage: Package name to corpus archives loading it, for apportionment.
        size: How many functions to probe.
        minimum: Apportioned scripts a function must have to qualify.

    Returns:
        The battery, with everything it passed over recorded beside it.
    """
    usage = usage or {}
    offered = [
        Probe(
            package=package,
            function=name,
            scripts=apportion(scripts, owners, package, usage),
            owners=owners,
        )
        for name, owners, scripts in frame
        if package in owners and name not in shadowed and name not in excluded
    ]
    offered.sort(key=lambda p: (-p.scripts, p.function))
    qualifying = [p for p in offered if p.scripts >= minimum]
    return Battery(
        package=package,
        probes=qualifying[:size],
        offered=offered,
        calls=sum(p.scripts for p in offered),
    )


BATTERY_COLUMNS = [
    "package",
    "function",
    "scripts",
    "chosen",
    "contested",
    "owners",
    "package_calls",
    "coverage",
]


def write_batteries(batteries: list[Battery], path: Path) -> None:
    """Write every candidate, chosen or not.

    The functions passed over are written alongside the chosen ones on purpose.
    A battery is a coverage claim, and a claim whose alternatives are invisible
    cannot be argued with.

    Args:
        batteries: One per package.
        path: Destination CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BATTERY_COLUMNS)
        writer.writeheader()
        for battery in sorted(batteries, key=lambda b: b.package):
            chosen = {p.function for p in battery.probes}
            for probe in battery.offered:
                writer.writerow(
                    {
                        "package": battery.package,
                        "function": probe.function,
                        "scripts": f"{probe.scripts:.4g}",
                        "chosen": int(probe.function in chosen),
                        "contested": int(probe.contested),
                        "owners": ";".join(probe.owners),
                        "package_calls": battery.calls,
                        "coverage": f"{battery.coverage:.4f}",
                    }
                )
