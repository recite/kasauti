"""statsmodels side: unpenalized maximum likelihood on separated data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))

import concord_py as cc  # noqa: E402
import numpy as np  # noqa: E402
import statsmodels.api as sm  # noqa: E402


def body(data_path):
    """Fit an unpenalized logit and report what comes back.

    Whatever this raises is the observation: `cc.main` records the exception as
    `status: "error"`, which sits in the report beside the packages that returned
    a number for the same data.

    Args:
        data_path: Path to `data.csv`.

    Returns:
        Quantities and diagnostics for the result schema.
    """
    d = cc.read_csv(data_path)
    y = np.asarray(d["y"])
    design = sm.add_constant(np.asarray(d["x"]))

    fit = sm.Logit(y, design).fit(disp=0)
    return {
        "quantities": {
            "coef.intercept": fit.params[0],
            "coef.x": fit.params[1],
            "se.x": fit.bse[1],
            "pvalue.x": fit.pvalues[1],
        },
        "diagnostics": {
            "converged": bool(fit.mle_retvals.get("converged")),
            "iterations": int(fit.mle_retvals.get("iterations", -1)),
        },
    }


cc.main("logit_separation", "statsmodels", body, packages=["numpy", "statsmodels"])
