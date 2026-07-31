"""Collect version histories and changelog text for the packages in the frame.

Two things are needed per package: a dated list of every release, which gives the
timeline a bug can be located on, and the changelog text, which is where the
package admits to having been wrong.

Coverage is uneven and the unevenness matters. `survival` ships a meticulous
`inst/NEWS.Rd` with an entry per fix; several equally-used packages expose almost
nothing. Raw bug counts across packages therefore measure candor at least as much
as they measure bugginess, so every harvest records how much text it found and
that figure travels with the counts downstream.
"""

from __future__ import annotations

import json
import re
import subprocess
import tarfile
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

import requests

CRANDB = "https://crandb.r-pkg.org"
CRAN_SRC = "https://cran.r-project.org/src/contrib"
PYPI = "https://pypi.org/pypi"

#: Filenames inside an R source tarball that may hold the changelog, best first.
#: NEWS files are cumulative, so the newest tarball carries the whole history and
#: one download per package is enough.
R_NEWS_CANDIDATES = [
    "inst/NEWS.Rd",
    "inst/NEWS.md",
    "inst/NEWS",
    "NEWS.md",
    "NEWS",
    "ChangeLog",
    "inst/ChangeLog",
]

#: `export(a, b)` and its siblings, whose contents are a comma-separated name
#: list. `exportPattern` is deliberately absent: it names a regex rather than a
#: set, and is resolved separately against the package's own sources.
NAMESPACE_EXPORT = re.compile(r"\bexport(?:Classes|Methods)?\s*\(")
#: `exportPattern("^[^.]")` -- a regex standing in for a name list, common in
#: older packages. Unresolved it would leave those packages with no exports at
#: all, and so no candidates, which reads as "clean" rather than "unreadable".
NAMESPACE_PATTERN = re.compile(r"\bexportPattern\s*\(\s*([\"'])(.*?)\1\s*\)")
#: `S3method(generic, class)`, registering `generic.class`. The composite is what
#: a changelog names ("vcovHC.mlm was wrong"); the bare generic is not added,
#: since `print` belongs to base R however many methods a package writes for it.
#: The generic is quoted when it is an operator -- `S3method("[", escalc)` -- so
#: the token is read up to the comma rather than assumed to be a word.
NAMESPACE_S3 = re.compile(r"\bS3method\s*\(")
#: A top-level function definition in an R source file, used to enumerate the
#: names an `exportPattern` regex is matched against. The captured group is the
#: whole left-hand side, because R lets one definition name several functions:
#: metafor defines its central estimator as `rma <- rma.uni <- function(...)`,
#: and matching only the innermost name would lose `rma` entirely.
R_DEFINITION = re.compile(
    r"^\s*((?:[\"'`]?[A-Za-z.][\w.]*[\"'`]?\s*(?:<-|=)\s*)+)function\s*\(",
    re.MULTILINE,
)
USER_AGENT = "kasauti/0.1 (research; differential testing of statistical software)"

GITHUB_API = "https://api.github.com/repos"
GITHUB_RAW = "https://raw.githubusercontent.com"

#: Python projects keep release notes in the repository rather than the sdist,
#: so the changelog and the version timeline come from different places: PyPI
#: dates the releases, GitHub explains them. Each entry is
#: `(repo, directory, extension)`.
PYTHON_NOTES = {
    "statsmodels": ("statsmodels/statsmodels", "docs/source/release", ".rst"),
    "scipy": ("scipy/scipy", "doc/source/release", ".rst"),
    "scikit-learn": ("scikit-learn/scikit-learn", "doc/whats_new", ".rst"),
    "numpy": ("numpy/numpy", "doc/source/release", ".rst"),
}


@dataclass
class Release:
    """One released version of a package.

    Attributes:
        version: Version string as the ecosystem writes it.
        released: Release date, or None when the registry has none. Early CRAN
            releases predate systematic date recording.
    """

    version: str
    released: date | None

    def to_dict(self) -> dict:
        """Return a JSON-serializable form.

        Returns:
            The release with the date as an ISO string.
        """
        return {
            "version": self.version,
            "released": self.released.isoformat() if self.released else None,
        }


@dataclass
class Harvest:
    """Everything collected for one package.

    Attributes:
        package: Package name.
        ecosystem: `cran` or `pypi`.
        releases: Dated release history, oldest first.
        news_text: Raw changelog text.
        news_source: Where the text came from, for the audit trail.
        exports: Names the package exports -- declared in NAMESPACE for CRAN,
            introspected from the imported modules for PyPI, which has no
            equivalent file.
        errors: Non-fatal problems encountered.
    """

    package: str
    ecosystem: str
    releases: list[Release] = field(default_factory=list)
    news_text: str = ""
    news_source: str = ""
    exports: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def dated_releases(self) -> list[Release]:
        """Releases whose date is known.

        Returns:
            The subset with a non-null date.
        """
        return [r for r in self.releases if r.released]

    @property
    def news_bytes(self) -> int:
        """Size of the collected changelog.

        Returns:
            Length of `news_text` in characters. Zero means the package
            documents nothing machine-readably, which is a finding about the
            package rather than a gap in the harvest.
        """
        return len(self.news_text)

    def to_dict(self) -> dict:
        """Return a JSON-serializable form.

        Returns:
            The harvest as a plain dict.
        """
        payload = asdict(self)
        payload["releases"] = [r.to_dict() for r in self.releases]
        return payload


def _get(url: str, timeout: int = 60, **kwargs) -> requests.Response:
    """Fetch a URL with a descriptive user agent.

    Args:
        url: URL to fetch.
        timeout: Seconds before giving up.
        **kwargs: Passed through to `requests.get`.

    Returns:
        The response.
    """
    return requests.get(
        url, timeout=timeout, headers={"User-Agent": USER_AGENT}, **kwargs
    )


def _parse_cran_date(raw: str | None) -> date | None:
    """Parse the several date formats CRAN metadata uses.

    Args:
        raw: Raw date string, or None.

    Returns:
        The parsed date, or None if absent or unrecognized.
    """
    if not raw:
        return None
    text = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[: len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    # "Mon Jul 19 23:28:55 2004; zeileis"
    match = re.search(r"\b(\w{3})\s+(\d{1,2})\s+[\d:]+\s+(\d{4})", text)
    if match:
        try:
            return datetime.strptime(
                f"{match.group(1)} {match.group(2)} {match.group(3)}", "%b %d %Y"
            ).date()
        except ValueError:
            return None
    return None


def cran_releases(package: str) -> tuple[list[Release], list[str]]:
    """Fetch the dated release history of a CRAN package.

    Uses the crandb metadata service rather than scraping the archive listing,
    which returns both current and archived versions in one document.

    Args:
        package: CRAN package name.

    Returns:
        A `(releases, errors)` pair, releases sorted oldest first.
    """
    errors: list[str] = []
    try:
        response = _get(f"{CRANDB}/{package}/all")
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        return [], [f"crandb fetch failed: {exc}"]

    releases = []
    for version, meta in (payload.get("versions") or {}).items():
        released = _parse_cran_date(
            meta.get("Date/Publication") or meta.get("Packaged") or meta.get("Date")
        )
        releases.append(Release(version=version, released=released))

    undated = sum(1 for r in releases if not r.released)
    if undated:
        errors.append(f"{undated} of {len(releases)} releases have no recorded date")

    releases.sort(key=lambda r: (r.released or date.min, r.version))
    return releases, errors


def cran_source(
    package: str, version: str | None = None
) -> tuple[str, str, list[str], list[str]]:
    """Fetch a CRAN package's changelog and export list from its source tarball.

    The tarball is the most complete source: NEWS files are cumulative, so the
    newest one carries the full history, and packages that expose nothing through
    CRAN's rendered news page often still ship a NEWS file. It also carries
    NAMESPACE, which is why exports come from here rather than from an installed
    copy -- there is no install to do, so no ceiling on how many packages the
    frame can cover.

    Args:
        package: CRAN package name.
        version: Version to download. Defaults to the current release.

    Returns:
        A `(text, source, exports, errors)` tuple. `text` is empty when the
        package ships no recognizable changelog; `exports` is empty when it ships
        no NAMESPACE, which for a modern package means the download failed.
    """
    errors: list[str] = []
    if version is None:
        try:
            response = _get(f"{CRANDB}/{package}")
            response.raise_for_status()
            version = response.json().get("Version")
        except (requests.RequestException, ValueError) as exc:
            return "", "", [], [f"could not resolve current version: {exc}"]

    urls = [
        f"{CRAN_SRC}/{package}_{version}.tar.gz",
        f"{CRAN_SRC}/Archive/{package}/{package}_{version}.tar.gz",
    ]
    for url in urls:
        try:
            response = _get(url, timeout=180, stream=True)
            if response.status_code != 200:
                continue
            with tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / "pkg.tar.gz"
                archive.write_bytes(response.content)
                text, source, exports, error = _read_tarball(archive, package)
                if error:
                    errors.append(error)
                if not text:
                    errors.append(f"no changelog file in {url}")
                if not exports:
                    errors.append(f"no NAMESPACE in {url}")
                return text, f"{url}::{source}" if text else "", exports, errors
        except (requests.RequestException, tarfile.TarError, OSError) as exc:
            errors.append(f"{url}: {exc}")
    return "", "", [], [*errors, "tarball not retrievable"]


def _strip_r_comments(text: str) -> str:
    """Remove `#` comments from R source, respecting string literals.

    Real NAMESPACE files carry comments inside `export(...)` blocks -- sandwich
    opens its export list with `## core ingredients` -- so a regex applied to raw
    text harvests the comment as though it were a function name.

    Args:
        text: R source.

    Returns:
        The source with comments blanked out, line structure preserved.
    """
    kept = []
    for line in text.split("\n"):
        quote, escaped, cut = "", False, len(line)
        for index, char in enumerate(line):
            if escaped:
                escaped = False
            elif quote:
                if char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
            elif char in "\"'`":
                quote = char
            elif char == "#":
                cut = index
                break
        kept.append(line[:cut])
    return "\n".join(kept)


def _balanced(text: str, start: int) -> str:
    """Return the contents of the parenthesis group opening at `start`.

    Args:
        text: Source text.
        start: Index of the opening parenthesis.

    Returns:
        The text between the parentheses, empty if unbalanced.
    """
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index]
    return ""


def parse_namespace(text: str, definitions: set[str] | None = None) -> list[str]:
    """Extract the names a package exports from its NAMESPACE file.

    This replaces asking a running R session, which required every package to be
    installed and so capped the study at the packages one machine could build.

    Args:
        text: Contents of NAMESPACE.
        definitions: Names defined in the package's own R sources, needed to
            resolve `exportPattern` regexes into an actual name list.

    Returns:
        The exported names, sorted.
    """
    clean = _strip_r_comments(text)
    names: set[str] = set()

    for match in NAMESPACE_EXPORT.finditer(clean):
        body = _balanced(clean, match.end() - 1)
        for raw in body.split(","):
            name = raw.strip().strip("\"'`").strip()
            if name:
                names.add(name)

    for match in NAMESPACE_S3.finditer(clean):
        parts = [
            part.strip().strip("\"'`").strip()
            for part in _balanced(clean, match.end() - 1).split(",")
        ]
        if len(parts) >= 2 and parts[0] and parts[1]:
            names.add(f"{parts[0]}.{parts[1]}")

    for _, pattern in NAMESPACE_PATTERN.findall(clean):
        if not definitions:
            continue
        try:
            compiled = re.compile(pattern.replace("\\\\", "\\"))
        except re.error:
            continue
        names |= {name for name in definitions if compiled.search(name)}

    return sorted(name for name in names if name)


def _read_tarball(
    archive: Path, package: str
) -> tuple[str, str, list[str], str | None]:
    """Pull the changelog and the export list out of an R source tarball.

    Both come from one open: the tarball is fetched into a temporary directory
    and discarded, so reading NAMESPACE separately would mean downloading every
    package twice.

    Args:
        archive: Path to the `.tar.gz`.
        package: Package name, which prefixes every path inside the tarball.

    Returns:
        A `(text, member_name, exports, error)` tuple.
    """
    text, source = "", ""
    exports: list[str] = []
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = {m.name: m for m in tar.getmembers() if m.isfile()}

            def read(name: str) -> str:
                handle = tar.extractfile(members[name])
                return handle.read().decode("utf-8", errors="replace") if handle else ""

            for candidate in R_NEWS_CANDIDATES:
                name = f"{package}/{candidate}"
                if name in members:
                    text = read(name)
                    if text:
                        source = candidate
                        break

            namespace = f"{package}/NAMESPACE"
            if namespace in members:
                raw = read(namespace)
                definitions: set[str] = set()
                if NAMESPACE_PATTERN.search(raw):
                    for name in members:
                        if name.startswith(f"{package}/R/") and name.endswith(
                            (".R", ".r", ".S", ".q")
                        ):
                            definitions |= r_definitions(read(name))
                exports = parse_namespace(raw, definitions)
    except (tarfile.TarError, OSError) as exc:
        return "", "", [], f"could not read tarball: {exc}"
    return text, source, exports, None


def r_definitions(source: str) -> set[str]:
    """Enumerate the functions an R source file defines at top level.

    Args:
        source: Contents of an R source file.

    Returns:
        Every name bound to a function, including all names in a chained
        assignment.
    """
    names: set[str] = set()
    for chain in R_DEFINITION.findall(source):
        for part in re.split(r"<-|=", chain):
            name = part.strip().strip("\"'`").strip()
            if name:
                names.add(name)
    return names


def pypi_releases(package: str) -> tuple[list[Release], list[str]]:
    """Fetch the dated release history of a PyPI package.

    Args:
        package: PyPI project name.

    Returns:
        A `(releases, errors)` pair, releases sorted oldest first.
    """
    try:
        response = _get(f"{PYPI}/{package}/json")
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        return [], [f"pypi fetch failed: {exc}"]

    releases = []
    for version, files in (payload.get("releases") or {}).items():
        uploaded = None
        for entry in files:
            raw = entry.get("upload_time_iso_8601") or entry.get("upload_time")
            if raw:
                try:
                    uploaded = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
                    break
                except ValueError:
                    continue
        releases.append(Release(version=version, released=uploaded))

    releases.sort(key=lambda r: (r.released or date.min, r.version))
    return releases, []


def harvest_cran(package: str) -> Harvest:
    """Collect releases and changelog text for one CRAN package.

    Args:
        package: CRAN package name.

    Returns:
        The harvest, with any non-fatal problems in `errors`.
    """
    releases, errors = cran_releases(package)
    text, source, exports, source_errors = cran_source(package)
    return Harvest(
        package=package,
        ecosystem="cran",
        releases=releases,
        news_text=text,
        news_source=source,
        exports=exports,
        errors=errors + source_errors,
    )


def github_notes(package: str, timeout: int = 60) -> tuple[str, str, list[str]]:
    """Fetch a Python project's release notes from its GitHub repository.

    Every file in the project's release-notes directory is concatenated in name
    order. The parser finds version sections wherever they fall, so the ordering
    only has to be stable, not meaningful.

    Args:
        package: PyPI project name, which must appear in `PYTHON_NOTES`.
        timeout: Seconds before giving up on a single request.

    Returns:
        A `(text, source, errors)` triple. Text is empty when the project is not
        mapped or the directory cannot be listed.
    """
    if package not in PYTHON_NOTES:
        return "", "", [f"no release-notes location known for {package}"]

    repo, directory, extension = PYTHON_NOTES[package]
    errors: list[str] = []
    try:
        response = _get(f"{GITHUB_API}/{repo}/contents/{directory}", timeout=timeout)
        response.raise_for_status()
        listing = response.json()
    except (requests.RequestException, ValueError) as exc:
        return "", "", [f"could not list {repo}/{directory}: {exc}"]

    names = sorted(
        item["name"]
        for item in listing
        if item.get("type") == "file" and item.get("name", "").endswith(extension)
    )

    chunks = []
    for name in names:
        try:
            page = _get(f"{GITHUB_RAW}/{repo}/HEAD/{directory}/{name}", timeout=timeout)
            if page.status_code == 200:
                chunks.append(page.text)
            else:
                errors.append(f"{name}: HTTP {page.status_code}")
        except requests.RequestException as exc:
            errors.append(f"{name}: {exc}")

    if not chunks:
        return "", "", [*errors, f"no readable notes in {repo}/{directory}"]
    return (
        "\n\n".join(chunks),
        f"github:{repo}/{directory} ({len(chunks)} files)",
        errors,
    )


#: Introspects a Python distribution's public API. R declares its exports in a
#: file; Python has no such file, so the names have to come from the objects
#: themselves.
#:
#: Module-level names only. Collecting methods too is tempting -- release notes
#: name them, and `fit_regularized` exists only as a method -- but it was tried
#: and measured: methods added `values`, `get`, `set`, `fit`, `transform`,
#: `score`, `shape`, and `size` to the export set, and those alone drove 150 of
#: the candidate entries, none of them about a statistical procedure. What is
#: kept is the analogue of what R's NAMESPACE declares.
PYTHON_EXPORTS = """
import importlib, inspect, json, pkgutil, sys, warnings
warnings.simplefilter("ignore")
# statsmodels ships sandbox and example modules that print, and in some cases
# fit models, at import time. Importing them pollutes stdout and wastes minutes,
# which is why the result is written to a file rather than printed.
SKIP = ("test", "tests", "sandbox", "examples", "example", "benchmarks", "setup",
        "conftest", "_build_utils", "datasets", "docs")
root = importlib.import_module(sys.argv[1])
names, modules = set(), [root]
if hasattr(root, "__path__"):
    for info in pkgutil.walk_packages(root.__path__, root.__name__ + "."):
        parts = info.name.split(".")
        if any(p.startswith("_") or p in SKIP for p in parts):
            continue
        try:
            modules.append(importlib.import_module(info.name))
        except BaseException:
            continue
for module in modules:
    for attr in dir(module):
        if attr.startswith("_"):
            continue
        try:
            obj = getattr(module, attr)
        except BaseException:
            continue
        if inspect.isroutine(obj) or inspect.isclass(obj):
            names.add(attr)
open(sys.argv[2], "w").write(json.dumps(sorted(names)))
"""

#: Distribution name to the module it installs, where they differ.
PYTHON_MODULES = {"scikit-learn": "sklearn"}


def python_exports(package: str, timeout: int = 900) -> set[str]:
    """Introspect a Python package's public names in a throwaway environment.

    The Python funnel had no export restriction, which is why its candidates
    were noisier than R's and were left out of the classified rate: without one,
    every English word in a release note that happens to match a call in the
    corpus becomes a candidate. `uv` makes the fix cheap -- the package is
    installed into a temporary environment and imported, so nothing has to be
    present on this machine beforehand.

    Args:
        package: PyPI distribution name.
        timeout: Seconds before giving up.

    Returns:
        Public functions, classes, and methods. Empty if the package cannot be
        installed or imported, which shows up as zero yield downstream.
    """
    module = PYTHON_MODULES.get(package, package.replace("-", "_"))
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "exports.json"
        proc = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "uv",
                "run",
                "--quiet",
                "--no-project",
                "--with",
                package,
                "python",
                "-c",
                PYTHON_EXPORTS,
                module,
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if proc.returncode != 0 or not out.exists():
            return set()
        return set(json.loads(out.read_text()))


def harvest_pypi(package: str) -> Harvest:
    """Collect releases and release notes for one PyPI package.

    The two halves come from different services: PyPI dates the releases, and
    GitHub holds the notes, because Python projects ship documentation in the
    repository rather than in the distribution.

    Args:
        package: PyPI project name.

    Returns:
        The harvest.
    """
    releases, errors = pypi_releases(package)
    text, source, note_errors = github_notes(package)
    exports = sorted(python_exports(package))
    if not exports:
        errors.append(f"could not introspect {package}")
    return Harvest(
        package=package,
        ecosystem="pypi",
        releases=releases,
        news_text=text,
        news_source=source,
        exports=exports,
        errors=errors + note_errors,
    )


def cache_path(root: Path, ecosystem: str, package: str) -> Path:
    """Return the on-disk location for a package's harvest.

    Args:
        root: Cache root directory.
        ecosystem: `cran` or `pypi`.
        package: Package name.

    Returns:
        Path to the harvest JSON.
    """
    return Path(root) / ecosystem / f"{package}.json"


def harvest(
    package: str, ecosystem: str, cache_root: Path, refresh: bool = False
) -> Harvest:
    """Collect a package's harvest, reusing the cache unless asked to refresh.

    Every stage downstream re-reads this file rather than re-fetching, so a full
    reclassification costs no network at all.

    Args:
        package: Package name.
        ecosystem: `cran` or `pypi`.
        cache_root: Cache root directory.
        refresh: Ignore any cached copy and fetch again.

    Returns:
        The harvest.
    """
    path = cache_path(cache_root, ecosystem, package)
    payload = json.loads(path.read_text()) if path.exists() else None
    # A cache written before exports were collected is stale, not merely partial:
    # serving it would leave the package with no attributable functions and so no
    # candidates, which is indistinguishable from a package with nothing wrong.
    stale = payload is not None and "exports" not in payload
    if payload is not None and not refresh and not stale:
        return Harvest(
            package=payload["package"],
            ecosystem=payload["ecosystem"],
            releases=[
                Release(
                    version=r["version"],
                    released=date.fromisoformat(r["released"])
                    if r["released"]
                    else None,
                )
                for r in payload["releases"]
            ],
            news_text=payload["news_text"],
            news_source=payload["news_source"],
            exports=payload.get("exports", []),
            errors=payload["errors"],
        )

    result = harvest_cran(package) if ecosystem == "cran" else harvest_pypi(package)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2))
    return result
