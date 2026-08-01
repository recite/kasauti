"""Test a changelog's claim cheaply, before deciding whether to write it up.

Seven bug records exist against a shortlist of forty-one entries the pipeline
already flagged as silent, result-changing, and high severity. The gap is not
selection -- it is that a record demands a fixture, a backend, per-quantity
expectation prose, and a probe regex before a single number is measured. So a
claim gets *tested* only after someone has committed an afternoon to *publishing*
it, and those two things should not cost the same.

A screen is the cheap half. It runs one fixture against the release that carried
the fix and the release immediately before it, and asks one question: did any
number move? No prose, no expectations, no probe. Only a screen that moved
something is promoted to a record.

**Adjacent versions, not current.** Existing records compare the buggy version
against whatever is installed today -- for `sandwich` 2.5-0 that is seven years
and thirty-one releases of unrelated change folded into one diff. A predecessor
pair attributes the movement to a single release.

**Three outcomes, and the third is the point.** A screen that sees nothing move
has not refuted the changelog; its fixture may simply never have reached the
code. That is the same distinction `ABSENT` taught the bisect, and it is kept
honest by a **positive control**: every fixture states what it checked to know
the condition was met, and a screen whose control fails is `UNEVALUABLE` rather
than `NOT_TRIGGERED`.

Screening also buys the thing a hand-curated base cannot report -- a denominator.
Every published finding so far is a success, because failures were never cheap
enough to attempt.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from kasauti.archaeology import library
from kasauti.archaeology.bisect import NOT_YET_IMPLEMENTED, run_backend

MOVED = "MOVED"
NOT_TRIGGERED = "NOT_TRIGGERED"
UNEVALUABLE = "UNEVALUABLE"

#: Report order: what was found, then what was not, then what could not be looked
#: at. The last group is a claim about this study rather than about the packages.
ORDER = [MOVED, NOT_TRIGGERED, UNEVALUABLE]

#: Below this a difference is arithmetic noise rather than a change in behaviour.
#: The same band `AGREE` uses in the comparison harness, for the same reason.
DEFAULT_TOL = 1e-8

#: Two values both this small are equal. Comparing a denormal against an exact
#: zero otherwise reports a huge relative difference between two numbers that are
#: zero for every purpose.
NOISE_FLOOR = 1e-12


@dataclass
class Request:
    """One changelog claim to test.

    Attributes:
        entry_id: The changelog entry, as `package@version#index`.
        package: Owning package.
        fixed_in: Release that carried the fix.
        script: Fixture script to run, relative to the fixture directory.
        functions: Functions the entry names.
        conditions: The triggering conditions, as the entry states them.
    """

    entry_id: str
    package: str
    fixed_in: str
    script: str
    functions: list[str] = field(default_factory=list)
    conditions: str = ""

    @property
    def slug(self) -> str:
        """A filename for this screen.

        Returns:
            The entry id with `@` and `#` reduced to hyphens.
        """
        return re.sub(r"[^A-Za-z0-9.-]+", "-", self.entry_id).strip("-")


@dataclass
class Screen:
    """What running one fixture against two adjacent releases showed.

    Attributes:
        entry_id: The changelog entry tested.
        package: Owning package.
        before: Release immediately preceding the fix.
        after: Release that carried the fix.
        before_on: Release date of `before`.
        after_on: Release date of `after`.
        exact: Whether the changelog's fix version is itself a CRAN release. When
            it is not, `before` and `after` straddle it and a movement is
            attributable to that span rather than to one release.
        verdict: `MOVED`, `NOT_TRIGGERED`, or `UNEVALUABLE`.
        detail: Why, in one line.
        script: Fixture script that produced it.
        control: What the fixture checked to know its condition was met.
        moved: Quantities that differ between the two releases.
        max_reldiff: Largest relative difference over shared quantities.
        quantities: Both releases' numbers, `before` and `after`.
    """

    entry_id: str
    package: str
    before: str = ""
    after: str = ""
    before_on: date | None = None
    after_on: date | None = None
    exact: bool = True
    verdict: str = UNEVALUABLE
    detail: str = ""
    script: str = ""
    control: str = ""
    moved: list[str] = field(default_factory=list)
    max_reldiff: float = 0.0
    quantities: dict[str, dict[str, float]] = field(default_factory=dict)

    def write(self, directory: Path) -> Path:
        """Write the screen to JSON.

        Args:
            directory: Where screens for this package live.

        Returns:
            The path written.
        """
        directory.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^A-Za-z0-9.-]+", "-", self.entry_id).strip("-")
        path = directory / f"{slug}.json"
        payload = asdict(self)
        payload["before_on"] = self.before_on.isoformat() if self.before_on else None
        payload["after_on"] = self.after_on.isoformat() if self.after_on else None
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return path

    @classmethod
    def load(cls, path: Path) -> Screen:
        """Read a screen back from JSON.

        Written alongside `write` and tested as a round trip, because the last
        time a field was added to one side and not the other it was the record's
        own evidence that went missing.

        Args:
            path: File to read.

        Returns:
            The screen.
        """
        payload = json.loads(path.read_text())
        for key in ("before_on", "after_on"):
            payload[key] = date.fromisoformat(payload[key]) if payload[key] else None
        return cls(**payload)


def version_key(version: str) -> tuple[int, ...]:
    """Order a CRAN version string.

    Args:
        version: A version like `2.35-8`, `1.9-0`, or `2.4.6.26`.

    Returns:
        Its numeric components, comparable with `<`.
    """
    return tuple(int(part) for part in re.findall(r"\d+", version))


def bracket(
    releases: list[tuple[str, date | None]], version: str
) -> tuple[tuple[str, date | None] | None, tuple[str, date | None] | None, bool]:
    """The releases on either side of a changelog's stated fix version.

    Usually the fix version *is* a release and the pair is it and its immediate
    predecessor. Often enough it is not. `survival`'s NEWS is organised under
    headings like "2.35" that CRAN never shipped, and six of the nine fix
    versions on this study's `survival` shortlist have no archive tarball at all
    -- Terry Therneau releases through his own channel and only some versions
    reach CRAN.

    Rather than discard those claims, the pair widens to the releases that
    straddle the stated version, and `exact` records that it did. The screen is
    still valid; it is just attributing a movement to a span of releases instead
    of to one, and a reader must be told which they are looking at.

    Args:
        releases: `(version, released)` pairs, oldest first.
        version: The version the changelog says carried the fix.

    Returns:
        A `(before, after, exact)` triple. Either side is None when the history
        does not reach that far.
    """
    target = version_key(version)
    before = [r for r in releases if version_key(r[0]) < target]
    after = [r for r in releases if version_key(r[0]) >= target]
    return (
        before[-1] if before else None,
        after[0] if after else None,
        bool(after) and after[0][0] == version,
    )


def relative_difference(a: float, b: float) -> float:
    """Relative difference between two numbers, with a noise floor.

    Args:
        a: One value.
        b: The other.

    Returns:
        `|a - b| / max(|a|, |b|)`, or 0.0 when both are below the noise floor.
    """
    if not math.isfinite(a) or not math.isfinite(b):
        return 0.0 if a == b else math.inf
    scale = max(abs(a), abs(b))
    if scale < NOISE_FLOOR:
        return 0.0
    return abs(a - b) / scale


def _controlled(result: dict) -> tuple[bool, str]:
    """Whether a run demonstrated it reached the code under test.

    A fixture states its own control -- `inherits(m, "mlm")`, say -- and a screen
    that cannot see one has no basis for saying a defect was not triggered, only
    that it was not observed. The two are different claims and the weaker one is
    the honest default.

    Args:
        result: A backend's result JSON.

    Returns:
        A `(passed, description)` pair.
    """
    diagnostics = result.get("diagnostics") or {}
    if "control" not in diagnostics:
        return False, ""
    says = str(diagnostics.get("control_says") or "").strip()
    return bool(diagnostics["control"]), says


def _errored(result: dict | None) -> str:
    """Describe why a run cannot be compared, or "" if it can.

    Args:
        result: A backend's result JSON, or None.

    Returns:
        A one-line reason, empty when the run is usable.
    """
    if result is None:
        return "produced no result"
    if result.get("status") != "ok":
        message = (result.get("error") or "").strip()
        if any(marker in message.lower() for marker in NOT_YET_IMPLEMENTED):
            # Worth naming rather than lumping in with the build failures: an
            # entry whose predecessor has no such function is documenting a
            # feature, not fixing a defect, and the shortlist misread it.
            return f"the function does not exist in this version -- {message[:160]}"
        return f"errored -- {message[:160]}"
    return ""


def judge(
    before: dict | None,
    after: dict | None,
    tol: float = DEFAULT_TOL,
) -> tuple[str, str, list[str], float]:
    """Decide what two adjacent releases showed.

    Args:
        before: Result from the release preceding the fix.
        after: Result from the release carrying it.
        tol: Relative difference above which a quantity counts as moved.

    Returns:
        A `(verdict, detail, moved, max_reldiff)` tuple.
    """
    # A run must survive three questions in this order before its numbers mean
    # anything: did it run, did it say what it checked, and did that check hold.
    runs: dict[str, dict] = {}
    for label, result in (("before", before), ("after", after)):
        reason = _errored(result)
        if reason:
            return UNEVALUABLE, f"{label}: {reason}", [], 0.0
        runs[label] = result or {}

        passed, says = _controlled(runs[label])
        if not says:
            return (
                UNEVALUABLE,
                f"{label}: the fixture declares no positive control, so "
                "'nothing moved' cannot be distinguished from 'nothing ran'",
                [],
                0.0,
            )
        if not passed:
            return UNEVALUABLE, f"{label}: control failed -- {says}", [], 0.0

    old = {
        k: v
        for k, v in (runs["before"].get("quantities") or {}).items()
        if v is not None
    }
    new = {
        k: v
        for k, v in (runs["after"].get("quantities") or {}).items()
        if v is not None
    }
    shared = sorted(set(old) & set(new))
    if not shared:
        return UNEVALUABLE, "the two runs share no comparable quantity", [], 0.0

    moved = [k for k in shared if relative_difference(old[k], new[k]) >= tol]
    largest = max(relative_difference(old[k], new[k]) for k in shared)

    # A quantity that appears or vanishes is a change in what the function
    # returns, which is a changed result by any reading a user would recognise.
    only_before = sorted(set(old) - set(new))
    only_after = sorted(set(new) - set(old))
    reshaped = [*(f"-{k}" for k in only_before), *(f"+{k}" for k in only_after)]

    if moved or reshaped:
        parts = []
        if moved:
            parts.append(f"{len(moved)} of {len(shared)} quantities moved")
        if reshaped:
            parts.append(f"{len(reshaped)} appeared or vanished")
        return MOVED, "; ".join(parts), [*moved, *reshaped], largest
    return (
        NOT_TRIGGERED,
        f"all {len(shared)} quantities agree; the fixture did not reach the defect",
        [],
        largest,
    )


def render_report(screens: list[Screen], declared: int, fixtures: list[str]) -> str:
    """Render the screening coverage report.

    Args:
        screens: Screens that have been run.
        declared: How many claims the fixture catalogues declare.
        fixtures: Fixture directories the screens drew on.

    Returns:
        Markdown.
    """
    counts = {v: sum(1 for s in screens if s.verdict == v) for v in ORDER}
    lines = [
        "# Screening changelog claims",
        "",
        f"{declared} claim(s) declared across {len(fixtures)} package fixture(s); "
        f"**{len(screens)}** screened.",
        "",
        "A screen runs one fixture against the release that carried a fix and the "
        "release immediately before it, and asks whether any number moved. It is "
        "the cheap half of a bug record: no prose, no per-quantity expectations, "
        "no exposure probe. Only a screen that moved something is promoted.",
        "",
        "## Verdicts",
        "",
        "| verdict | n | meaning |",
        "|---|---|---|",
        f"| `MOVED` | {counts[MOVED]} | a quantity differs between the two releases |",
        f"| `NOT_TRIGGERED` | {counts[NOT_TRIGGERED]} | they agree; the fixture did "
        "not reach the defect |",
        f"| `UNEVALUABLE` | {counts[UNEVALUABLE]} | a version would not build, or "
        "the call errored |",
        "",
        "**`NOT_TRIGGERED` is not a refutation.** It says a particular fixture, "
        "written from a particular reading of the entry, did not move a number -- "
        "which is a falsifiable statement about the fixture, not a verdict on the "
        "maintainer. Every fixture states a positive control, so a run that never "
        "reached the code is reported as `UNEVALUABLE` instead.",
        "",
        "## What was screened",
        "",
        "| entry | versions | verdict | moved | largest | control |",
        "|---|---|---|---|---|---|",
    ]
    for screen in sorted(screens, key=lambda s: (ORDER.index(s.verdict), s.entry_id)):
        total = len(screen.quantities.get("after") or {})
        moved = f"{len(screen.moved)}/{total}" if total else "--"
        largest = f"{screen.max_reldiff:.2e}" if screen.max_reldiff else "--"
        span = f"{screen.before} → {screen.after}" + ("" if screen.exact else " ~")
        lines.append(
            f"| `{screen.entry_id}` | {span} | "
            f"`{screen.verdict}` | {moved} | {largest} | {screen.control or '--'} |"
        )

    inexact = [s for s in screens if not s.exact]
    if inexact:
        lines += [
            "",
            f"`~` marks the {len(inexact)} claim(s) whose stated fix version CRAN "
            "never shipped, so the pair straddles it rather than pinning it. "
            "`survival`'s NEWS is organised under headings like `2.35` that are not "
            "releases, and several versions it names went out through the author's "
            "own channel. A movement there is attributable to the span, not to one "
            "release, and the bisect is what narrows it.",
        ]

    lines += [
        "",
        "## Fixtures",
        "",
        "One fixture per package, not per bug. The shortlist concentrates -- "
        "`survival` alone is twelve claims -- so a dataset written once serves "
        "many entries, and what varies per claim is the call and its control.",
        "",
        *(f"* `fixtures/{name}/`" for name in sorted(fixtures)),
        "",
    ]
    return "\n".join(lines)


def run(
    request: Request,
    fixtures: Path,
    releases: list[tuple[str, date | None]],
    ledger: library.Ledger,
    tol: float = DEFAULT_TOL,
    timeout: int = 600,
) -> Screen:
    """Screen one changelog claim against adjacent releases.

    Args:
        request: The claim to test.
        fixtures: Directory holding this package's fixture and scripts.
        releases: `(version, released)` pairs, oldest first.
        ledger: Build ledger.
        tol: Relative difference above which a quantity counts as moved.
        timeout: Seconds allowed per backend run.

    Returns:
        The screen, whatever it found.
    """
    screen = Screen(
        entry_id=request.entry_id,
        package=request.package,
        script=request.script,
    )

    earlier, later, exact = bracket(releases, request.fixed_in)
    screen.exact = exact
    if earlier is None or later is None:
        missing = "predecessor" if earlier is None else "release at or after it"
        screen.detail = (
            f"{request.fixed_in} has no {missing} on CRAN, so there is nothing to "
            "compare against"
        )
        return screen
    screen.before, screen.before_on = earlier
    screen.after, screen.after_on = later

    cmd = ["Rscript", "--vanilla", request.script, f"${{{library.ROOT_VARIABLE}}}"]
    runs: dict[str, dict | None] = {}
    for label, version in (("before", screen.before), ("after", screen.after)):
        lib, detail = library.ensure(request.package, version, ledger)
        if lib is None:
            screen.detail = f"{label}: {version} would not build -- {detail}"
            return screen
        runs[label] = run_backend(
            fixtures, cmd, lib, timeout=timeout, data=fixtures / "data.csv"
        )

    verdict, detail, moved, largest = judge(runs["before"], runs["after"], tol)
    screen.verdict, screen.detail = verdict, detail
    screen.moved, screen.max_reldiff = moved, largest
    screen.quantities = {
        label: (result or {}).get("quantities") or {} for label, result in runs.items()
    }
    if runs["after"]:
        screen.control = _controlled(runs["after"])[1]
    return screen
