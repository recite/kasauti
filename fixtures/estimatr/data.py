"""A blocked, weighted experiment with three arms, for `estimatr`.

Both `estimatr` claims are about `difference_in_means` under conditions the
default experiment does not meet: one needs more than two treatment conditions,
the other needs weights and blocks supplied together. So the fixture carries a
three-armed treatment, block labels, and unequal weights, and each script names
the subset it uses.
"""

import csv
import math
from pathlib import Path

N = 120
ARMS = 3
BLOCKS = 4


def build() -> list[dict[str, float]]:
    """Construct the experiment.

    Returns:
        One dict per unit. Assignment cycles through arms within block, so every
        arm appears in every block and a blocked estimator is well defined.
    """
    rows = []
    for i in range(N):
        u = i / (N - 1)
        arm = i % ARMS
        block = (i // ARMS) % BLOCKS
        effect = (0.0, 0.8, -0.5)[arm]
        rows.append(
            {
                "z": float(arm),
                "block": float(block + 1),
                # Weights vary within block, so a weighted estimate and an
                # unweighted one cannot coincide.
                "w": 1.0 + 0.6 * abs(math.sin(7 * u + block)),
                "x1": math.cos(3 * u),
                "y": 1.0 + effect + 0.4 * block + 0.5 * math.sin(11 * u),
            }
        )
    return rows


COLUMNS = ["z", "block", "w", "x1", "y"]


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
