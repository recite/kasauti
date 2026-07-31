"""Deterministic clustered data with a binary outcome and unequal weights.

Three fits come off this one dataset: a plain `lm`, an `lm` with weights, and a
`glm`. The bug is documented to reach the second and third and not the first, so
the dataset has to support all three at once for the comparison to isolate it.

No RNG. Eight clusters of five, which is the small-G regime where cluster-robust
covariance is most sensitive to exactly the kind of correction this bug touched.
"""

import csv
import math
from pathlib import Path

N = 40
CLUSTERS = 8


def build() -> list[dict[str, float]]:
    """Construct the dataset.

    Returns:
        One dict per row with keys `x`, `y`, `g`, `w`.
    """
    rows = []
    for i in range(N):
        x = i / (N - 1)
        g = i // (N // CLUSTERS) + 1
        rows.append(
            {
                "x": x,
                "y": int(math.sin(7 * x) + g / 20 > 0.3),
                "g": g,
                # Unequal weights: an lm with all-equal weights would not
                # exercise the weighted path the bug lives on.
                "w": 1 + ((i + 1) % 3),
            }
        )
    return rows


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x", "y", "g", "w"])
        for row in build():
            writer.writerow(
                [f"{row['x']:.17g}", int(row["y"]), int(row["g"]), int(row["w"])]
            )


if __name__ == "__main__":
    main()
