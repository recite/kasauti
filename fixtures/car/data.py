"""A regression `car`'s battery can interrogate.

All three probes work on a fitted linear model rather than on raw data:
`linearHypothesis` (30 corpus scripts) tests restrictions on its coefficients,
`deltaMethod` (15) propagates their covariance through a nonlinear function, and
`ncvTest` looks for non-constant variance. So the fixture supplies a design with
three genuinely distinct predictors and a deliberately heteroskedastic error, and
the coefficients are far from zero so a ratio of them is well conditioned.
"""

import csv
import math
from pathlib import Path

N = 100


def build() -> list[dict[str, float]]:
    """Construct the frame.

    Returns:
        One dict per row.
    """
    rows = []
    for i in range(N):
        u = i / (N - 1)
        x1 = math.sin(5 * u)
        x2 = math.cos(3 * u) - 0.4 * math.sin(8 * u)
        x3 = math.sin(11 * u) * math.cos(2 * u)
        # Error scale grows with x1, so a non-constant-variance test has
        # something to find rather than reporting a null it was handed.
        noise = (0.15 + 0.7 * abs(x1)) * math.sin(29 * u)
        rows.append(
            {
                "x1": x1,
                "x2": x2,
                "x3": x3,
                # Coefficients well away from zero: deltaMethod on a ratio is
                # ill-conditioned when the denominator can be near zero.
                "y": 3.0 + 2.5 * x1 - 1.6 * x2 + 0.9 * x3 + noise,
            }
        )
    return rows


COLUMNS = ["x1", "x2", "x3", "y"]


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
