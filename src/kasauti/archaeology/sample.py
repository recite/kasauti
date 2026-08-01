"""Choose which packages to sweep, with inclusion probabilities that are written down.

Sweeping is the expensive stage -- a package's whole release history, one build
each -- so not every package in the frame can be swept, and which ones are is a
sampling decision. Made badly it is the same mistake this project has already
made twice: the first frame was named from memory, and the first screening queue
was worked in descending exposure. Both produce a set that cannot be weighted
back to anything.

So: **stratified, seeded, and recorded.** Two stratifiers, and neither is
aesthetic.

* **Usage**, because a bug's consequence is proportional to how much the package
  is run, and the top of that distribution is where the paper-level claims live.
  The very top is a **certainty stratum** -- taken with probability 1, because a
  study of statistical software that sampled away `MASS` would be answering a
  different question than the one asked.
* **Compiled code**, because it is the strongest available predictor of whether
  a release will build at all. Every wall in `docs/reach.md` but one is a C or
  C++ symbol, and `survival` -- 12 of 94 releases reachable -- is the case that
  makes stratifying on it necessary rather than tidy. Sampling without it risks
  a draw that is mostly unbuildable, and the shortfall would look like a finding
  about bug rates.

Each selected package carries the probability with which it was selected, so
package-level quantities can be Horvitz-Thompson weighted back to the frame
instead of being reported as if the sample were the population.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

#: Packages taken with certainty. The head of a usage distribution this skewed is
#: not a random quantity worth sampling: `MASS` at 459 corpus archives and 2,139
#: reverse dependencies is in the study or the study is about something else.
CERTAINTY = 8

#: Strata below the certainty layer, as quantile cuts on corpus usage.
TIERS = ("high", "medium", "low")


@dataclass
class Candidate:
    """One package the sample could include.

    Attributes:
        package: Package name.
        corpus: Replication archives loading it.
        strong: CRAN packages depending on it.
        compiled: Whether it ships code needing compilation.
        releases: How many releases it has, which is what a sweep costs.
    """

    package: str
    corpus: int
    strong: int
    compiled: bool
    releases: int


@dataclass
class Stratum:
    """One cell of the design.

    Attributes:
        name: Human-readable label.
        members: Candidates in the cell, sorted by package name.
        take: How many to draw.
    """

    name: str
    members: list[Candidate]
    take: int

    @property
    def probability(self) -> float:
        """Inclusion probability for every member of this cell.

        Returns:
            `take / size`, capped at 1.
        """
        if not self.members:
            return 0.0
        return min(self.take / len(self.members), 1.0)


@dataclass
class Selected:
    """One package drawn, with the probability it was drawn at.

    Attributes:
        package: Package name.
        stratum: Cell it came from.
        probability: Its inclusion probability.
        weight: `1 / probability`, the Horvitz-Thompson weight.
        corpus: Corpus archives loading it.
        compiled: Whether it needs compilation.
        releases: Releases a sweep would run.
    """

    package: str
    stratum: str
    probability: float
    weight: float
    corpus: int
    compiled: bool
    releases: int


def tier(index: int, total: int) -> str:
    """Which usage tier a rank falls in.

    Args:
        index: Zero-based rank by descending usage.
        total: How many packages are being ranked.

    Returns:
        One of `TIERS`.
    """
    if total <= 0:
        return TIERS[-1]
    position = index / total
    if position < 1 / 3:
        return TIERS[0]
    return TIERS[1] if position < 2 / 3 else TIERS[2]


def stratify(
    candidates: list[Candidate], per_stratum: int, certainty: int = CERTAINTY
) -> list[Stratum]:
    """Build the design.

    Args:
        candidates: Every package eligible for the sample.
        per_stratum: How many to draw from each non-certainty cell.
        certainty: How many of the most-used packages to take with probability 1.

    Returns:
        The strata, certainty cell first.
    """
    ordered = sorted(candidates, key=lambda c: (-c.corpus, c.package))
    head, tail = ordered[:certainty], ordered[certainty:]

    strata = [
        Stratum(
            name="certainty",
            members=sorted(head, key=lambda c: c.package),
            take=len(head),
        )
    ]

    cells: dict[str, list[Candidate]] = {}
    for index, candidate in enumerate(tail):
        key = (
            f"{tier(index, len(tail))}/{'compiled' if candidate.compiled else 'pure-R'}"
        )
        cells.setdefault(key, []).append(candidate)

    for name in sorted(cells):
        members = sorted(cells[name], key=lambda c: c.package)
        strata.append(
            Stratum(name=name, members=members, take=min(per_stratum, len(members)))
        )
    return strata


def draw(strata: list[Stratum], seed: int = 20260801) -> list[Selected]:
    """Draw the sample.

    Seeded and drawn from a name-sorted list, so the same frame and seed give the
    same sample on any machine. A sample nobody else can reproduce is a
    convenience sample with extra steps.

    Args:
        strata: The design.
        seed: Random seed, recorded with the output.

    Returns:
        The selected packages, with their inclusion probabilities.
    """
    # A seeded Mersenne Twister is exactly what is wanted here and a
    # cryptographic generator is exactly what is not: the sample has to be
    # reproducible from the seed on any machine.
    rng = random.Random(seed)  # noqa: S311
    selected: list[Selected] = []

    for stratum in strata:
        picked = (
            list(stratum.members)
            if stratum.take >= len(stratum.members)
            else rng.sample(stratum.members, stratum.take)
        )
        probability = stratum.probability
        for candidate in sorted(picked, key=lambda c: c.package):
            selected.append(
                Selected(
                    package=candidate.package,
                    stratum=stratum.name,
                    probability=probability,
                    weight=1.0 / probability if probability else 0.0,
                    corpus=candidate.corpus,
                    compiled=candidate.compiled,
                    releases=candidate.releases,
                )
            )
    return selected


SAMPLE_COLUMNS = [
    "package",
    "stratum",
    "probability",
    "weight",
    "corpus",
    "compiled",
    "releases",
]


def write_sample(selected: list[Selected], path: Path) -> None:
    """Write the drawn sample to CSV.

    Args:
        selected: The sample.
        path: Destination CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SAMPLE_COLUMNS)
        writer.writeheader()
        for row in sorted(selected, key=lambda s: (s.stratum, s.package)):
            writer.writerow(
                {
                    "package": row.package,
                    "stratum": row.stratum,
                    "probability": f"{row.probability:.6g}",
                    "weight": f"{row.weight:.6g}",
                    "corpus": row.corpus,
                    "compiled": int(row.compiled),
                    "releases": row.releases,
                }
            )


def read_sample(path: Path) -> list[Selected]:
    """Read a previously drawn sample.

    Args:
        path: Sample CSV.

    Returns:
        The selected packages.
    """
    with path.open() as handle:
        return [
            Selected(
                package=row["package"],
                stratum=row["stratum"],
                probability=float(row["probability"]),
                weight=float(row["weight"]),
                corpus=int(row["corpus"]),
                compiled=bool(int(row["compiled"])),
                releases=int(row["releases"]),
            )
            for row in csv.DictReader(handle)
        ]
