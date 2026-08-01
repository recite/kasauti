"""Find when a bug was introduced by running the reproducer against old versions.

Changelogs say when a defect was fixed and almost never when it started: of 369
exposed entries, **4** name an introducing version and 11 call themselves
regressions. So the left edge of every exposure window in this study is censored,
and `papers_in_window` currently means "published before the fix" with no lower
bound at all.

The only way to get a real date is to run the code. A verified record already
carries everything needed: a backend script parameterised by library path, and
two reference outputs -- `results.buggy.json` and `results.fixed.json` -- recorded
when the bug was verified. Running that same script against an archived version
and asking *which of the two it matches* needs no new oracle.

Three outcomes per probe, never two. The old end of a version range is exactly
where source packages stop building against a current toolchain, and collapsing
"could not evaluate" into "not buggy" would date every introduction to the last
version that happened to compile -- an answer that looks precise and is an
artifact of the build environment.

The result is a bracket, not a point: the newest version observed FIXED and the
oldest observed BUGGY. Bisection also assumes the predicate is monotone -- that a
bug, once introduced, stays until the fix. That is usually true and occasionally
not, so the bracket's two endpoints are re-tested and the assumption is recorded
with the answer rather than left implicit.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

BUGGY = "BUGGY"
FIXED = "FIXED"
ABSENT = "ABSENT"
UNEVALUABLE = "UNEVALUABLE"

#: R's way of saying the code under test does not exist in this version. A bug in
#: a method that has not been written is not a bug, so this is evidence that the
#: defect had not yet been introduced -- categorically different from a version
#: that could not be built or errored for reasons nobody has established.
#:
#: The distinction is what turned the sandwich bisect from an inconclusive "buggy
#: as far back as it compiles" into a measurement: `vcovHC` had no `mlm` method
#: before 2.2-4, so the sign error arrived with the feature.
NOT_YET_IMPLEMENTED = (
    "no applicable method",
    "could not find function",
    "unused argument",
    "unable to find an inherited method",
)

#: Where archived versions are installed, matching what the `case.yaml` backends
#: already use so a bisect and a verification exercise the same library. A
#: throwaway location on purpose: these are decade-old sources built only to be
#: interrogated, and they must never join the environment the tool itself runs in.
RLIBS = Path("/tmp/rlibs")  # noqa: S108


@dataclass
class Probe:
    """One version, tested.

    Attributes:
        version: The version installed.
        released: Its release date.
        outcome: `BUGGY`, `FIXED`, `ABSENT`, or `UNEVALUABLE`.
        detail: Why, for anything other than a clean BUGGY or FIXED.
    """

    version: str
    released: date | None
    outcome: str
    detail: str = ""


@dataclass
class Bisection:
    """The bracket a bisect established.

    Attributes:
        probes: Every version tested, in the order tested.
        last_fixed: Newest version observed not to have the bug -- either
            behaving like the fixed version, or lacking the code entirely.
        first_buggy: Oldest version observed to exhibit the bug.
        unevaluable: Versions that could not be judged either way.
    """

    probes: list[Probe] = field(default_factory=list)
    last_fixed: Probe | None = None
    first_buggy: Probe | None = None
    unevaluable: list[Probe] = field(default_factory=list)

    @property
    def introduced_on(self) -> date | None:
        """The date to record as the bug's introduction.

        The oldest version seen to exhibit the bug. Deliberately not the midpoint
        of the bracket: a measured date that is provably too late is better than
        an interpolated one that is merely plausible, and "too late" narrows the
        exposure window rather than inflating it.

        Returns:
            The release date of `first_buggy`, or None if nothing was.
        """
        return self.first_buggy.released if self.first_buggy else None

    @property
    def bracketed(self) -> bool:
        """Whether both edges of the transition were observed.

        Returns:
            True when a FIXED or ABSENT version was found below a BUGGY one,
            which is what distinguishes a measured introduction from "buggy as
            far back as it would build".
        """
        return self.last_fixed is not None and self.first_buggy is not None

    @property
    def arrived_with_the_feature(self) -> bool:
        """Whether the bug was present from the moment the code existed.

        Returns:
            True when the version below the transition lacks the code entirely
            rather than having a working version of it. A stronger claim than a
            plain bracket: nobody broke this, it was wrong when written.
        """
        return self.last_fixed is not None and self.last_fixed.outcome == ABSENT


def install(package: str, version: str, timeout: int = 900) -> tuple[Path | None, str]:
    """Install one archived CRAN version into its own library.

    Args:
        package: CRAN package name.
        version: Version to install.
        timeout: Seconds before giving up.

    Returns:
        A `(library_path, detail)` pair. The path is None when the build failed,
        and `detail` carries the tail of the build log -- which is a result worth
        keeping, since a version that cannot be built bounds how far back the
        archaeology can reach.
    """
    lib = RLIBS / f"{package}_{version}"
    if (lib / package).exists():
        return lib, "already installed"
    lib.mkdir(parents=True, exist_ok=True)

    url = f"https://cran.r-project.org/src/contrib/Archive/{package}/{package}_{version}.tar.gz"
    script = f'install.packages("{url}", repos = NULL, type = "source", lib = "{lib}")'
    proc = subprocess.run(  # noqa: S603
        ["Rscript", "--vanilla", "-e", script],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if (lib / package).exists():
        return lib, ""
    return None, (proc.stderr or proc.stdout)[-400:]


def run_backend(
    directory: Path, cmd: list[str], lib: Path, timeout: int = 600
) -> dict | None:
    """Run a record's backend script against an installed library.

    Args:
        directory: The bug record's directory.
        cmd: Backend argv from `case.yaml`, whose first flag is the library path.
        lib: Library holding the version under test.
        timeout: Seconds before giving up.

    Returns:
        The parsed result JSON, or None when the run failed or wrote nothing.
    """
    import os

    from milaan.runner import LIB_DIR

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "result.json"
        argv = [*cmd, str(directory / "data.csv"), str(out)]
        # The library path is the first flag in every version-pinned backend.
        argv = [str(lib) if arg.startswith(str(RLIBS)) else arg for arg in argv]
        try:
            subprocess.run(  # noqa: S603
                argv,
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
                env={**os.environ, "MILAAN_LIB": str(LIB_DIR)},
            )
        except subprocess.TimeoutExpired:
            return None
        return json.loads(out.read_text()) if out.exists() else None


def classify_run(
    observed: dict | None,
    buggy: dict,
    fixed: dict,
    tol: float = 1e-8,
) -> tuple[str, str]:
    """Decide whether a run looks like the buggy version or the fixed one.

    Compares against both reference outputs recorded at verification time, so no
    new predicate has to be invented per bug. A run matching neither is
    `UNEVALUABLE` rather than assigned to the nearer one: the older an archived
    version is, the more likely it differs from both for reasons that have
    nothing to do with this defect.

    Args:
        observed: The run's result JSON, or None if it did not run.
        buggy: Reference output from the buggy version.
        fixed: Reference output from the fixed version.
        tol: Relative difference below which two values count as equal.

    Returns:
        An `(outcome, detail)` pair.
    """
    from milaan.compare import relative_difference

    if observed is None:
        return UNEVALUABLE, "backend produced no result"
    if observed.get("status") != "ok":
        message = (observed.get("error") or "").lower()
        if any(marker in message for marker in NOT_YET_IMPLEMENTED):
            return ABSENT, (observed.get("error") or "").strip()[:120]
        return UNEVALUABLE, f"backend status {observed.get('status')}"

    quantities = observed.get("quantities") or {}

    # A run that produced no comparable number at all usually means the code
    # path did not exist -- but a case whose backend wraps the call in
    # `try(silent = TRUE)` and writes NA has destroyed the evidence that would
    # say so, and "not implemented" then looks identical to "broke for some
    # other reason". Reported as unevaluable, with the cause named, because a
    # bisect cannot be sharper than the reproducer it is driving.
    comparable = [
        k for k in (fixed.get("quantities") or {}) if quantities.get(k) is not None
    ]
    if not comparable:
        return (
            UNEVALUABLE,
            "produced no comparable quantity; the reproducer may swallow errors",
        )

    def matches(reference: dict) -> bool:
        values = reference.get("quantities") or {}
        shared = [
            k
            for k in values
            if quantities.get(k) is not None and values.get(k) is not None
        ]
        if not shared:
            return False
        return all(
            relative_difference(float(quantities[k]), float(values[k])) < tol
            for k in shared
        )

    like_buggy, like_fixed = matches(buggy), matches(fixed)
    if like_buggy and not like_fixed:
        return BUGGY, ""
    if like_fixed and not like_buggy:
        return FIXED, ""
    if like_buggy and like_fixed:
        # The two references agree on every shared quantity, so this case cannot
        # tell the versions apart at all.
        return UNEVALUABLE, "the two reference outputs are indistinguishable here"
    return UNEVALUABLE, "matches neither reference output"


def search(
    versions: list[tuple[str, date | None]],
    evaluate,
    on_probe=None,
) -> Bisection:
    """Binary-search a version history for where a bug appears.

    Args:
        versions: `(version, released)` oldest first, all strictly older than
            the fix.
        evaluate: Callable taking `(version, released)` and returning a `Probe`.
        on_probe: Optional callback invoked with each `Probe` as it completes,
            so a long run can report progress.

    Returns:
        The bracket, with every probe recorded.

    The search walks outward on `UNEVALUABLE` rather than treating it as an
    answer: when the midpoint cannot be judged, neighbours are tried before the
    range is narrowed, so a single unbuildable version does not silently decide
    which half to discard.
    """
    result = Bisection()
    seen: dict[str, Probe] = {}

    def probe(index: int) -> Probe:
        version, released = versions[index]
        if version not in seen:
            found = evaluate(version, released)
            seen[version] = found
            result.probes.append(found)
            if found.outcome == UNEVALUABLE:
                result.unevaluable.append(found)
            if on_probe:
                on_probe(found)
        return seen[version]

    def judgeable(index: int, low: int, high: int) -> int | None:
        """Nearest index to `index` that yields a verdict, searching outward.

        Confined to the live window. Searching the whole history instead let the
        walk return an index outside `[low, high]`, after which the update did
        not shrink the range and the loop never terminated -- which is exactly
        what happened the first time this ran.
        """
        for offset in range(high - low + 1):
            for candidate in (index - offset, index + offset):
                if low <= candidate <= high and probe(candidate).outcome != UNEVALUABLE:
                    return candidate
        return None

    low, high = 0, len(versions) - 1
    while low <= high:
        middle = judgeable((low + high) // 2, low, high)
        if middle is None:
            break
        found = seen[versions[middle][0]]
        if found.outcome == BUGGY:
            result.first_buggy = found
            high = middle - 1
        else:
            # FIXED and ABSENT both mean "the bug is not here", and both bound
            # the search from below. They are kept apart in the report because
            # one says the code was right and the other that it was not written.
            result.last_fixed = found
            low = middle + 1

    return result
