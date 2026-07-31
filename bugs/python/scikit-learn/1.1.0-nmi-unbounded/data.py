"""Two clusterings where one is degenerate.

`b` puts every point in a single cluster, so its entropy is zero. Mutual
information with a zero-entropy labeling is zero, and normalized mutual
information is therefore zero under any sensible normalizer. The bug is what the
`min` and `geometric` normalizers did with the resulting division.

Found by searching 16,000 small random labelings for a result outside [0, 1] --
the metric's own bound -- and taking the clearest hit. Written out as literals so
the case does not depend on a random search reproducing.
"""

import csv
from pathlib import Path

A = [0, 1, 1, 1, 0, 0, 0, 1, 1, 1]
B = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]


def main() -> None:
    """Write `data.csv` beside this script."""
    out = Path(__file__).with_name("data.csv")
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["a", "b"])
        for a, b in zip(A, B, strict=True):
            writer.writerow([a, b])


if __name__ == "__main__":
    main()
