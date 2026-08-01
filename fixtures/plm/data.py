"""One balanced panel serving every `plm` screen.

`plm`'s five shortlisted claims all want the same thing -- a panel with an index,
a regressor, and enough periods to lag -- and differ in what is estimated from
it: a GMM model with instruments, a Lagrange-multiplier test, a Hausman test, a
Beck-Katz covariance.

Twenty units over eight periods. Long enough that `pgmm` has instruments to build
after differencing, small enough that a 2010 build fits it instantly, and
balanced so that a screen never conflates the claim under test with an
unbalanced-panel code path.
"""

import csv
import math
from pathlib import Path

UNITS = 20
PERIODS = 8


def build() -> list[dict[str, float]]:
    """Construct the panel.

    Returns:
        One dict per unit-period.
    """
    rows = []
    for unit in range(UNITS):
        a = math.sin(3.0 * (unit + 1) / UNITS)
        lagged = 0.0
        for period in range(PERIODS):
            u = period / (PERIODS - 1)
            x1 = math.sin(5 * u + unit)
            x2 = math.cos(2 * u - 0.3 * unit)
            # A dynamic outcome, so a GMM estimator has something to instrument
            # and the lag structure the pgmm claims are about is real.
            y = 0.4 * lagged + a + 1.5 * x1 - 0.8 * x2 + 0.2 * math.sin(9 * u)
            lagged = y
            rows.append(
                {
                    "id": float(unit + 1),
                    "year": float(2000 + period),
                    "y": y,
                    "x1": x1,
                    "x2": x2,
                    "w": 1.0 + 0.4 * abs(math.cos(7 * u + unit)),
                }
            )
    return rows


COLUMNS = ["id", "year", "y", "x1", "x2", "w"]


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
