"""The bug record: one directory per bug, one file per stage.

A bug is a unit of work, not a row in a table. Each one runs the same sequence --
triage it, narrow its exposure, find the papers, run it against pinned versions,
write up what happened -- and each stage leaves a durable artifact in the bug's
own directory. A session picks up wherever the last one stopped instead of
re-deriving the shortlist.

The layout is deliberate: a bug directory that has reached verification contains
a `case.yaml`, which `loader.discover_cases` already finds by `rglob`. So a
verified bug is an ordinary case to the comparison engine, and an unverified one
is simply not discovered. The lifecycle falls out of the files.

Records for candidates that did not survive verification stay in the tree.
`REFUTED` and `NOT_REPRODUCED` are results -- a lead that failed is exactly what a
later session must not spend an afternoon rediscovering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

#: Lifecycle states in order. Everything before the terminal three is progress
#: through the pipeline; the terminal three are verdicts on the bug itself.
PIPELINE_STATES = ["CANDIDATE", "PROBED", "LINKED"]
TERMINAL_STATES = ["VERIFIED", "REFUTED", "NOT_REPRODUCED"]
STATUSES = PIPELINE_STATES + TERMINAL_STATES

#: Which pipeline stage each status implies has completed. The terminal states
#: sit past the pipeline for ordering purposes, but they do *not* imply the
#: earlier stages ran: verification and exposure-counting are independent axes,
#: and a bug can be run against pinned versions before anyone counts its reach.
STAGE_OF = {name: index for index, name in enumerate(PIPELINE_STATES)}
STAGE_OF.update({name: len(PIPELINE_STATES) for name in TERMINAL_STATES})

SEVERITY_WEIGHT = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

CATEGORIES = [
    "RESULT_CHANGING",
    "BEHAVIOR_CHANGE",
    "ERROR_TO_WORKING",
    "PERFORMANCE",
    "FEATURE",
    "DOC",
    "UNCLEAR",
]


class BugError(ValueError):
    """Raised when a `bug.yaml` is malformed or claims more than it shows."""


@dataclass
class Exposure:
    """How many scripts and papers a bug could have reached.

    Two script counts, never one. A probe is a regular expression over source
    text: it can show a script *could* have met the triggering condition, never
    that it did. Reporting only the narrowed number would present a guess as a
    measurement, and reporting only the function-name count overstates by up to
    two orders of magnitude -- `sandwich` 2.5-0 looked like 79 scripts and was 1.

    Attributes:
        scripts_calling_function: Scripts calling any affected function. Upper
            bound.
        scripts_meeting_probe: Of those, scripts matching the conditions probe.
            None until the probe stage has run.
        papers_in_window: Distinct papers whose replication archive contains a
            matching script and which were published while the bug was live.
        papers_censored: Papers that match but whose window is left-censored
            because the bug's introducing version is unknown.
    """

    scripts_calling_function: int | None = None
    scripts_meeting_probe: int | None = None
    papers_in_window: int | None = None
    papers_censored: int | None = None

    @property
    def narrowed(self) -> int | None:
        """The best available script count.

        Returns:
            The probe count where the probe has run, else the function-name
            count, else None.
        """
        if self.scripts_meeting_probe is not None:
            return self.scripts_meeting_probe
        return self.scripts_calling_function

    def to_dict(self) -> dict[str, Any]:
        """Return the YAML form.

        Returns:
            The exposure as a plain dict.
        """
        return {
            "scripts_calling_function": self.scripts_calling_function,
            "scripts_meeting_probe": self.scripts_meeting_probe,
            "papers_in_window": self.papers_in_window,
            "papers_censored": self.papers_censored,
        }


@dataclass
class Bug:
    """One bug's record.

    Attributes:
        id: Stable identifier, matching the directory name.
        package: Package the bug was in.
        ecosystem: `cran` or `pypi`.
        entry_id: Back-pointer into the changelog corpus.
        fixed_in: Version that shipped the fix.
        fixed_on: Date that version was released.
        introduced_in: Version that introduced the defect, if known.
        introduced_on: Date that version was released, if known.
        functions: Affected exported functions.
        conditions: When the bug bit, in prose. Mandatory -- a bug without
            stated conditions cannot have its exposure narrowed, and an
            un-narrowed exposure count has been wrong every time it was checked.
        condition_probe: Regular expression over script source that approximates
            `conditions`. Stored so a reader can judge the bound rather than
            trust it.
        category: What kind of change this was.
        silent: Whether the buggy version answered wrong without warning. The
            field that separates a corrupted published result from a loud
            failure nobody shipped.
        severity: Consequence where the bug applied.
        status: Lifecycle state.
        exposure: Script and paper counts.
        magnitude: What verification measured, in prose.
        directory: Where the record lives.
    """

    id: str
    package: str
    fixed_in: str
    conditions: str
    ecosystem: str = "cran"
    entry_id: str | None = None
    fixed_on: date | None = None
    introduced_in: str | None = None
    introduced_on: date | None = None
    functions: list[str] = field(default_factory=list)
    condition_probe: str | None = None
    category: str = "RESULT_CHANGING"
    silent: bool = True
    severity: str = "MEDIUM"
    status: str = "CANDIDATE"
    exposure: Exposure = field(default_factory=Exposure)
    magnitude: str | None = None
    directory: Path | None = None

    @property
    def stage(self) -> int:
        """How far through the pipeline this record has got.

        Returns:
            The index of the completed stage.
        """
        return STAGE_OF[self.status]

    @property
    def is_terminal(self) -> bool:
        """Whether verification has reached a verdict.

        Returns:
            True for `VERIFIED`, `REFUTED`, or `NOT_REPRODUCED`.
        """
        return self.status in TERMINAL_STATES

    @property
    def censored(self) -> bool:
        """Whether the exposure window is open at the left.

        Returns:
            True when the introducing version is unknown, so the bug cannot be
            dated to a start.
        """
        return self.introduced_on is None

    @property
    def rank(self) -> tuple[int, int]:
        """Sort key: severity first, then narrowed exposure.

        Returns:
            A tuple ordering the most consequential and widest-reaching first.
        """
        return (SEVERITY_WEIGHT.get(self.severity, 0), self.exposure.narrowed or 0)

    def has_case(self) -> bool:
        """Whether a verification case sits beside this record.

        Returns:
            True when `case.yaml` exists in the bug directory.
        """
        return bool(self.directory and (self.directory / "case.yaml").exists())

    def to_dict(self) -> dict[str, Any]:
        """Return the YAML form, with dates as ISO strings.

        Returns:
            The record as a plain dict, ready to serialize.
        """
        return {
            "id": self.id,
            "package": self.package,
            "ecosystem": self.ecosystem,
            "entry_id": self.entry_id,
            "fixed_in": self.fixed_in,
            "fixed_on": self.fixed_on.isoformat() if self.fixed_on else None,
            "introduced_in": self.introduced_in,
            "introduced_on": (
                self.introduced_on.isoformat() if self.introduced_on else None
            ),
            "functions": list(self.functions),
            "conditions": self.conditions,
            "condition_probe": self.condition_probe,
            "category": self.category,
            "silent": self.silent,
            "severity": self.severity,
            "status": self.status,
            "exposure": self.exposure.to_dict(),
            "magnitude": self.magnitude,
        }


def _as_date(value: Any) -> date | None:
    """Coerce a YAML scalar to a date.

    Args:
        value: A date, an ISO string, or None.

    Returns:
        The date, or None.

    Raises:
        BugError: If the value is neither a date nor a parseable ISO string.
    """
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise BugError(f"cannot parse date {value!r}") from exc


def validate(bug: Bug) -> None:
    """Check a record for internal consistency.

    The rules mirror `loader.load_case`'s refusal to accept an expected
    divergence with no reason: a record may not assert more than it shows.

    Args:
        bug: The record to check.

    Raises:
        BugError: On any inconsistency, naming the record and the problem.
    """
    where = bug.id

    if bug.status not in STATUSES:
        raise BugError(f"{where}: unknown status {bug.status!r}")
    if bug.category not in CATEGORIES:
        raise BugError(f"{where}: unknown category {bug.category!r}")
    if bug.severity not in SEVERITY_WEIGHT:
        raise BugError(f"{where}: unknown severity {bug.severity!r}")

    if not bug.conditions.strip():
        raise BugError(
            f"{where}: conditions is required. Without stated conditions the "
            "exposure count cannot be narrowed, and an un-narrowed count has "
            "overstated reach by up to 100x every time it was checked."
        )

    if bug.directory and bug.directory.name != bug.id:
        raise BugError(
            f"{where}: id does not match its directory name {bug.directory.name!r}"
        )

    # Only the pipeline states assert that probing happened. The terminal states
    # are verification verdicts on an independent axis -- a bug can be run
    # against pinned versions before anyone has counted its exposure, and
    # requiring otherwise would make a VERIFIED record unloadable until probed.
    if (
        bug.status in ("PROBED", "LINKED")
        and bug.exposure.scripts_meeting_probe is None
    ):
        raise BugError(
            f"{where}: status is {bug.status} but no probe count is recorded"
        )
    if bug.status == "LINKED" and bug.exposure.papers_in_window is None:
        raise BugError(f"{where}: status is LINKED but no paper count is recorded")

    if bug.status == "VERIFIED":
        if not bug.has_case():
            raise BugError(
                f"{where}: status is VERIFIED but there is no case.yaml beside "
                "the record, so the claim has nothing behind it"
            )
        if not bug.magnitude:
            raise BugError(
                f"{where}: status is VERIFIED but magnitude is empty -- record "
                "what running it actually showed"
            )


def load_bug(directory: Path) -> Bug:
    """Read and validate a bug record.

    Args:
        directory: Directory containing `bug.yaml`.

    Returns:
        The parsed record.

    Raises:
        BugError: If the file is missing or fails validation.
    """
    directory = Path(directory)
    path = directory / "bug.yaml"
    if not path.exists():
        raise BugError(f"no bug.yaml in {directory}")

    raw = yaml.safe_load(path.read_text()) or {}
    exposure_raw = raw.get("exposure") or {}

    bug = Bug(
        id=raw.get("id", directory.name),
        package=raw.get("package", ""),
        fixed_in=str(raw.get("fixed_in", "")),
        conditions=raw.get("conditions") or "",
        ecosystem=raw.get("ecosystem", "cran"),
        entry_id=raw.get("entry_id"),
        fixed_on=_as_date(raw.get("fixed_on")),
        introduced_in=raw.get("introduced_in"),
        introduced_on=_as_date(raw.get("introduced_on")),
        functions=list(raw.get("functions") or []),
        condition_probe=raw.get("condition_probe"),
        category=str(raw.get("category", "RESULT_CHANGING")).upper(),
        silent=bool(raw.get("silent", True)),
        severity=str(raw.get("severity", "MEDIUM")).upper(),
        status=str(raw.get("status", "CANDIDATE")).upper(),
        exposure=Exposure(
            scripts_calling_function=exposure_raw.get("scripts_calling_function"),
            scripts_meeting_probe=exposure_raw.get("scripts_meeting_probe"),
            papers_in_window=exposure_raw.get("papers_in_window"),
            papers_censored=exposure_raw.get("papers_censored"),
        ),
        magnitude=raw.get("magnitude"),
        directory=directory,
    )
    validate(bug)
    return bug


def write_bug(bug: Bug) -> Path:
    """Write a record back to its directory.

    Args:
        bug: The record to write.

    Returns:
        Path to the written `bug.yaml`.

    Raises:
        BugError: If the record has no directory or fails validation.
    """
    if bug.directory is None:
        raise BugError(f"{bug.id}: no directory to write to")
    validate(bug)
    bug.directory.mkdir(parents=True, exist_ok=True)
    path = bug.directory / "bug.yaml"
    path.write_text(yaml.safe_dump(bug.to_dict(), sort_keys=False, width=88))
    return path


def discover_bugs(root: Path) -> list[Bug]:
    """Find and parse every record under a root directory.

    Args:
        root: The `bugs/` directory.

    Returns:
        Records sorted most consequential first.
    """
    root = Path(root)
    if not root.exists():
        return []
    bugs = [load_bug(p.parent) for p in sorted(root.rglob("bug.yaml"))]
    return sorted(bugs, key=lambda b: (-b.rank[0], -b.rank[1], b.id))


def advance(bug: Bug, status: str) -> Bug:
    """Move a record forward in the lifecycle.

    Status only advances. A record that has already been verified is not
    demoted by a later re-probe, and re-running an earlier stage does not undo a
    verdict.

    Args:
        bug: The record to advance.
        status: The status the completed stage implies.

    Returns:
        The record, with `status` updated where that is a move forward.

    Raises:
        BugError: If `status` is not a known state.
    """
    if status not in STATUSES:
        raise BugError(f"{bug.id}: unknown status {status!r}")
    if status in TERMINAL_STATES or STAGE_OF[status] > bug.stage:
        bug.status = status
    return bug


def render_index(bugs: list[Bug]) -> str:
    """Render the record index as markdown.

    Args:
        bugs: All records.

    Returns:
        Markdown for `bugs/INDEX.md`.
    """
    verified = [b for b in bugs if b.status == "VERIFIED"]
    negative = [b for b in bugs if b.status in ("REFUTED", "NOT_REPRODUCED")]
    open_records = [b for b in bugs if not b.is_terminal]

    out = [
        "# Bug record",
        "",
        f"{len(bugs)} records: {len(verified)} verified, {len(negative)} refuted or "
        f"not reproduced, {len(open_records)} still open.",
        "",
        "Exposure is reported as a pair. `calls` counts scripts calling an",
        "affected function and is an upper bound; `probe` counts those also",
        "matching the bug's conditions probe. A probe is a regular expression",
        "over source text -- it shows a script *could* have met the triggering",
        "condition, never that it did. Neither number means much alone.",
        "",
        "| bug | severity | silent | calls | probe | papers | status |",
        "|---|---|---|---|---|---|---|",
    ]
    for bug in bugs:
        exposure = bug.exposure
        papers = exposure.papers_in_window
        cell = "--" if papers is None else str(papers)
        if bug.censored and papers is not None:
            cell = f"{cell}*"
        calls = exposure.scripts_calling_function
        probe = exposure.scripts_meeting_probe
        out.append(
            f"| [`{bug.id}`]({bug.id}/) | {bug.severity} | "
            f"{'yes' if bug.silent else 'no'} | "
            f"{'--' if calls is None else calls} | "
            f"{'--' if probe is None else probe} | "
            f"{cell} | {bug.status} |"
        )

    if any(b.censored for b in bugs):
        out += [
            "",
            "`*` marks a left-censored window: the version that introduced the",
            "defect is not recorded, so the paper count covers everything published",
            "before the fix rather than only the interval when the bug was live.",
            "Those counts are upper bounds, not comparable with uncensored ones.",
        ]

    if negative:
        out += [
            "",
            "## Did not survive verification",
            "",
            "Kept deliberately. A candidate that failed is the most expensive",
            "thing this pipeline produces, and deleting it invites the same lead",
            "being chased again.",
            "",
        ]
        for bug in negative:
            detail = bug.magnitude or "see NOTES.md"
            out.append(f"- `{bug.id}` -- {bug.status}: {detail}")

    return "\n".join(out) + "\n"
