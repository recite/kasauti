"""How much a package is used, measured without reference to any one field.

The exposure count this study has run on until now is "replication archives in a
social-science corpus that load the package". It is the right measure for the
question the corpus answers -- *which published paper could this bug have reached*
-- and it is field-specific by construction. A package heavily used in ecology or
in industry looks unused through it.

Two external, scriptable measures fix that without displacing the corpus:

* **Reverse dependencies.** How many CRAN packages declare this one in `Depends`,
  `Imports`, or `LinkingTo`. Structural, exact, and derived from CRAN's own
  package database rather than from anyone's judgment. Strong dependencies are
  counted apart from `Suggests`, because a suggestion is a much weaker claim about
  whether code actually runs.
* **Downloads.** Requests to the RStudio CRAN mirror over a fixed window, from the
  cranlogs service. Noisy per package and inflated by continuous integration, but
  it is the only measure that sees users who never publish anything.

Both are cached and checked in. A frame that shifts because CRAN gained a package
last Tuesday is not a frame, and every count here has to be reproducible from the
repository rather than from the network.
"""

from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests

CRANLOGS = "https://cranlogs.r-pkg.org/downloads/total"

USER_AGENT = "kasauti/0.1 (research; differential testing of statistical software)"

#: Packages per cranlogs request. The service documents no limit; this keeps the
#: URL well inside anything a server would object to and makes a failure affect
#: one chunk rather than the whole frame.
CHUNK = 50

#: Dependency fields that mean the code is loaded when the dependant runs.
#: `Enhances` and `Suggests` do not, and are counted separately.
STRONG = ("Depends", "Imports", "LinkingTo")

#: Reads CRAN's package database and prints one row per (package, field, target).
#: Run through R rather than reimplemented because `tools::CRAN_package_db()` is
#: the canonical accessor and parsing `PACKAGES` by hand would be a second, worse
#: copy of it.
#: Written without a single backslash. The version-constraint suffix is stripped
#: with a character class rather than an escaped parenthesis, because the string
#: crosses Python, a shell argument, and R's parser, and each of those has its own
#: opinion about backslashes -- the first attempt died on `'\\(' is an unrecognized
#: escape` before reaching CRAN at all.
REVERSE_SCRIPT = """
db <- tools::CRAN_package_db()
fields <- c("Depends", "Imports", "LinkingTo", "Suggests")
out <- character()
for (field in fields) {
  values <- db[[field]]
  for (i in seq_along(values)) {
    if (is.na(values[[i]]) || !nzchar(values[[i]])) next
    parts <- strsplit(values[[i]], ",")[[1]]
    names <- trimws(sub("[(].*", "", parts))
    names <- names[nzchar(names) & names != "R"]
    for (name in unique(names)) out <- c(out, paste(field, name))
  }
}
needs <- db$NeedsCompilation
for (i in seq_along(needs)) {
  flag <- if (!is.na(needs[[i]]) && needs[[i]] == "yes") "yes" else "no"
  out <- c(out, paste("NeedsCompilation", db$Package[[i]], flag))
}
writeLines(out)
"""


@dataclass
class Usage:
    """What is known about how much one package is used.

    Attributes:
        package: Package name.
        corpus: Replication archives in the social-science corpus that load it.
        strong: CRAN packages declaring it in Depends, Imports, or LinkingTo.
        suggests: CRAN packages declaring it in Suggests.
        downloads: Downloads over the recorded window.
        compiled: Whether it ships code needing compilation -- the strongest
            available predictor of whether an archived release will build.
    """

    package: str
    corpus: int = 0
    strong: int = 0
    suggests: int = 0
    downloads: int = 0
    compiled: bool = False


def fetch_reverse_dependencies(timeout: int = 600) -> dict[str, dict[str, int]]:
    """Count reverse dependencies for every package on CRAN.

    Args:
        timeout: Seconds before giving up on R.

    Returns:
        Package name to a `{"strong": n, "suggests": n}` pair.

    Raises:
        RuntimeError: If R could not produce the database.
    """
    proc = subprocess.run(  # noqa: S603
        ["Rscript", "--vanilla", "-e", REVERSE_SCRIPT],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if not proc.stdout.strip():
        raise RuntimeError(f"CRAN_package_db() produced nothing\n{proc.stderr[-2000:]}")

    counts: dict[str, dict[str, int]] = {}
    for line in proc.stdout.splitlines():
        field, _, rest = line.partition(" ")
        if not rest:
            continue
        if field == "NeedsCompilation":
            name, _, flag = rest.partition(" ")
            counts.setdefault(name, {"strong": 0, "suggests": 0})["compiled"] = int(
                flag == "yes"
            )
            continue
        entry = counts.setdefault(rest, {"strong": 0, "suggests": 0})
        entry["strong" if field in STRONG else "suggests"] += 1
    return counts


def fetch_downloads(packages: list[str], window: str, timeout: int = 120) -> dict:
    """Fetch total downloads for each package over a window.

    Args:
        packages: Package names.
        window: A cranlogs period, such as `2024-01-01:2024-12-31`.
        timeout: Seconds per request.

    Returns:
        Package name to download count. A package the service does not know is
        absent rather than zero, because those are different facts.
    """
    totals: dict[str, int] = {}
    for start in range(0, len(packages), CHUNK):
        chunk = packages[start : start + CHUNK]
        response = requests.get(
            f"{CRANLOGS}/{window}/{','.join(chunk)}",
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        for row in response.json():
            if row.get("package"):
                totals[row["package"]] = int(row.get("downloads") or 0)
    return totals


def load_usage(
    packages: list[str], window: str, cache: Path, refresh: bool = False
) -> dict[str, Usage]:
    """Assemble the field-neutral usage table, fetching once.

    Args:
        packages: Packages to measure.
        window: cranlogs period for the download count.
        cache: JSON file the raw measurements are cached in.
        refresh: Re-fetch even when the cache exists.

    Returns:
        Package name to its usage.
    """
    if cache.exists() and not refresh:
        payload = json.loads(cache.read_text())
    else:
        payload = {
            "window": window,
            "reverse": fetch_reverse_dependencies(),
            "downloads": fetch_downloads(packages, window),
        }
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload, indent=2, sort_keys=True))

    reverse = payload["reverse"]
    downloads = payload["downloads"]
    return {
        package: Usage(
            package=package,
            strong=reverse.get(package, {}).get("strong", 0),
            suggests=reverse.get(package, {}).get("suggests", 0),
            downloads=downloads.get(package, 0),
            compiled=bool(reverse.get(package, {}).get("compiled", 0)),
        )
        for package in packages
    }


USAGE_COLUMNS = ["package", "corpus", "strong", "suggests", "downloads", "compiled"]


def write_usage(rows: list[Usage], path: Path) -> None:
    """Write the usage table to CSV.

    Args:
        rows: One entry per package.
        path: Destination CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=USAGE_COLUMNS)
        writer.writeheader()
        for row in sorted(rows, key=lambda u: (-u.corpus, u.package)):
            writer.writerow(
                {
                    "package": row.package,
                    "corpus": row.corpus,
                    "strong": row.strong,
                    "suggests": row.suggests,
                    "downloads": row.downloads,
                    "compiled": int(row.compiled),
                }
            )


def read_usage(path: Path) -> dict[str, Usage]:
    """Read a previously written usage table.

    Args:
        path: Usage CSV.

    Returns:
        Package name to its usage.
    """
    with path.open() as handle:
        return {
            row["package"]: Usage(
                package=row["package"],
                corpus=int(row["corpus"]),
                strong=int(row["strong"]),
                suggests=int(row["suggests"]),
                downloads=int(row["downloads"]),
                compiled=bool(int(row.get("compiled", 0))),
            )
            for row in csv.DictReader(handle)
        }
