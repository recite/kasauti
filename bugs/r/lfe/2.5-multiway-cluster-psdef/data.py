"""Deterministic two-way clustered panel whose CGM covariance is not PSD.

The Cameron-Gelbach-Miller estimator for two clustering dimensions is
`V_firm + V_year - V_intersection`, a difference of covariance matrices, and
nothing forces the result to be positive semi-definite. When it is not, at least
one eigenvalue is negative and the standard errors read off its diagonal are
understating precision that the data does not contain.

Getting there needs few clusters in both dimensions, which is exactly the regime
applied panel work lives in: three firms and four years here. No RNG -- the
regressors are sine and cosine at fixed frequencies, so the negative eigenvalue
is a property of the design rather than of a seed. The frequencies (7 and 5, and
35 for the disturbance) were found by searching a small deterministic grid for
the largest resulting gap in a standard error.
"""

import csv
import math
from pathlib import Path

N = 60
FIRMS = 3
YEARS = 4

#: Frequencies for the two regressors and the disturbance. Their product drives
#: the disturbance, which keeps it orthogonal to neither regressor in a way any
#: single cluster dimension can absorb.
FREQ_X1 = 7
FREQ_X2 = 5


def build() -> list[dict[str, float]]:
    """Construct the panel.

    Firm cycles fastest and year cycles over blocks of firms, so every
    firm-by-year cell is populated and the two dimensions are non-nested --
    the case CGM exists for, and the case where its subtraction can overshoot.

    Returns:
        One dict per row with keys `y`, `x1`, `x2`, `firm`, `year`.
    """
    rows = []
    for i in range(N):
        firm = i % FIRMS + 1
        year = (i // FIRMS) % YEARS + 1
        x1 = math.sin(FREQ_X1 * i)
        x2 = math.cos(FREQ_X2 * i)
        y = (
            x1
            - x2
            + 2 * math.sin(FREQ_X1 * FREQ_X2 * i)
            + firm / 2
            + year / 3
        )
        rows.append({"y": y, "x1": x1, "x2": x2, "firm": firm, "year": year})
    return rows


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["y", "x1", "x2", "firm", "year"])
        for row in build():
            writer.writerow(
                [
                    f"{row['y']:.17g}",
                    f"{row['x1']:.17g}",
                    f"{row['x2']:.17g}",
                    int(row["firm"]),
                    int(row["year"]),
                ]
            )


if __name__ == "__main__":
    main()
