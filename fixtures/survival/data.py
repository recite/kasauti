"""One dataset serving every `survival` screen.

`survival` carries twelve of the forty-one shortlisted claims -- more than any
other package -- and its entries reach for a wide spread of shapes: strata,
offsets, case weights, clusters, competing risks, interval censoring, and the
counting-process `(start, stop]` form. So the columns are the union of what
those need, and each script takes the subset its condition names.

Deterministic throughout. Two package versions must differ by the package and by
nothing else, so no column is drawn from a generator.
"""

import csv
import math
from pathlib import Path

#: Forty subjects, each contributing two counting-process intervals. Enough for
#: a Cox model to converge with strata and clusters, small enough that a 2009
#: build fits it instantly.
SUBJECTS = 40


def build() -> list[dict[str, float]]:
    """Construct the dataset.

    Returns:
        Two rows per subject, in `(start, stop]` form. The second row of each
        pair carries the subject's event, so collapsing on `id` gives an
        ordinary right-censored dataset.
    """
    rows = []
    for subject in range(SUBJECTS):
        u = subject / (SUBJECTS - 1)
        x1 = math.sin(5 * u)
        x2 = math.cos(3 * u) - 0.4 * math.sin(7 * u)
        # Durations spread over an order of magnitude, with ties, because a tie
        # is where several of these entries live.
        span = 2.0 + 8.0 * abs(math.sin(4 * u))
        middle = span / 2.0
        event = float(subject % 3 != 0)
        for part in (0, 1):
            start = 0.0 if part == 0 else middle
            stop = middle if part == 0 else span
            rows.append(
                {
                    "id": float(subject + 1),
                    "start": start,
                    "stop": stop,
                    # Only the closing interval can carry the event.
                    "event": event if part == 1 else 0.0,
                    "time": span,
                    "status": event,
                    "x1": x1,
                    "x2": x2,
                    # Two strata and four clusters, crossed, so a strata term
                    # and a cluster term are not the same grouping.
                    "s": float(subject % 2 + 1),
                    "cl": float(subject % 4 + 1),
                    # Case weights that vary *within* a cluster, which is the
                    # condition survival 3.6-1 names.
                    "w": 1.0 + 0.5 * abs(math.cos(9 * u)) + 0.1 * part,
                    "off": 0.2 * math.sin(2 * u),
                    # Three competing outcomes, for the Fine-Gray screens: 0
                    # censored, 1 the cause of interest, 2 a competing cause.
                    "cause": float(0 if subject % 5 == 0 else (1 + subject % 2)),
                    # An interval-censored pair. A quarter of the subjects have
                    # an open upper endpoint, which is survival 2.41-2's case.
                    "lo": 0.5 * span,
                    "hi": span if subject % 4 else float("inf"),
                }
            )
    return rows


COLUMNS = [
    "id",
    "start",
    "stop",
    "event",
    "time",
    "status",
    "x1",
    "x2",
    "s",
    "cl",
    "w",
    "off",
    "cause",
    "lo",
    "hi",
]


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in build():
            # `Inf` rather than `1.7976931348623157e+308`: R reads it back as
            # infinite, which is the point of the column.
            writer.writerow(
                ["Inf" if math.isinf(row[c]) else f"{row[c]:.17g}" for c in COLUMNS]
            )


if __name__ == "__main__":
    main()
