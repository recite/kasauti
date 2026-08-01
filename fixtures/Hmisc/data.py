"""Data with missing values and weights, for `Hmisc`.

Hmisc's battery is the weakest in the sample -- 16% coverage, and its three
top-called functions are an imputation routine, a wrapper that fits over the
imputations, and a data-reshaping helper. That is what the corpus calls it for,
so that is what gets probed; the low coverage is reported rather than fixed by
substituting functions nobody uses.

`aregImpute` needs missing values spread across several columns, and the
weighted estimators need weights that vary. Both are supplied here rather than
arranged in the probe.
"""

import csv
import math
from pathlib import Path

N = 150


def build() -> list[list[str]]:
    """Construct the frame.

    Returns:
        One row per observation, with `NA` written where a value is missing.
        Missingness depends on the row index and differs by column, so it is
        neither monotone nor identical across columns -- an imputation that
        exploited either would look better here than it is.
    """
    rows = []
    for i in range(N):
        u = i / (N - 1)
        x1 = math.sin(6 * u)
        x2 = math.cos(4 * u) + 0.4 * math.sin(9 * u)
        x3 = math.sin(11 * u) * math.cos(3 * u)
        y = 2.0 + 1.4 * x1 - 0.8 * x2 + 0.5 * x3 + 0.2 * math.sin(23 * u)
        weight = 1.0 + 0.8 * abs(math.cos(7 * u))

        cells = {"x1": x1, "x2": x2, "x3": x3, "y": y}
        for offset, name in enumerate(("x1", "x2", "x3")):
            if (i + 3 * offset) % 11 == 0:
                cells[name] = None
        rows.append(
            [
                "NA" if cells[c] is None else f"{cells[c]:.17g}"
                for c in ("x1", "x2", "x3", "y")
            ]
            + [f"{weight:.17g}"]
        )
    return rows


COLUMNS = ["x1", "x2", "x3", "y", "w"]


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerows(build())


if __name__ == "__main__":
    main()
