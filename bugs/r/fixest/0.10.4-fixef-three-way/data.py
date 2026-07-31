"""Deterministic panel with four fixed-effect dimensions that are not regular.

`fixef()` solves for the fixed-effect coefficients after the estimator has swept
them out. With three or more dimensions the sweep leaves a system that needs
reference levels chosen, and when the dimensions are not fully connected --
fixest calls this "not regular" -- choosing them is delicate. That is the regime
this dataset sits in.

No RNG. Each dimension cycles at a different stride over the row index (1, 2, 4,
and 7) so the four partitions cross each other irregularly rather than nesting,
and the regressor is a sine. The strides were found by searching a small
deterministic grid for the largest violation of the identity that decides the
case: extracted fixed effects plus `Xb` must reproduce the fitted values.
"""

import csv
import math
from pathlib import Path

N = 48
#: Strides for the four fixed-effect dimensions. Coprime-ish to each other and to
#: N, which is what keeps the partitions crossed rather than nested.
STRIDE_YR = 2
STRIDE_IND = 4
STRIDE_REG = 7
FREQ_X = 3


def build() -> list[dict[str, float]]:
    """Construct the panel.

    Returns:
        One dict per row with keys `y`, `x`, `id`, `yr`, `ind`, `reg`.
    """
    rows = []
    for i in range(N):
        ident = i % 7 + 1
        yr = (i // STRIDE_YR) % 6 + 1
        ind = (i // STRIDE_IND) % 4 + 1
        reg = (i // STRIDE_REG) % 3 + 1
        x = math.sin(FREQ_X * i)
        y = (
            x
            + ident / 2
            + yr / 3
            + ind / 4
            + reg / 5
            + math.cos(STRIDE_REG * FREQ_X * i) / 5
        )
        rows.append({"y": y, "x": x, "id": ident, "yr": yr, "ind": ind, "reg": reg})
    return rows


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["y", "x", "id", "yr", "ind", "reg"])
        for row in build():
            writer.writerow(
                [
                    f"{row['y']:.17g}",
                    f"{row['x']:.17g}",
                    int(row["id"]),
                    int(row["yr"]),
                    int(row["ind"]),
                    int(row["reg"]),
                ]
            )


if __name__ == "__main__":
    main()
