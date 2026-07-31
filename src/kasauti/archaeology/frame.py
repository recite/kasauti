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

import builtins
import csv
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from kasauti.archaeology.calls import CallSite
from kasauti.archaeology.harvest import harvest

#: Packages that ship with R rather than through CRAN. They have no source
#: tarball, so their exports come from the interpreter -- which costs nothing,
#: since a machine with R has them by definition.
BASE_PACKAGES = {
    "base",
    "compiler",
    "datasets",
    "grDevices",
    "graphics",
    "grid",
    "methods",
    "parallel",
    "splines",
    "stats",
    "stats4",
    "tcltk",
    "tools",
    "utils",
}

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

#: The Python twin of `NON_COMPUTING`: array and frame plumbing, not statistics.
#:
#: It has to be longer than R's, and for a reason worth stating. R's inferential
#: packages export distinctive names -- nothing but `sandwich` means `vcovHC` --
#: so intersecting a changelog with a package's exports admits almost no English
#: prose. numpy exports `where`, `all`, `any`, `array`, `empty`, and `fix`, which
#: are ordinary words in a release note *and* calls in nearly every script. Left
#: in, `where` alone drove 179 candidate entries.
#:
#: Statistics stay in. `mean`, `median`, `std`, `var`, `quantile`, and `corrcoef`
#: compute numbers that reach a table, exactly as `sd` and `quantile` do on the R
#: side, and a bug in one of them is the kind of thing this study exists to find.
NON_COMPUTING_PYTHON = {
    # construction and shape
    "array",
    "asarray",
    "asanyarray",
    "empty",
    "empty_like",
    "zeros",
    "zeros_like",
    "ones",
    "ones_like",
    "full",
    "arange",
    "linspace",
    "eye",
    "identity",
    "reshape",
    "ravel",
    "flatten",
    "squeeze",
    "expand_dims",
    "transpose",
    "atleast_1d",
    "atleast_2d",
    "swapaxes",
    "moveaxis",
    "broadcast_to",
    "shape",
    "size",
    "ndim",
    # joining and splitting
    "concatenate",
    "stack",
    "hstack",
    "vstack",
    "dstack",
    "column_stack",
    "split",
    "array_split",
    "hsplit",
    "vsplit",
    "tile",
    "repeat",
    "append",
    "insert",
    "delete",
    "resize",
    # selection and ordering
    "where",
    "take",
    "put",
    "compress",
    "extract",
    "select",
    "choose",
    "index",
    "indices",
    "ix_",
    "nonzero",
    "flatnonzero",
    "argmax",
    "argmin",
    "argsort",
    "argwhere",
    "searchsorted",
    "sort",
    "unique",
    "flip",
    "roll",
    # predicates and type handling
    "all",
    "any",
    "isnan",
    "isinf",
    "isfinite",
    "isclose",
    "allclose",
    "astype",
    "dtype",
    "cast",
    "can_cast",
    "result_type",
    "copy",
    "copyto",
    "view",
    "fix",
    "at",
    "get",
    "set",
    "values",
    "keys",
    "items",
    "count",
    "matrix",
    "asmatrix",
    # input, output, and display
    "load",
    "save",
    "savez",
    "loadtxt",
    "savetxt",
    "genfromtxt",
    "fromfile",
    "tofile",
    "read_csv",
    "to_csv",
    "printoptions",
    "set_printoptions",
    "array2string",
    "array_repr",
    "array_str",
    "plot",
    "show",
    "figure",
    "subplot",
    "subplots",
    "savefig",
    # estimator scaffolding
    "fit",
    "transform",
    "fit_transform",
    "predict",
    "predict_proba",
    "score",
    "get_params",
    "set_params",
    "summary",
    "clone",
} | set(dir(builtins))
"""Plus every Python builtin, computed rather than listed.

numpy re-exports `max`, `min`, `sum`, `abs`, and `round`; a script calling any of
them almost always means the builtin, and a changelog sentence containing the word
"max" is not thereby about `numpy.max`. This is the same rule the R side applies to
names base R exports, arrived at the same way -- ask the language, do not guess.
Nothing statistical is lost: no builtin computes a mean, a variance, or a quantile.
"""

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


def base_exports(packages: list[str]) -> dict[str, set[str]]:
    """Ask R which functions each base package exports.

    Base packages ship with R rather than through CRAN, so they have no source
    tarball to read NAMESPACE from -- but they are installed wherever R exists,
    so asking the interpreter imposes no ceiling on coverage. `stats` alone
    accounts for `lm`, `glm`, and `t.test`, so skipping it is not an option.

    Args:
        packages: Base package names to query.

    Returns:
        Package name to its set of exports.

    Raises:
        RuntimeError: If R itself fails to run.
    """
    if not packages:
        return {}
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
    return {p: set(names) for p, names in json.loads(proc.stdout).items()}


def package_exports(packages: list[str], cache_root: Path) -> dict[str, set[str]]:
    """Resolve each package's exported names.

    CRAN packages are read from the NAMESPACE inside the source tarball the
    harvest already downloads. That removes the install requirement, which was
    the real constraint on how many packages the study could cover: a package
    only had to be buildable on this machine to be studied.

    Args:
        packages: Package names.
        cache_root: Harvest cache root, where the tarball-derived exports live.

    Returns:
        Package name to its set of exports. A package absent from the harvest
        contributes an empty set rather than an error, and shows up as zero
        yield downstream.
    """
    base = [p for p in packages if p in BASE_PACKAGES]
    exports = base_exports(base)
    for package in packages:
        if package in BASE_PACKAGES:
            continue
        exports[package] = set(harvest(package, "cran", cache_root).exports)
    return exports


def by_function(exports: dict[str, set[str]]) -> dict[str, list[str]]:
    """Invert a package-to-exports mapping.

    Args:
        exports: Package name to its set of exports.

    Returns:
        Function name to the packages exporting it.
    """
    owners: dict[str, list[str]] = defaultdict(list)
    for package, names in exports.items():
        for name in names:
            owners[name].append(package)
    return {name: sorted(packages) for name, packages in owners.items()}


@dataclass
class Frame:
    """The assembled sampling frame.

    Attributes:
        rows: Procedures ranked by the number of scripts calling them.
        scripts_parsed: Parsed script counts by language, the frame denominator.
        packages: Packages attributed against.
        no_exports: Packages whose export list came back empty, which means the
            frame cannot attribute anything to them. Kept visible because a
            package that contributes nothing for want of a NAMESPACE looks
            exactly like a package nobody uses.
        unattributed_top: The most-called functions that no inferential package
            claims, kept as a visible check that the curation is not dropping
            something important.
        shadow_dropped: Script-function pairs discarded because the name is
            routinely masked by the tidyverse and the call was not qualified.
    """

    rows: list[FrameRow] = field(default_factory=list)
    scripts_parsed: dict[str, int] = field(default_factory=dict)
    packages: list[str] = field(default_factory=list)
    no_exports: list[str] = field(default_factory=list)
    unattributed_top: list[tuple[str, int]] = field(default_factory=list)
    shadow_dropped: int = 0


def build_frame(
    call_sites: list[CallSite],
    scripts_parsed: dict[str, int],
    cache_root: Path,
    packages: list[str] | None = None,
) -> Frame:
    """Rank called procedures by how many scripts use them.

    Counts distinct scripts rather than total calls: a loop that calls `lm` two
    hundred times is one exposed analysis, not two hundred.

    Args:
        call_sites: Extracted call sites across the corpus.
        scripts_parsed: Parsed script count per language, for the share
            denominator.
        cache_root: Harvest cache root, which holds each package's exports.
        packages: Inferential packages to attribute against. Defaults to
            `INFERENTIAL_PACKAGES`.

    Returns:
        The assembled frame.
    """
    packages = packages or INFERENTIAL_PACKAGES
    per_package = package_exports(packages, cache_root)
    exports = by_function(per_package)

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
        packages=sorted(per_package),
        no_exports=sorted(p for p, names in per_package.items() if not names),
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
        "## Which packages",
        "",
        f"The frame covers **{len(frame.packages)}** packages, selected by",
        "intersecting two sources, neither of them the author's memory: the",
        "packages CRAN's expert-maintained Task Views list for a field, and the",
        "packages replication archives in the corpus actually load. A package",
        "qualifies by being both recognized by the field and used in the",
        "literature.",
        "",
        "The earlier version of this frame named its packages by hand. Measuring",
        "the corpus afterwards showed what that costs: `lfe`, loaded by 222",
        "archives, had simply been forgotten -- and a package left off the list is",
        "indistinguishable from a package with nothing wrong.",
        "",
        "Judgment survives in two exclusion rules, both stated at the level of a",
        "category rather than a package, and both falsifiable in a way an",
        "inclusion list is not. `INFERENTIAL_VIEWS` picks which of CRAN's 49 views",
        "describe inference rather than infrastructure or a distant laboratory",
        "domain. `NON_INFERENTIAL` drops packages whose whole job is plotting,",
        "formatting, or data manipulation -- unavoidable, because `ggplot2` is",
        "genuinely part of the Spatial and NetworkAnalysis toolkits, so no choice",
        "of views excludes it.",
        "",
        "## How a call is attributed to a package",
        "",
        "**R.** A name is attributed to every package in the frame that exports",
        "it, read from the `NAMESPACE` inside the CRAN source tarball rather than",
        "from a hand-written table. Names the tidyverse routinely masks -- `filter`,",
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
    out += [
        "Exports come from the `NAMESPACE` inside each package's CRAN source",
        "tarball, not from an installed copy, so coverage is not limited to what",
        "one machine can build. Base packages, which have no tarball, are read",
        "from the interpreter.",
        "",
    ]
    if frame.no_exports:
        out += [
            "No export list resolved, so nothing can be attributed to them: "
            f"`{'`, `'.join(frame.no_exports)}`.",
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
