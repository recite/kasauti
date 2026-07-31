"""An unbalanced panel where one unit is observed exactly once.

Two datasets, differing only in whether a singleton group is present:

* `data.csv`     -- five units, four periods each
* `singleton.csv` -- the same, plus a sixth unit with a single observation

The singleton is the whole triggering condition, and it is not exotic: any
panel where one unit enters and leaves within a period, or is dropped to a
single usable row by missingness, has one.

No RNG. The response carries a component at a frequency the regressors do not,
so the residuals are genuine rather than zero -- an earlier version of this
case fit perfectly and reported standard errors of 0.000000 for every method,
which hid the effect entirely.
"""

import csv
import math
from pathlib import Path

UNITS, PERIODS = 5, 4


def build(with_singleton: bool) -> list[dict[str, float]]:
    """Construct the panel.

    Args:
        with_singleton: Append a sixth unit observed once.

    Returns:
        One dict per row with keys `id`, `tm`, `y`, `x`, `z`.
    """
    ids = [u for u in range(1, UNITS + 1) for _ in range(PERIODS)]
    times = [t for _ in range(UNITS) for t in range(1, PERIODS + 1)]
    if with_singleton:
        ids, times = [*ids, UNITS + 1], [*times, 1]

    rows = []
    for k, (unit, period) in enumerate(zip(ids, times, strict=True), start=1):
        x = math.sin(k)
        z = math.cos(2 * k)
        rows.append(
            {
                "id": unit,
                "tm": period,
                # The final term is what leaves residual variation behind.
                "y": 0.8 * x - 0.4 * z + 0.1 * unit + 0.5 * math.sin(3.7 * k + 1.1),
                "x": x,
                "z": z,
            }
        )
    return rows


def main() -> None:
    """Write `data.csv` and `singleton.csv` beside this script."""
    here = Path(__file__).parent
    for name, singleton in (("data.csv", False), ("singleton.csv", True)):
        with (here / name).open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "tm", "y", "x", "z"])
            for row in build(singleton):
                writer.writerow(
                    [
                        int(row["id"]),
                        int(row["tm"]),
                        f"{row['y']:.17g}",
                        f"{row['x']:.17g}",
                        f"{row['z']:.17g}",
                    ]
                )


if __name__ == "__main__":
    main()
