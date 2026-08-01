"""A regression with a deliberately aliased column, for `lmtest`.

`lmtest@0.9-35#2` is about `bptest` on aliased or collinear regressors, so the
fixture supplies the collinearity rather than hoping for it: `x3` is an exact
linear combination of `x1` and `x2`, which makes `lm` alias it and leaves the
Breusch-Pagan test to decide what to do about a rank-deficient fit.
"""

import csv
import math
from pathlib import Path

N = 80


def build() -> list[dict[str, float]]:
    """Construct the dataset.

    Returns:
        One dict per row. `x3` is exactly `2 * x1 - x2`, so a fit including all
        three is rank deficient and `lm` drops one.
    """
    rows = []
    for i in range(N):
        u = i / (N - 1)
        x1 = math.sin(6 * u)
        x2 = math.cos(4 * u) + 0.3 * math.sin(11 * u)
        # Heteroskedastic by construction: the residual scale grows with x1, so
        # the test the entry is about has something to detect.
        noise = (0.2 + 0.8 * abs(x1)) * math.sin(23 * u)
        rows.append(
            {
                "x1": x1,
                "x2": x2,
                "x3": 2.0 * x1 - x2,
                "y": 1.0 + 2.0 * x1 - 0.5 * x2 + noise,
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
