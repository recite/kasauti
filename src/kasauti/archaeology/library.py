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


def _tidy(log: str, limit: int = 240) -> str:
    """Reduce a build log to one line that fits in a CSV cell.

    Args:
        log: Captured output.
        limit: Characters to keep.

    Returns:
        The tail of the log, whitespace collapsed.
    """
    return " ".join(log.split())[-limit:]


def install(
    package: str, version: str, root: Path | None = None, timeout: int = 900
) -> tuple[Path | None, str]:
    """Install one archived CRAN version into its own library, unconditionally.

    The uncached primitive. Callers should use `ensure`, which consults the
    ledger first.

    Args:
        package: CRAN package name.
        version: Version to install.
        root: Library root. Defaults to `library_root()`.
        timeout: Seconds before giving up.

    Returns:
        A `(library_path, detail)` pair, the path being None when the build
        failed and `detail` carrying the tail of the log.
    """
    lib = path_for(package, version, root)
    lib.mkdir(parents=True, exist_ok=True)

    url = f"{CRAN_ARCHIVE}/{package}/{package}_{version}.tar.gz"
    script = f'install.packages("{url}", repos = NULL, type = "source", lib = "{lib}")'
    try:
        proc = subprocess.run(  # noqa: S603
            ["Rscript", "--vanilla", "-e", script],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    if (lib / package).exists():
        return lib, ""
    return None, _tidy(proc.stderr or proc.stdout)


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
