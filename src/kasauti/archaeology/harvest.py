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
        errors: Non-fatal problems encountered.
    """

    package: str
    ecosystem: str
    releases: list[Release] = field(default_factory=list)
    news_text: str = ""
    news_source: str = ""
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


def cran_news(package: str, version: str | None = None) -> tuple[str, str, list[str]]:
    """Fetch a CRAN package's changelog from its source tarball.

    The tarball is the most complete source: NEWS files are cumulative, so the
    newest one carries the full history, and packages that expose nothing through
    CRAN's rendered news page often still ship a NEWS file.

    Args:
        package: CRAN package name.
        version: Version to download. Defaults to the current release.

    Returns:
        A `(text, source, errors)` triple. `text` is empty when the package ships
        no recognizable changelog.
    """
    errors: list[str] = []
    if version is None:
        try:
            response = _get(f"{CRANDB}/{package}")
            response.raise_for_status()
            version = response.json().get("Version")
        except (requests.RequestException, ValueError) as exc:
            return "", "", [f"could not resolve current version: {exc}"]

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
                text, source, error = _read_news_from_tarball(archive, package)
                if error:
                    errors.append(error)
                if text:
                    return text, f"{url}::{source}", errors
                return "", "", [*errors, f"no changelog file in {url}"]
        except (requests.RequestException, tarfile.TarError, OSError) as exc:
            errors.append(f"{url}: {exc}")
    return "", "", [*errors, "tarball not retrievable"]


def _read_news_from_tarball(archive: Path, package: str) -> tuple[str, str, str | None]:
    """Pull the first recognizable changelog out of an R source tarball.

    Args:
        archive: Path to the `.tar.gz`.
        package: Package name, which prefixes every path inside the tarball.

    Returns:
        A `(text, member_name, error)` triple.
    """
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = {m.name: m for m in tar.getmembers() if m.isfile()}
            for candidate in R_NEWS_CANDIDATES:
                name = f"{package}/{candidate}"
                if name not in members:
                    continue
                handle = tar.extractfile(members[name])
                if handle is None:
                    continue
                return handle.read().decode("utf-8", errors="replace"), candidate, None
    except (tarfile.TarError, OSError) as exc:
        return "", "", f"could not read tarball: {exc}"
    return "", "", None


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
    text, source, news_errors = cran_news(package)
    return Harvest(
        package=package,
        ecosystem="cran",
        releases=releases,
        news_text=text,
        news_source=source,
        errors=errors + news_errors,
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
    return Harvest(
        package=package,
        ecosystem="pypi",
        releases=releases,
        news_text=text,
        news_source=source,
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
    if path.exists() and not refresh:
        payload = json.loads(path.read_text())
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
            errors=payload["errors"],
        )

    result = harvest_cran(package) if ecosystem == "cran" else harvest_pypi(package)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2))
    return result
