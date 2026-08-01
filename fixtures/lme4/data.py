"""Grouped data for `lme4`, sized so the variance components are identified.

`lmer` (33 corpus scripts), `glmer` (12), and `fixef` (12) all need the same
thing: a grouping factor with enough levels to estimate a random-effect
variance, and enough within-group variation that it is not confounded with the
fixed effects. Twenty groups of eight is comfortably above where a variance
component collapses to zero and small enough that a decade-old build fits it in
a moment.

The group effects and the binary outcome are closed-form functions of the
indices, so nothing here depends on an RNG.
"""

import csv
import math
from pathlib import Path

GROUPS = 20
PER_GROUP = 8


def build() -> list[dict[str, float]]:
    """Construct the frame.

    Returns:
        One dict per observation.
    """
    rows = []
    for group in range(GROUPS):
        # A group effect with real spread: a variance component estimated from
        # near-identical groups is a boundary fit, and boundary fits are where
        # optimisers disagree for reasons that are not the question here.
        effect = 1.4 * math.sin(2.0 * (group + 1) / GROUPS * math.pi)
        for member in range(PER_GROUP):
            u = member / (PER_GROUP - 1)
            x1 = math.sin(4 * u + group)
            x2 = math.cos(3 * u - 0.5 * group)
            linear = 0.6 + 1.3 * x1 - 0.8 * x2 + effect
            rows.append(
                {
                    "g": float(group + 1),
                    "x1": x1,
                    "x2": x2,
                    "y": linear + 0.25 * math.sin(19 * u + group),
                    "yb": float(linear > 0.6),
                }
            )
    return rows


COLUMNS = ["g", "x1", "x2", "y", "yb"]


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
