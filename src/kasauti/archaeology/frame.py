"""Construct the sampling frame from what replication scripts actually call.

Both halves of this project need a defensible answer to "why these procedures and
these packages, and not others". Guessing what might break is not one. The frame
here is derived from usage: every function call in a corpus of published
replication archives, restricted to functions that produce estimates, standard
errors, or test statistics, and ranked by the number of distinct scripts that call
them.

That ranking is the frame for both tracks. It picks which procedures are worth
cross-implementation testing, and it picks which packages are worth mining for
result-changing bug fixes -- weighted by exposure in the published literature
rather than by general popularity.
"""

from __future__ import annotations

import csv
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from kasauti.archaeology.calls import CallSite

#: Packages whose functions produce numbers that end up in a results table. The
#: corpus's single most-used package is ggplot2, which is irrelevant here: a bug
#: in a plotting library does not change a reported coefficient. This list is the
#: one deliberately curated input to the frame, and it is deliberately visible.
INFERENTIAL_PACKAGES = [
    # Core modelling, shipped with R
    "stats",
    "MASS",
    "survival",
    "nlme",
    "mgcv",
    # Covariance and inference
    "sandwich",
    "lmtest",
    "car",
    "clubSandwich",
    "multiwayvcov",
    "estimatr",
    "survey",
    # Panel, IV, econometrics
    "plm",
    "AER",
    "fixest",
    "ivreg",
    # Hierarchical and mixed
    "lme4",
    # Matching, design, causal
    "Matching",
    "MatchIt",
    "rdrobust",
    "rddtools",
    "mediation",
    # Distributions and specialised GLMs
    "betareg",
    "pscl",
    "VGAM",
    "ordinal",
    "quantreg",
    "robustbase",
    "metafor",
    "logistf",
]

#: Functions that are exported by an inferential package but do not themselves
#: compute an estimate -- printing, coercion, extraction, family constructors,
#: data plumbing. Excluded so the frame ranks procedures rather than scaffolding.
NON_COMPUTING = {
    # extraction and display
    "print",
    "summary",
    "plot",
    "format",
    "coef",
    "coefficients",
    "residuals",
    "resid",
    "fitted",
    "fitted.values",
    "predict",
    "vcov",
    "confint",
    "nobs",
    "logLik",
    "AIC",
    "BIC",
    "deviance",
    "df.residual",
    "sigma",
    "tidy",
    "glance",
    "etable",
    "screenreg",
    "texreg",
    "stargazer",
    # model plumbing
    "model.matrix",
    "model.frame",
    "terms",
    "formula",
    "as.formula",
    "update",
    "offset",
    "contrasts",
    "relevel",
    "reformulate",
    "na.omit",
    "na.exclude",
    "complete.cases",
    "setNames",
    "napredict",
    "naresid",
    # GLM family constructors: arguments to a fit, not fits
    "binomial",
    "poisson",
    "gaussian",
    "Gamma",
    "quasibinomial",
    "quasipoisson",
    "inverse.gaussian",
    "make.link",
    # generic data manipulation that happens to live in an inferential namespace
    "aggregate",
    "sapply",
    "lapply",
    "apply",
    "setdiff",
    "union",
    "intersect",
    "reshape",
    "addmargins",
    "ftable",
    "xtabs",
    "expand.grid",
    "toupper",
}

#: Names exported by base R's `stats` or `MASS` that the tidyverse re-exports and
#: routinely masks. A bare `filter()` in a script that loads dplyr is dplyr's
#: filter, not `stats::filter`, and attributing it to `stats` would put a data
#: verb at the top of a frame of statistical procedures. These are counted only
#: when the call is namespace-qualified, which is conservative: some genuine
#: `stats::filter` uses written bare are lost, but nothing is overcounted.
SHADOWED = {
    "filter",
    "select",
    "lag",
    "lead",
    "slice",
    "rename",
    "mutate",
    "summarise",
    "summarize",
    "arrange",
    "group_by",
    "count",
    "first",
    "last",
    "between",
    "combine",
    "collapse",
    "matches",
    "starts_with",
    "ends_with",
    "contains",
    "recode",
    "near",
    "desc",
    "n",
    "f",
    "t",
    "c",
    "df",
    "D",
    "I",
}


#: Python modules whose functions produce numbers that end up in a results table.
#: A call is attributed to the first entry its resolved module path starts with,
#: so `statsmodels.api` and `statsmodels.formula.api` both land on `statsmodels`.
#: `sklearn` is included because it is used for inference in practice even though
#: it is a prediction library -- the `logit_separation` case is about exactly that
#: mismatch.
INFERENTIAL_PYTHON_MODULES = [
    "statsmodels",
    "scipy.stats",
    "scipy.optimize",
    "linearmodels",
    "sklearn.linear_model",
    "sklearn.metrics",
    "lifelines",
    "pymer4",
    "pyfixest",
    "arch",
    "pingouin",
    "numpy.random",
]


def attribute_python(module: str) -> str | None:
    """Map a resolved module path to an inferential package.

    Args:
        module: Dotted module path from the call site's `qualifier`.

    Returns:
        The matching entry of `INFERENTIAL_PYTHON_MODULES`, or None.
    """
    if not module:
        return None
    for candidate in INFERENTIAL_PYTHON_MODULES:
        if module == candidate or module.startswith(candidate + "."):
            return candidate
    return None


@dataclass
class FrameRow:
    """One procedure in the sampling frame.

    Attributes:
        fname: Function name as called.
        packages: Inferential packages exporting this name. More than one means
            the attribution is ambiguous from the call site alone.
        language: `R` or `Python`.
        scripts: Distinct scripts calling it.
        calls: Total call sites.
        share: `scripts` as a share of all parsed scripts in that language.
    """

    fname: str
    packages: list[str]
    language: str
    scripts: int
    calls: int
    share: float = 0.0

    @property
    def ambiguous(self) -> bool:
        """Whether the name is exported by more than one inferential package.

        Returns:
            True when attribution needs the script's imports to resolve.
        """
        return len(self.packages) > 1


def r_namespace_exports(packages: list[str]) -> dict[str, list[str]]:
    """Ask R which functions each package exports.

    Uses the installed namespaces rather than a hand-written list, so the mapping
    is authoritative for the versions actually present and cannot drift.

    Args:
        packages: Package names to query.

    Returns:
        Function name to the packages exporting it. Packages that are not
        installed are silently skipped; call `missing_packages` to see which.

    Raises:
        RuntimeError: If R itself fails to run.
    """
    listing = ", ".join(f'"{p}"' for p in packages)
    script = (
        f"pkgs <- c({listing}); out <- list();"
        "for (p in pkgs) { if (requireNamespace(p, quietly=TRUE)) {"
        "  e <- tryCatch(getNamespaceExports(p), error=function(e) character());"
        "  out[[p]] <- e } };"
        "cat(jsonlite::toJSON(out))"
    )

    proc = subprocess.run(  # noqa: S603
        ["Rscript", "--vanilla", "-e", script],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"failed to query R namespaces:\n{proc.stderr[-1500:]}")

    by_package = json.loads(proc.stdout)
    exports: dict[str, list[str]] = defaultdict(list)
    for package, functions in by_package.items():
        for function in functions:
            exports[function].append(package)
    return dict(exports)


def missing_packages(packages: list[str]) -> list[str]:
    """Report which of the requested packages are not installed.

    Coverage matters: a function exported only by an uninstalled package cannot be
    attributed, and would silently drop out of the frame.

    Args:
        packages: Package names to check.

    Returns:
        The subset that is not installed.
    """
    listing = ", ".join(f'"{p}"' for p in packages)
    script = (
        f"pkgs <- c({listing}); "
        "cat(paste(pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)], "
        "collapse=' '))"
    )
    proc = subprocess.run(  # noqa: S603
        ["Rscript", "--vanilla", "-e", script],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.split()


@dataclass
class Frame:
    """The assembled sampling frame.

    Attributes:
        rows: Procedures ranked by the number of scripts calling them.
        scripts_parsed: Parsed script counts by language, the frame denominator.
        uninstalled: Inferential packages that could not be introspected.
        unattributed_top: The most-called functions that no inferential package
            claims, kept as a visible check that the curation is not dropping
            something important.
        shadow_dropped: Script-function pairs discarded because the name is
            routinely masked by the tidyverse and the call was not qualified.
    """

    rows: list[FrameRow] = field(default_factory=list)
    scripts_parsed: dict[str, int] = field(default_factory=dict)
    uninstalled: list[str] = field(default_factory=list)
    unattributed_top: list[tuple[str, int]] = field(default_factory=list)
    shadow_dropped: int = 0


def build_frame(
    call_sites: list[CallSite],
    scripts_parsed: dict[str, int],
    packages: list[str] | None = None,
) -> Frame:
    """Rank called procedures by how many scripts use them.

    Counts distinct scripts rather than total calls: a loop that calls `lm` two
    hundred times is one exposed analysis, not two hundred.

    Args:
        call_sites: Extracted call sites across the corpus.
        scripts_parsed: Parsed script count per language, for the share
            denominator.
        packages: Inferential packages to attribute against. Defaults to
            `INFERENTIAL_PACKAGES`.

    Returns:
        The assembled frame.
    """
    packages = packages or INFERENTIAL_PACKAGES
    exports = r_namespace_exports(packages)

    # The two languages are attributed by different mechanisms and must not be
    # mixed: matching a Python call named `index` against R's export list would
    # attribute a pandas method to `plm`.
    scripts: dict[tuple[str, str, tuple[str, ...]], set[str]] = defaultdict(set)
    calls: Counter[tuple[str, str, tuple[str, ...]]] = Counter()
    qualified: dict[tuple[str, str], set[str]] = defaultdict(set)

    for site in call_sites:
        if site.language == "R":
            owners = tuple(sorted(exports.get(site.fname, [])))
            if site.qualifier:
                qualified[(site.fname, site.qualifier)].add(site.path)
        else:
            owner = attribute_python(site.qualifier)
            owners = (owner,) if owner else ()
        key = (site.language, site.fname, owners)
        scripts[key].add(site.path)
        calls[key] += site.n

    rows, unattributed = [], Counter()
    shadow_dropped = 0
    for (language, fname, owners), paths in scripts.items():
        if not owners or fname in NON_COMPUTING:
            if fname not in NON_COMPUTING:
                unattributed[fname] += len(paths)
            continue
        if language == "R" and fname in SHADOWED:
            # Count a masked name only where the call named one of the packages
            # that actually exports it; any-qualifier matching would let
            # dplyr::select be counted as MASS::select.
            surviving: set[str] = set()
            for owner in owners:
                surviving |= qualified.get((fname, owner), set())
            shadow_dropped += len(paths) - len(surviving)
            if not surviving:
                continue
            paths = surviving
        denominator = scripts_parsed.get(language, 0)
        rows.append(
            FrameRow(
                fname=fname,
                packages=list(owners),
                language=language,
                scripts=len(paths),
                calls=calls[(language, fname, owners)],
                share=len(paths) / denominator if denominator else 0.0,
            )
        )

    rows.sort(key=lambda r: (-r.scripts, r.fname))
    return Frame(
        rows=rows,
        scripts_parsed=scripts_parsed,
        uninstalled=missing_packages(packages),
        unattributed_top=unattributed.most_common(40),
        shadow_dropped=shadow_dropped,
    )


def write_frame(frame: Frame, path: Path) -> None:
    """Write the frame to CSV.

    Args:
        frame: The assembled frame.
        path: Destination CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["rank", "language", "fname", "packages", "scripts", "share", "calls"]
        )
        for rank, row in enumerate(frame.rows, start=1):
            writer.writerow(
                [
                    rank,
                    row.language,
                    row.fname,
                    ";".join(row.packages),
                    row.scripts,
                    f"{row.share:.4f}",
                    row.calls,
                ]
            )


def package_exposure(frame: Frame) -> list[tuple[str, int, int]]:
    """Aggregate the frame to package level.

    A package's exposure is the number of distinct scripts calling any of its
    inferential functions. Ambiguous names count for every package exporting
    them, so these are upper bounds and are labelled as such in the report.

    Args:
        frame: The assembled frame.

    Returns:
        `(package, scripts, distinct_functions)` sorted by scripts descending.
    """
    scripts: dict[str, int] = Counter()
    functions: dict[str, set[str]] = defaultdict(set)
    for row in frame.rows:
        for package in row.packages:
            scripts[package] += row.scripts
            functions[package].add(row.fname)
    return sorted(
        ((p, n, len(functions[p])) for p, n in scripts.items()),
        key=lambda t: -t[1],
    )


def render_report(frame: Frame, extraction: dict[str, dict]) -> str:
    """Render the sampling frame as markdown.

    Args:
        frame: The assembled frame.
        extraction: Per-language extraction coverage from `calls`.

    Returns:
        The markdown report.
    """
    out = [
        "# Sampling frame",
        "",
        "Which statistical procedures are worth testing, and which packages are",
        "worth mining for result-changing bugs, derived from what published",
        "replication archives actually call rather than from what seemed likely to",
        "break.",
        "",
        "## Corpus and coverage",
        "",
        "| language | scripts | parsed | failed | parse rate | call sites |",
        "|---|---|---|---|---|---|",
    ]
    for language, stats in sorted(extraction.items()):
        out.append(
            f"| {language} | {stats['files_seen']} | {stats['files_parsed']} | "
            f"{stats['files_failed']} | {stats['parse_rate']:.1%} | "
            f"{stats['call_sites']} |"
        )

    out += [
        "",
        "Parsing uses each language's own parser -- R's `getParseData`, Python's",
        "`ast` -- not regular expressions, so a name in a string or a comment is",
        "not counted as a call. Scripts that fail to parse are counted, not",
        "dropped; that rate is a property of the archives.",
        "",
        "## How a call is attributed to a package",
        "",
        "**R.** A name is attributed to every installed package in the curated",
        "list that exports it, established by `getNamespaceExports` rather than by",
        "a hand-written table. Names the tidyverse routinely masks -- `filter`,",
        "`select`, `lag`, `slice` -- count only when written `pkg::name`, since a",
        "bare `filter()` in a script that loads dplyr is dplyr's. That rule",
        f"discarded {frame.shadow_dropped} script-function pairs, which is the",
        "conservative direction: genuine bare `stats::filter` uses are lost, but",
        "nothing is overcounted.",
        "",
        "**Python.** Callees are resolved through each file's own import",
        "statements, so `sm.OLS` counts as statsmodels only because of `import",
        "statsmodels.api as sm` above it. A callee that does not trace to an",
        "import -- a method on a local object -- is left unattributed. Without",
        "this, common method names like `index` and `time` are indistinguishable",
        "from package functions.",
        "",
        "Plotting, printing, extraction, and family constructors are excluded: a",
        "bug in `ggplot2`, the corpus's most-used package overall, does not change",
        "a reported coefficient.",
        "",
    ]
    if frame.uninstalled:
        out += [
            f"Not introspectable (not installed, so unattributable): "
            f"`{'`, `'.join(frame.uninstalled)}`.",
            "",
        ]

    for language in ("R", "Python"):
        rows = [r for r in frame.rows if r.language == language][:30]
        if not rows:
            continue
        denominator = frame.scripts_parsed.get(language, 0)
        out += [
            f"## Top procedures, {language} (n = {denominator} parsed scripts)",
            "",
            "| # | function | package | scripts | share |",
            "|---|---|---|---|---|",
        ]
        for rank, row in enumerate(rows, start=1):
            out.append(
                f"| {rank} | `{row.fname}` | {';'.join(row.packages)} | "
                f"{row.scripts} | {row.share:.1%} |"
            )
        out.append("")

    out += [
        "## Package exposure",
        "",
        "Distinct scripts calling any inferential function of each package. Names",
        "exported by more than one package count for each, so these are upper",
        "bounds.",
        "",
        "| package | script-calls | distinct functions |",
        "|---|---|---|",
    ]
    for package, scripts, functions in package_exposure(frame)[:25]:
        out.append(f"| `{package}` | {scripts} | {functions} |")

    out += [
        "",
        "## What the frame says",
        "",
        "Random number generation dominates both languages: `rnorm` is the most",
        "called procedure in R and `numpy.random` accounts for the whole Python",
        "top ten. Any change to a generator or to how a seed is consumed moves",
        "every simulation-based result in the corpus, which makes RNG the single",
        "highest-exposure surface for changelog archaeology -- R 3.6.0's change to",
        "`sample()` is the canonical example.",
        "",
        "After simulation, the frame is concentrated: `lm` in 6.9% of R scripts,",
        "then `glm`, then the robust-covariance family (`coeftest`, `vcovHC`,",
        "`feols`, `lm_robust`) which is exactly where the cross-implementation",
        "suite already finds a seven-fold disagreement between R and Python.",
        "",
    ]
    return "\n".join(out) + "\n"
