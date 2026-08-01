"""One item matrix serving every `psych` screen.

`psych`'s four shortlisted claims are all about scale statistics computed from a
matrix of items -- three about `alpha`, one about `ICC` -- so a single item
matrix serves all of them. What varies per claim is whether missing values are
present and whether the input is a covariance matrix or raw data.

Deterministic: the items are closed-form functions of subject and item index,
built so the scale is genuinely reliable (a positive common factor) rather than
noise, which is what makes alpha and ICC well defined.
"""

import csv
import math
from pathlib import Path

SUBJECTS = 60
ITEMS = 8


def build() -> list[list[float | str]]:
    """Construct the item matrix.

    Returns:
        One row per subject, with `ITEMS` responses. Some cells are missing --
        written as `NA` -- because two of the four claims are specifically about
        what `alpha` does when they are.
    """
    rows: list[list[float | str]] = []
    for subject in range(SUBJECTS):
        u = subject / (SUBJECTS - 1)
        # A shared latent trait, so the items correlate and alpha is meaningful.
        trait = math.sin(4 * u) + 0.6 * math.cos(u)
        row: list[float | str] = []
        for item in range(ITEMS):
            v = (item + 1) / ITEMS
            loading = 0.5 + 0.4 * v
            unique = 0.35 * math.sin(13 * u + 7 * v)
            value = loading * trait + unique
            # A missing cell every so often, spread across subjects and items
            # rather than in a block, so pairwise and listwise deletion give
            # different answers.
            missing = (subject * ITEMS + item) % 23 == 0
            row.append("NA" if missing else value)
        rows.append(row)
    return rows


COLUMNS = [f"i{n + 1}" for n in range(ITEMS)]


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in build():
            writer.writerow(
                [cell if isinstance(cell, str) else f"{cell:.17g}" for cell in row]
            )


if __name__ == "__main__":
    main()
