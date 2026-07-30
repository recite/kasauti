"""Deterministic data for a multivariate linear model.

Two responses measured on the same predictor -- the shape `lm(cbind(y1, y2) ~ x)`
fits and `vcovHC.mlm` covers. Closed form, no RNG, so the only thing that differs
between the two package versions is the package.
"""

import csv
import math
from pathlib import Path

N = 30


def build() -> list[dict[str, float]]:
    """Construct the dataset.

    The two responses share a predictor but move on different periods, so the
    cross-equation covariance is genuinely non-zero -- which is the block the
    bug corrupted.

    Returns:
        One dict per row with keys `x`, `y1`, `y2`.
    """
    rows = []
    for i in range(N):
        x = i / (N - 1)
        rows.append(
            {
                "x": x,
                "y1": math.sin(6 * x) + 0.3 * math.cos(2 * x),
                "y2": math.cos(5 * x) - 0.4 * math.sin(3 * x),
            }
        )
    return rows


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x", "y1", "y2"])
        for row in build():
            writer.writerow([f"{row[k]:.17g}" for k in ("x", "y1", "y2")])


if __name__ == "__main__":
    main()
