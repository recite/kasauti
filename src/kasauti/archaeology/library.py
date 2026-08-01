"""Build archived package versions once, and remember what would not build.

Every measurement in this study that reaches backwards -- verifying a bug against
its predecessor, bisecting an introduction, sweeping a version history -- runs the
same operation: install version V of package P and call it. At seven records that
operation was cheap enough to be careless about. It is not any more: screening the
41-entry shortlist against adjacent releases is 80-odd installs, the bisects that
follow are a hundred more, and a sweep over the nine packages the screens will
have fixtures for is roughly 740.

Two things made the old `bisect.install` unaffordable at that scale, and both are
the same mistake in different clothes -- forgetting a result:

* it installed into `/tmp`, which the operating system empties, so a build
  survived only until the next reboot;
* it retried failures, so a version that cannot compile against this toolchain
  cost its full timeout every single time it was asked for.

So builds go to a persistent root, and every outcome -- success and failure alike
-- is written to a **ledger**. A failure recorded once is never attempted again,
which turns the most expensive case into the cheapest.

The ledger is not merely a cache. The set of versions that will not build against
a current toolchain is the hard limit on how far archaeology can reach, and it is
worth publishing rather than rediscovering: R made `NAMESPACE` mandatory in 2008,
so nothing older installs at all, and `fixest`'s templated C++ stops compiling
somewhere in mid-2021. `floor()` reads that boundary off the ledger per package.
"""

from __future__ import annotations

import csv
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

BUILT = "BUILT"
FAILED = "FAILED"

#: Where archived versions live when nothing says otherwise. Under the user's
#: cache directory rather than the repository: these are decade-old sources built
#: only to be interrogated, they are large, and they are reproducible from CRAN.
#: Under the cache directory rather than `/tmp` because the whole point is that
#: they outlive a reboot.
DEFAULT_ROOT = Path.home() / ".cache" / "kasauti" / "rlibs"

#: Environment variable naming the root. Exported to backends so a `case.yaml`
#: can write `${KASAUTI_RLIBS}/sandwich_2.4-0` instead of a literal path, which
#: is how every pinned case came to point at a directory that gets emptied.
ROOT_VARIABLE = "KASAUTI_RLIBS"

CRAN_ARCHIVE = "https://cran.r-project.org/src/contrib/Archive"

#: Where a missing dependency is fetched from. Current versions, deliberately:
#: the archived package under test is the measurement, and pinning its whole
#: dependency tree to the same era is a much larger project than this one.
CRAN_MIRROR = "https://cloud.r-project.org"

#: R's complaint when `repos = NULL` left it unable to resolve an import.
MISSING_DEPENDENCY = re.compile(
    r"dependenc(?:y|ies)\s+(.+?)\s+(?:is|are) not available", re.IGNORECASE
)

#: The curly-quoted package names inside that complaint.
QUOTED = re.compile("[\u2018']([A-Za-z][\\w.]*)[\u2019']")

#: The tarball was not where it was looked for, which for the newest release of a
#: package means it is still in the main contrib directory rather than the Archive.
DOWNLOAD_FAILED = re.compile(r"download\.file|cannot open URL|HTTP status was '404")

#: A C header the compiler could not find.
MISSING_HEADER = re.compile(r"fatal error: '([\w./+-]+\.h)' file not found")

#: Where such a header plausibly lives on a machine that has it. Package managers
#: install into their own prefixes and R is not told, so the header can be present
#: and invisible at the same time.
HEADER_PREFIXES = (
    "/opt/homebrew/opt/*/include",
    "/usr/local/opt/*/include",
    "/opt/homebrew/include",
    "/usr/local/include",
    "/opt/local/include",
)

LEDGER_COLUMNS = ["package", "version", "outcome", "r_version", "platform", "detail"]


def library_root() -> Path:
    """Return the root under which archived versions are installed.

    Returns:
        `$KASAUTI_RLIBS` if set, else `DEFAULT_ROOT`.
    """
    return Path(os.environ.get(ROOT_VARIABLE, DEFAULT_ROOT))


def path_for(package: str, version: str, root: Path | None = None) -> Path:
    """Return the library directory for one version.

    Args:
        package: Package name.
        version: Version string.
        root: Library root. Defaults to `library_root()`.

    Returns:
        The directory the version is (or would be) installed into.
    """
    return (root or library_root()) / f"{package}_{version}"


def mentions_root(argument: str) -> bool:
    """Whether a backend argument names the version-library slot.

    Args:
        argument: One element of a backend command.

    Returns:
        True if the argument refers to the archived-version library, either by
        the environment variable or by a path under the resolved root.
    """
    return ROOT_VARIABLE in argument or argument.startswith(str(library_root()))


def substitute(cmd: list[str], lib: Path) -> list[str]:
    """Point a version-pinned backend command at a particular library.

    The same script serves every archived version; which one it loads is a flag.
    That is what lets a bisect drive a record's own reproducer without the record
    knowing it is being bisected.

    Args:
        cmd: Backend argv as the case declares it.
        lib: Library holding the version to load.

    Returns:
        The command with its library slot replaced and other variables expanded.

    Raises:
        ValueError: If no argument names the library slot. Silently returning the
            command unchanged would run the reproducer against whichever version
            happens to be installed and report the answer as if it came from the
            requested one.
    """
    from milaan.runner import expand

    out, replaced = [], False
    for argument in cmd:
        if mentions_root(argument):
            out.append(str(lib))
            replaced = True
        else:
            out.append(expand(argument))
    if not replaced:
        raise ValueError(
            f"no argument names the version library in {cmd!r}; a pinned backend "
            f"must pass ${{{ROOT_VARIABLE}}}/<package>_<version>"
        )
    return out


def r_version() -> str:
    """Return the R version builds are running against.

    Recorded on every ledger row, because "will not build" is a statement about a
    toolchain and is worthless without naming it.

    Returns:
        The version string, or "unknown" if R could not be asked.
    """
    script = "cat(paste0(R.version$major, '.', R.version$minor))"
    try:
        proc = subprocess.run(  # noqa: S603
            ["Rscript", "--vanilla", "-e", script],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return proc.stdout.strip() or "unknown"


@dataclass
class Build:
    """One attempt to install one version.

    Attributes:
        package: Package name.
        version: Version string.
        outcome: `BUILT` or `FAILED`.
        r_version: The R the attempt ran against.
        platform: The machine it ran on.
        detail: Tail of the build log, for a failure.
    """

    package: str
    version: str
    outcome: str
    r_version: str = ""
    platform: str = ""
    detail: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """Ledger key.

        Returns:
            The `(package, version)` pair identifying this build.
        """
        return (self.package, self.version)


@dataclass
class Ledger:
    """What has been built, and what refused to build.

    Attributes:
        path: CSV the ledger is read from and written to.
        builds: Recorded attempts, keyed by `(package, version)`.
    """

    path: Path
    builds: dict[tuple[str, str], Build] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Ledger:
        """Read a ledger, or start an empty one.

        Args:
            path: CSV to read.

        Returns:
            The ledger.
        """
        ledger = cls(path=path)
        if not path.exists():
            return ledger
        with path.open() as handle:
            for row in csv.DictReader(handle):
                build = Build(
                    package=row["package"],
                    version=row["version"],
                    outcome=row["outcome"],
                    r_version=row.get("r_version", ""),
                    platform=row.get("platform", ""),
                    detail=row.get("detail", ""),
                )
                ledger.builds[build.key] = build
        return ledger

    def get(self, package: str, version: str) -> Build | None:
        """Look up a recorded attempt.

        Args:
            package: Package name.
            version: Version string.

        Returns:
            The recorded build, or None if this version has not been tried.
        """
        return self.builds.get((package, version))

    def record(self, build: Build) -> None:
        """Add or replace an attempt and write the ledger out.

        Written on every record rather than at the end: a sweep is a long
        unattended run, and a ledger that only exists once the run finishes is
        exactly the one lost when it does not.

        Args:
            build: The attempt to record.
        """
        self.builds[build.key] = build
        self.write()

    def write(self) -> None:
        """Write the ledger to its CSV, sorted for a stable diff."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=LEDGER_COLUMNS)
            writer.writeheader()
            for key in sorted(self.builds):
                build = self.builds[key]
                writer.writerow(
                    {
                        "package": build.package,
                        "version": build.version,
                        "outcome": build.outcome,
                        "r_version": build.r_version,
                        "platform": build.platform,
                        "detail": build.detail,
                    }
                )


#: Lines worth keeping out of a failed build log. `install.packages` ends with a
#: wrapper message naming the tarball and saying it had non-zero exit status,
#: which is true of every failure and explains none of them. The compiler's own
#: first complaint is the reason -- `unknown type name 'Sint'` is what puts every
#: `survival` before 3.4-0 out of reach, and keeping the tail loses it.
#: A compiler diagnostic proper, which always writes `error:` with the colon.
#: Preferred over the looser pattern because compilers echo the offending source
#: line too, and `{ error(_("An out of bound write ..."` is source, not a reason.
BUILD_DIAGNOSTIC = re.compile(r"^.*\berror:.*$", re.MULTILINE)

BUILD_ERROR = re.compile(r"^.*\b(?:error|Error|ERROR)\b.*$", re.MULTILINE)

#: Wrapper noise that matches BUILD_ERROR but says nothing.
BUILD_NOISE = ("had non-zero exit status", "unable to install packages")


def _tidy(log: str, limit: int = 240) -> str:
    """Reduce a build log to the line that explains the failure.

    Args:
        log: Captured output.
        limit: Characters to keep.

    Returns:
        The most informative error line, or the tail of the log if none stands
        out.
    """
    for pattern in (BUILD_DIAGNOSTIC, BUILD_ERROR):
        for line in pattern.findall(log):
            text = " ".join(line.split())
            if text and not any(noise in text for noise in BUILD_NOISE):
                return text[:limit]
    return " ".join(log.split())[-limit:]


def _rscript(
    script: str, timeout: int, env: dict[str, str] | None = None
) -> tuple[str, bool]:
    """Run an R expression and return its combined output.

    Args:
        script: R source.
        timeout: Seconds before giving up.
        env: Extra environment variables for the run.

    Returns:
        An `(output, timed_out)` pair.
    """
    try:
        proc = subprocess.run(  # noqa: S603
            ["Rscript", "--vanilla", "-e", script],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env={**os.environ, **(env or {})},
        )
    except subprocess.TimeoutExpired:
        return "", True
    return (proc.stderr or "") + (proc.stdout or ""), False


def header_include(log: str) -> Path | None:
    """Where a header the build could not find actually lives, if it does.

    `mgcv` fails on `fatal error: 'libintl.h' file not found` -- on a machine
    that has `libintl.h`, sitting in a Homebrew prefix R was never told about.
    Recording that as a wall would attribute to the package a fact about this
    machine's include path, which is the same mistake the missing-dependency
    retry exists to avoid.

    Environment `CPPFLAGS` does not help: R's own `Makeconf` sets it and wins.
    The supported route is a user `Makevars`, which is what the caller does with
    the directory returned here.

    Args:
        log: A failed build log.

    Returns:
        The directory holding the missing header, or None if the failure is not
        a missing header or the header is genuinely absent.
    """
    names = MISSING_HEADER.findall(log)
    if not names:
        return None
    for pattern in HEADER_PREFIXES:
        for directory in sorted(Path("/").glob(pattern.lstrip("/"))):
            if (directory / names[0]).exists():
                return directory
    return None


def _last_archived(package: str) -> str | None:
    """The newest version of a package CRAN has archived.

    Args:
        package: Package name.

    Returns:
        Its last archived version, or None if the archive has no listing for it.
    """
    from kasauti.archaeology.harvest import cran_releases

    try:
        releases, _ = cran_releases(package)
    except Exception:
        return None
    return releases[-1].version if releases else None


#: How far to chase a chain of deleted dependencies. `Rcgmin` needs `optextras`,
#: and one more link is plausible; beyond that the right conclusion is that the
#: release is out of reach rather than that more effort is owed.
SUPPLY_DEPTH = 3


def _supply(name: str, lib: Path, timeout: int, depth: int = SUPPLY_DEPTH) -> bool:
    """Make one dependency available in a library, from CRAN or from the archive.

    Args:
        name: Package to supply.
        lib: Library to install it into.
        timeout: Seconds per install.
        depth: How many further links of a deleted-dependency chain to follow.

    Returns:
        Whether the package is present afterwards.
    """
    if (lib / name).exists():
        return True

    log, _ = _rscript(
        f'install.packages("{name}", lib = "{lib}", repos = "{CRAN_MIRROR}")', timeout
    )
    if (lib / name).exists():
        return True
    if depth <= 0:
        return False

    newest = _last_archived(name)
    if not newest:
        return False

    url = f"{CRAN_ARCHIVE}/{name}/{name}_{newest}.tar.gz"
    build = f'install.packages("{url}", repos = NULL, type = "source", lib = "{lib}")'
    log, _ = _rscript(build, timeout)
    if (lib / name).exists():
        return True

    for wanted in missing_dependencies(log):
        _supply(wanted, lib, timeout, depth - 1)
    _rscript(build, timeout)
    return (lib / name).exists()


def missing_dependencies(log: str) -> list[str]:
    """Packages a build could not find, read off its own complaint.

    Args:
        log: A failed build log.

    Returns:
        The dependency names R named, in the order it named them.
    """
    found: list[str] = []
    for clause in MISSING_DEPENDENCY.findall(log):
        found.extend(QUOTED.findall(clause))
    return found


def install(
    package: str, version: str, root: Path | None = None, timeout: int = 900
) -> tuple[Path | None, str]:
    """Install one archived CRAN version into its own library, unconditionally.

    The uncached primitive. Callers should use `ensure`, which consults the
    ledger first.

    Installing from a URL means `repos = NULL`, which switches off dependency
    resolution entirely -- so a package whose `Imports` are not already on the
    machine fails for a reason that has nothing to do with whether its source
    still compiles. `psych` failed on all six of its shortlisted versions purely
    for want of `mnormt`. That is not a toolchain wall and must not be recorded
    as one, so a missing dependency is fetched from CRAN and the build retried
    once. Dependencies land in the version's own library rather than the system
    one, which keeps decade-old sources out of the environment the tool runs in.

    A missing *header* is the same mistake in the other direction. `mgcv` fails on
    `fatal error: 'libintl.h' file not found` on a machine that has `libintl.h`,
    in a package-manager prefix R was never told about. Environment `CPPFLAGS`
    cannot fix it -- R's own `Makeconf` sets that variable and wins -- so the
    retry writes a user `Makevars` and points `R_MAKEVARS_USER` at it.

    Both retries are corrections for facts about *this machine*. Neither touches a
    failure where the source itself no longer compiles, which is the only kind
    that belongs in the ledger as a wall.

    Args:
        package: CRAN package name.
        version: Version to install.
        root: Library root. Defaults to `library_root()`.
        timeout: Seconds before giving up.

    Returns:
        A `(library_path, detail)` pair, the path being None when the build
        failed and `detail` carrying the line of the log that explains it.
    """
    lib = path_for(package, version, root)
    lib.mkdir(parents=True, exist_ok=True)

    def source(url: str) -> str:
        return (
            f'install.packages("{url}", repos = NULL, type = "source", lib = "{lib}")'
        )

    build = source(f"{CRAN_ARCHIVE}/{package}/{package}_{version}.tar.gz")
    log, expired = _rscript(build, timeout)
    if expired:
        return None, f"timed out after {timeout}s"
    if (lib / package).exists():
        return lib, ""

    if DOWNLOAD_FAILED.search(log):
        # A package's *current* version is not in the Archive -- CRAN moves a
        # release there only once it is superseded. Without this the newest
        # release of every package swept becomes a gap, which is the one release
        # a reader is most likely to check.
        build = source(f"{CRAN_MIRROR}/src/contrib/{package}_{version}.tar.gz")
        log, expired = _rscript(build, timeout)
        if expired:
            return None, f"timed out after {timeout}s"
        if (lib / package).exists():
            return lib, ""

    wanted = missing_dependencies(log)
    if wanted:
        names = ", ".join(f'"{name}"' for name in wanted)
        _rscript(
            f'install.packages(c({names}), lib = "{lib}", repos = "{CRAN_MIRROR}")',
            timeout,
        )
        # A dependency CRAN has *deleted* is not on the mirror at all. `plm`
        # 1.2-x needs `kinship`, removed in 2012, and `lfe` needs `Rcgmin`,
        # folded into `optimx`; between them they were closing 23 releases of
        # two heavily used packages, one of which owns the highest-reach
        # function in the whole corpus.
        #
        # A deleted package's own dependencies are often deleted too -- `Rcgmin`
        # wants `optextras` -- so the supply recurses, bounded. The alternative
        # is writing off the releases or writing a package manager.
        for name in wanted:
            _supply(name, lib, timeout)

        log, expired = _rscript(build, timeout)
        if expired:
            return None, f"timed out after {timeout}s"
        if (lib / package).exists():
            return lib, ""

    include = header_include(log)
    if include is not None:
        makevars = lib / "Makevars"
        makevars.write_text(
            f"CPPFLAGS += -I{include}\nLDFLAGS += -L{include.parent / 'lib'}\n"
        )
        log, expired = _rscript(build, timeout, {"R_MAKEVARS_USER": str(makevars)})
        if expired:
            return None, f"timed out after {timeout}s"
        if (lib / package).exists():
            return lib, ""

    return None, _tidy(log)


def ensure(
    package: str,
    version: str,
    ledger: Ledger,
    root: Path | None = None,
    timeout: int = 900,
    retry: bool = False,
) -> tuple[Path | None, str]:
    """Return a library holding this version, building it only if it must.

    Three ways to answer without spending a build, in the order they are checked:
    the directory is already populated; the ledger says this version built; the
    ledger says it did not. Only the fourth case runs `install`.

    Args:
        package: CRAN package name.
        version: Version wanted.
        ledger: Ledger to consult and update.
        root: Library root. Defaults to `library_root()`.
        timeout: Seconds before giving up on a build.
        retry: Attempt a version the ledger records as failed. For use after the
            toolchain changes, which is the only thing that could change the
            answer.

    Returns:
        A `(library_path, detail)` pair. The path is None when the version is
        unavailable, and `detail` says why -- carried forward from the ledger
        when the failure was recorded earlier, so the reason survives.
    """
    lib = path_for(package, version, root)
    recorded = ledger.get(package, version)

    if (lib / package).exists():
        if recorded is None or recorded.outcome != BUILT:
            ledger.record(
                Build(package, version, BUILT, r_version(), platform.platform())
            )
        return lib, ""

    if recorded is not None and recorded.outcome == FAILED and not retry:
        # Not a cache hit -- a recorded measurement. This version was tried once
        # against a named toolchain and would not build; spending the timeout
        # again would produce the same answer more slowly.
        return None, recorded.detail

    found, detail = install(package, version, root, timeout)
    ledger.record(
        Build(
            package=package,
            version=version,
            outcome=BUILT if found else FAILED,
            r_version=r_version(),
            platform=platform.platform(),
            detail=detail,
        )
    )
    return found, detail


def adopt(ledger: Ledger, root: Path | None = None) -> int:
    """Record every version already installed under the root.

    A build that happened before the ledger existed is still a build. Scanning
    for them costs a directory listing and saves re-deriving what is plainly on
    disk. A directory with no package inside is skipped rather than recorded as
    failed: `install` creates it before building, so an empty one means the build
    was attempted, not that it is impossible.

    Args:
        ledger: Ledger to add to.
        root: Library root. Defaults to `library_root()`.

    Returns:
        How many versions were newly recorded.
    """
    root = root or library_root()
    if not root.exists():
        return 0
    added = 0
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or "_" not in directory.name:
            continue
        package, version = directory.name.split("_", 1)
        if not (directory / package).exists():
            continue
        if (ledger.get(package, version) or Build("", "", "")).outcome == BUILT:
            continue
        ledger.builds[(package, version)] = Build(
            package, version, BUILT, r_version(), platform.platform()
        )
        added += 1
    if added:
        ledger.write()
    return added


#: How a failure reads, reduced to the thing it is an instance of. Grouping the
#: ledger this way turns a list of broken builds into a short list of walls, which
#: is the publishable form: an archived version is out of reach for one of a
#: handful of reasons, and every reason is a fact about the present toolchain
#: rather than about the package.
WALLS = (
    ("Sint", "the C sources use `Sint`, an S-PLUS typedef R no longer defines"),
    ("Calloc", "the C sources call `Calloc`, renamed `R_Calloc` in R 4.2"),
    ("NAMED", "the C sources call `NAMED`, which R's API no longer exposes"),
    ("DOUBLE_EPS", "the C++ sources use `DOUBLE_EPS`, a constant R has withdrawn"),
    ("NAMESPACE", "no `NAMESPACE` file, which R has required since 2008"),
    ("parse_Rd", "documentation in an Rd syntax R no longer parses"),
    (
        "implicit function declarations",
        "a C function declared implicitly, which current compilers reject",
    ),
    ("libintl.h", "the C sources need gettext headers this machine does not have"),
    ("not available for package", "a dependency that is no longer on CRAN"),
    ("GDAL", "a geospatial system library this machine does not have"),
    ("too few arguments", "a C call whose R-internal signature has since changed"),
    ("timed out", "the build did not finish inside the timeout"),
)


def wall(detail: str) -> str:
    """Name the class of failure a build log describes.

    Args:
        detail: A recorded failure reason.

    Returns:
        A one-line description of the wall, or the detail itself if it does not
        match a known one.
    """
    for marker, description in WALLS:
        if marker in detail:
            return description
    return detail


def walls(ledger: Ledger) -> dict[str, list[tuple[str, str]]]:
    """Group every recorded failure by the wall it hit.

    Args:
        ledger: Ledger of build attempts.

    Returns:
        Wall description to the `(package, version)` pairs it stopped.
    """
    grouped: dict[str, list[tuple[str, str]]] = {}
    for build in ledger.builds.values():
        if build.outcome != FAILED:
            continue
        grouped.setdefault(wall(build.detail), []).append(
            (build.package, build.version)
        )
    return {key: sorted(value) for key, value in sorted(grouped.items())}


def floor(package: str, versions: list[str], ledger: Ledger) -> str | None:
    """The oldest version of a package that is known to build.

    How far back archaeology can reach for this package. Read off the release
    order rather than by parsing version strings, because CRAN version numbers
    are not orderable in general -- `1.5-13` sorts after `1.5-9` only if you
    already know the convention.

    Args:
        package: Package name.
        versions: Its releases, oldest first.
        ledger: Ledger of build attempts.

    Returns:
        The oldest version recorded `BUILT`, or None if none has been.
    """
    for version in versions:
        build = ledger.get(package, version)
        if build is not None and build.outcome == BUILT:
            return version
    return None


def reach(package: str, versions: list[str], ledger: Ledger) -> dict[str, int]:
    """Summarise what is known about building a package's history.

    Args:
        package: Package name.
        versions: Its releases, oldest first.
        ledger: Ledger of build attempts.

    Returns:
        Counts of releases `tried`, `built`, `failed`, and `untried`.
    """
    tried = built = failed = 0
    for version in versions:
        build = ledger.get(package, version)
        if build is None:
            continue
        tried += 1
        if build.outcome == BUILT:
            built += 1
        else:
            failed += 1
    return {
        "tried": tried,
        "built": built,
        "failed": failed,
        "untried": len(versions) - tried,
    }
