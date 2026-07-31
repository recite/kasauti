"""Normalized mutual information under each of scikit-learn's normalizers.

One script serves both backends; the case pins the scikit-learn version through
`uv`, so which version this runs against is decided outside the file. Same trick
the R cases use with `lib.loc`, expressed in Python's packaging instead.

Only the standard library is imported before scikit-learn, so this runs unchanged
in an environment built around a four-year-old release.
"""

import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.environ.get("CONCORD_LIB", str(Path(__file__).resolve().parents[4] / "lib"))
)

import concord_py as cc  # noqa: E402
from sklearn.metrics import normalized_mutual_info_score  # noqa: E402


def body(data_path):
    """Compute NMI under all four averaging methods.

    Every value is reported, not just the ones expected to move, because the
    finding is as much about which normalizers escape the bug as about which
    fall into it.

    Args:
        data_path: Path to `data.csv`.

    Returns:
        Quantities and diagnostics for the result schema.
    """
    columns = cc.read_csv(data_path)
    a = [int(v) for v in columns["a"]]
    b = [int(v) for v in columns["b"]]

    quantities = {}
    for method in ("min", "geometric", "arithmetic", "max"):
        quantities[f"nmi@{method}"] = normalized_mutual_info_score(
            a, b, average_method=method
        )

    import sklearn

    return {
        "quantities": quantities,
        "diagnostics": {
            "sklearn_version": sklearn.__version__,
            "n": len(a),
            "clusters_a": len(set(a)),
            # Zero entropy in b is the whole triggering condition.
            "clusters_b": len(set(b)),
        },
    }


cc.main(
    "sklearn_nmi_unbounded",
    "buggy" if "--buggy" in sys.argv else "fixed",
    body,
    packages=["sklearn", "numpy"],
)
