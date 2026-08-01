"""Data for `MASS`, whose battery spans three unrelated jobs.

`mvrnorm` (54 corpus scripts) wants a covariance structure, `ginv` (31) wants a
matrix that is singular so the generalised inverse is not the ordinary one, and
`glm.nb` (29) wants overdispersed counts. One frame carries all three: the
continuous columns supply the covariance and the design, and `count` is
overdispersed by construction so a negative binomial has a dispersion parameter
to find.
"""

import csv
import math
from pathlib import Path

N = 120


def build() -> list[dict[str, float]]:
    """Construct the frame.

    Returns:
        One dict per row. `x3` is exactly `x1 + x2`, which makes the design
        matrix rank-deficient — the case where `ginv` differs from `solve`.
    """
    rows = []
    for i in range(N):
        u = i / (N - 1)
        x1 = math.sin(6 * u)
        x2 = math.cos(4 * u) + 0.3 * math.sin(9 * u)
        rate = math.exp(1.1 + 0.8 * x1 - 0.4 * x2)
        # Overdispersion without an RNG: the multiplier swings well outside what
        # a Poisson would allow, so glm.nb has a theta to estimate rather than
        # collapsing to a Poisson fit.
        swing = 1.0 + 0.9 * math.sin(17 * u)
        rows.append(
            {
                "x1": x1,
                "x2": x2,
                "x3": x1 + x2,
                "y": 2.0 + 1.5 * x1 - 0.7 * x2 + 0.4 * math.sin(13 * u),
                "count": float(max(round(rate * swing), 0)),
            }
        )
    return rows


COLUMNS = ["x1", "x2", "x3", "y", "count"]


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
