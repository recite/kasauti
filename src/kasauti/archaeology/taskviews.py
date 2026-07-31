"""Select which packages to study, from CRAN's own curation rather than mine.

The first version of this study named its packages from memory. That is the worst
possible sampling frame: it is unfalsifiable, it cannot be reproduced by anyone
else, and its errors are invisible -- a package left off the list looks exactly
like a package with nothing wrong. Measuring the corpus afterwards showed the
cost. `lfe`, used in 222 replication archives, was simply forgotten.

The frame here is the intersection of two independent sources, neither of them
mine. **CRAN Task Views** are expert-maintained, versioned, citable lists of the
packages that belong to a field. **The corpus** says how often published
replication archives actually load a package. A package qualifies by being both
recognized by the field and used in the literature.

Judgment survives in exactly two places, both visible and both stated at the
level of a category rather than a package:

* `INFERENTIAL_VIEWS` -- which of CRAN's 49 views describe inference rather than
  numerical infrastructure or a distant domain.
* `NON_INFERENTIAL` -- packages whose whole job is plotting, formatting, or data
  manipulation. This one is unavoidable: `ggplot2` is listed in the Spatial and
  NetworkAnalysis views, so no choice of views excludes it.

Both are exclusion rules, and exclusions are falsifiable in a way inclusions are
not. "Is ggplot2 inferential?" has an answer anyone can check. "Did you remember
lfe?" does not.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

import requests

CRAN_VIEWS = "https://cran.r-project.org/web/views"

USER_AGENT = "kasauti/0.1 (research; differential testing of statistical software)"

#: Package links inside a rendered task view page.
VIEW_PACKAGE = re.compile(r"\.\./packages/([A-Za-z][\w.]*)/index\.html")

#: Links on the task view index, which is where the list of views comes from.
#: Reading it rather than hard-coding names is not pedantry: the `SocialSciences`
#: view a social-science study would obviously reach for was retired, and asking
#: for it by name returns an empty list that looks like a view with no packages.
VIEW_NAME = re.compile(r"href=[\"']([A-Za-z]+)\.html")

#: The task views whose subject is inference -- estimating quantities, testing
#: hypotheses, fitting models. Excluded are views about software infrastructure
#: (Databases, HighPerformanceComputing, WebTechnologies, ModelDeployment),
#: presentation (DynamicVisualizations, ReproducibleResearch, TeachingStatistics),
#: numerical methods rather than statistics (NumericalMathematics, Optimization,
#: DifferentialEquations), and laboratory domains far from a social-science
#: replication corpus (ChemPhys, MedicalImaging, Omics, Paleontology,
#: Pharmacokinetics, Phylogenetics, Agriculture, Hydrology, Tracking,
#: SportsAnalytics, NaturalLanguageProcessing).
INFERENTIAL_VIEWS = [
    "ActuarialScience",
    "AnomalyDetection",
    "Bayesian",
    "CausalInference",
    "ClinicalTrials",
    "Cluster",
    "CompositionalData",
    "Distributions",
    "Econometrics",
    "Environmetrics",
    "Epidemiology",
    "ExperimentalDesign",
    "ExtremeValue",
    "Finance",
    "FunctionalData",
    "GraphicalModels",
    "MachineLearning",
    "MetaAnalysis",
    "MissingData",
    "MixedModels",
    "NetworkAnalysis",
    "OfficialStatistics",
    "Psychometrics",
    "Robust",
    "Spatial",
    "SpatioTemporal",
    "Survival",
    "TimeSeries",
]

#: Packages a task view lists for good reasons that have nothing to do with
#: producing a number. A bug in any of these can make a figure wrong or a table
#: ugly; none of them can change a coefficient. This is the package-level twin of
#: `NON_COMPUTING`, and it exists because view membership cannot separate them:
#: `ggplot2` is genuinely part of the Spatial and NetworkAnalysis toolkits.
NON_INFERENTIAL = {
    # plotting
    "ggplot2",
    "lattice",
    "latticeExtra",
    "RColorBrewer",
    "viridis",
    "viridisLite",
    "gridExtra",
    "cowplot",
    "ggrepel",
    "ggthemes",
    "scales",
    "plotly",
    "maps",
    "mapproj",
    "sjPlot",
    "dotwhisker",
    "corrplot",
    "GGally",
    # tables and reports
    "stargazer",
    "xtable",
    "texreg",
    "modelsummary",
    "huxtable",
    "kableExtra",
    "knitr",
    "rmarkdown",
    "gt",
    "flextable",
    # data manipulation and IO
    "dplyr",
    "tidyr",
    "tidyverse",
    "data.table",
    "readr",
    "readxl",
    "haven",
    "foreign",
    "reshape2",
    "reshape",
    "plyr",
    "stringr",
    "stringi",
    "magrittr",
    "purrr",
    "tibble",
    "forcats",
    "lubridate",
    "janitor",
    "glue",
    "here",
    "devtools",
}


@dataclass
class Selection:
    """One package that qualified for the frame.

    Attributes:
        package: CRAN package name.
        views: Task views listing it, sorted.
        usage: Replication archives in the corpus that load it.
    """

    package: str
    views: list[str]
    usage: int


def _get(url: str) -> str:
    """Fetch a page as text.

    Args:
        url: URL to fetch.

    Returns:
        The response body.
    """
    response = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def available_views() -> list[str]:
    """List every task view CRAN currently publishes.

    Returns:
        View names, sorted.
    """
    return sorted(set(VIEW_NAME.findall(_get(f"{CRAN_VIEWS}/"))))


def fetch_views(names: list[str]) -> dict[str, list[str]]:
    """Fetch the package membership of each named task view.

    Args:
        names: View names.

    Returns:
        View name to the packages it lists, sorted.

    Raises:
        ValueError: If a view returns no packages, which means the name is wrong
            rather than that the view is empty.
    """
    members = {}
    for name in names:
        packages = sorted(set(VIEW_PACKAGE.findall(_get(f"{CRAN_VIEWS}/{name}.html"))))
        if not packages:
            raise ValueError(f"task view {name!r} listed no packages")
        members[name] = packages
    return members


def load_views(path: Path, names: list[str] | None = None) -> dict[str, list[str]]:
    """Load task view membership, fetching and caching it once.

    Membership is cached and checked in so the frame cannot change underneath a
    result because CRAN edited a view.

    Args:
        path: Cache file.
        names: View names to fetch on a miss. Defaults to `INFERENTIAL_VIEWS`.

    Returns:
        View name to the packages it lists.
    """
    if path.exists():
        return json.loads(path.read_text())
    members = fetch_views(names or INFERENTIAL_VIEWS)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(members, indent=2, sort_keys=True))
    return members


def load_usage(path: Path) -> dict[str, int]:
    """Read how many corpus archives load each package.

    Args:
        path: CSV with `package` and `count` columns, as softverse writes it.

    Returns:
        Package name to archive count.
    """
    with path.open() as handle:
        return {row["package"]: int(row["count"]) for row in csv.DictReader(handle)}


def select(
    members: dict[str, list[str]], usage: dict[str, int], minimum: int = 10
) -> list[Selection]:
    """Intersect task view membership with corpus usage.

    Args:
        members: View name to its packages.
        usage: Package name to corpus archive count.
        minimum: Archives a package must appear in to qualify.

    Returns:
        Qualifying packages, most-used first.
    """
    views: dict[str, list[str]] = {}
    for view in sorted(members):
        for package in members[view]:
            views.setdefault(package, []).append(view)

    selected = [
        Selection(package=package, views=names, usage=usage.get(package, 0))
        for package, names in views.items()
        if usage.get(package, 0) >= minimum and package not in NON_INFERENTIAL
    ]
    selected.sort(key=lambda s: (-s.usage, s.package))
    return selected


def write_selection(selected: list[Selection], path: Path) -> None:
    """Write the selected packages to CSV.

    Args:
        selected: Qualifying packages.
        path: Destination CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["package", "usage", "views"])
        for row in selected:
            writer.writerow([row.package, row.usage, ";".join(row.views)])


def read_selection(path: Path) -> list[Selection]:
    """Read a previously written selection.

    Args:
        path: Selection CSV.

    Returns:
        The selected packages, in file order.
    """
    with path.open() as handle:
        return [
            Selection(
                package=row["package"],
                views=row["views"].split(";") if row["views"] else [],
                usage=int(row["usage"]),
            )
            for row in csv.DictReader(handle)
        ]
