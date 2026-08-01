"""A two-way fixed-effects panel with clusters, for `lfe`.

`felm` is called by **245** corpus scripts — the single highest-reach function in
the whole frame, and the one this study's package list forgot when it was written
from memory. So the fixture is built for it: two crossed fixed effects, a
clustering variable that is neither of them, and enough within-group variation
that the estimator has something to identify.

Deterministic. Two package versions must differ by the package and nothing else.
"""

import csv
import math
from pathlib import Path

FIRMS = 25
YEARS = 8


def build() -> list[dict[str, float]]:
    """Construct the panel.

    Returns:
        One dict per firm-year. `fe1` and `fe2` are crossed rather than nested,
        which is what makes this a two-way problem rather than a one-way one,
        and `cl` cuts across both so clustered errors are not the same as either
        fixed effect.
    """
    rows = []
    for firm in range(FIRMS):
        alpha = math.sin(2.0 * (firm + 1) / FIRMS)
        for year in range(YEARS):
            u = year / (YEARS - 1)
            gamma = math.cos(3.0 * u)
            x1 = math.sin(5 * u + firm)
            x2 = math.cos(2 * u - 0.4 * firm)
            rows.append(
                {
                    "fe1": float(firm + 1),
                    "fe2": float(2000 + year),
                    # Crossed with neither: firms split into 5 clusters, so a
                    # clustered covariance is a third grouping.
                    "cl": float(firm % 5 + 1),
                    "x1": x1,
                    "x2": x2,
                    "w": 1.0 + 0.4 * abs(math.sin(9 * u + firm)),
                    "y": alpha + gamma + 1.7 * x1 - 0.9 * x2 + 0.3 * math.sin(11 * u),
                }
            )
    return rows


COLUMNS = ["fe1", "fe2", "cl", "x1", "x2", "w", "y"]


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
