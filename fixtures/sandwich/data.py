"""One dataset serving every screen in this package.

A fixture is per-package, not per-bug. The forty-one shortlisted entries span
sixteen packages, and the concentration is the whole argument: `survival` alone
is twelve claims, `plm` five. Writing a dataset per claim is what kept the base
at seven records.

So the columns are a superset -- a short panel with clusters, weights, two
continuous responses, a binary one, and a duration -- and each screen script
takes the subset its condition needs. Nothing here is random: every column is a
closed-form function of the row index, so two package versions differ by the
package and by nothing else.
"""

import csv
import math
from pathlib import Path

#: Twelve units observed five times. Small enough that a decade-old package
#: fits it in milliseconds, structured enough to support clustering and panels.
UNITS = 12
PERIODS = 5


def build() -> list[dict[str, float]]:
    """Construct the dataset.

    Returns:
        One dict per row.
    """
    rows = []
    for unit in range(UNITS):
        for period in range(PERIODS):
            i = unit * PERIODS + period
            t = i / (UNITS * PERIODS - 1)
            x1 = math.sin(6 * t)
            x2 = math.cos(4 * t) + 0.5 * math.sin(9 * t)
            # A treatment that varies within unit, so a fixed-effects or
            # difference-in-means screen has something to estimate.
            d = float(period >= 2 + (unit % 3))
            rows.append(
                {
                    "id": float(unit + 1),
                    "t": float(period + 1),
                    "g": float(unit % 4 + 1),
                    "x1": x1,
                    "x2": x2,
                    "d": d,
                    # Strictly positive and unequal, so a weighted estimator
                    # cannot coincide with an unweighted one by accident.
                    "w": 1.0 + 0.5 * abs(math.cos(3 * t)),
                    "y": 1.0 + 2.0 * x1 - 0.7 * x2 + 0.4 * d + 0.3 * math.sin(11 * t),
                    "y2": 0.5 - 1.3 * x1 + 0.9 * x2 + 0.2 * math.cos(7 * t),
                    "yb": float(x1 + 0.5 * x2 > 0.0),
                    # A duration and a censoring indicator, for survival screens.
                    "time": 1.0 + 4.0 * abs(math.sin(5 * t)) + 0.1 * i,
                    "status": float((i % 4) != 0),
                }
            )
    return rows


COLUMNS = [
    "id",
    "t",
    "g",
    "x1",
    "x2",
    "d",
    "w",
    "y",
    "y2",
    "yb",
    "time",
    "status",
]


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
