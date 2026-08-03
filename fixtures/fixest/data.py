"""A panel with singleton fixed effects, because that is the whole question.

Absorbing a fixed effect forces a decision about groups that appear exactly
once. A singleton is perfectly fit by its own dummy: it contributes no
identifying variation, and it inflates the parameter count while doing it. Every
package that absorbs fixed effects has to choose, and the choice determines the
estimation sample -- N, the residual degrees of freedom, the cluster count, and
therefore every standard error downstream.

So the fixture supplies them by construction, in a known quantity, and the probe
asserts they survived. The proportions echo the case that prompted this: a
grouping variable where a substantial minority of levels hold a single
observation each.

Deterministic throughout. Two package versions differ by the package.
"""

import csv
import math
from pathlib import Path

#: Groups holding several observations each -- these identify the model.
MULTI = 40
PER_MULTI = 6

#: Groups holding exactly one. These are the singletons, and how a package
#: treats them is what the probe measures.
SINGLETON = 20

#: A second, crossed fixed effect, and a clustering variable that is neither.
PERIODS = 6
CLUSTERS = 8


def build() -> list[dict[str, float]]:
    """Construct the panel.

    Returns:
        One dict per observation. `MULTI` groups contribute `PER_MULTI` rows
        each and `SINGLETON` groups contribute one, so the singleton count and
        the observation count are both known in advance and can be asserted.
    """
    rows: list[dict[str, float]] = []

    def observation(group: int, period: int, index: int) -> dict[str, float]:
        u = index / 100.0
        x1 = math.sin(5 * u + group)
        x2 = math.cos(3 * u - 0.4 * group)
        alpha = 0.9 * math.sin(2.0 * group / MULTI)
        gamma = 0.5 * math.cos(1.7 * period)
        return {
            "g": float(group),
            "t": float(period + 1),
            "cl": float(group % CLUSTERS + 1),
            "x1": x1,
            "x2": x2,
            "y": alpha + gamma + 1.6 * x1 - 0.9 * x2 + 0.25 * math.sin(11 * u),
        }

    index = 0
    for group in range(1, MULTI + 1):
        for period in range(PER_MULTI):
            rows.append(observation(group, period % PERIODS, index))
            index += 1

    for offset in range(SINGLETON):
        group = MULTI + 1 + offset
        rows.append(observation(group, offset % PERIODS, index))
        index += 1

    return rows


COLUMNS = ["g", "t", "cl", "x1", "x2", "y"]


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in build():
            writer.writerow([f"{row[c]:.17g}" for c in COLUMNS])


if __name__ == "__main__":
    main()
