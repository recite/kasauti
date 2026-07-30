"""Command-line entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from concord import report as report_module
from concord.compare import compare_case
from concord.loader import discover_cases, select_cases
from concord.runner import DEFAULT_TIMEOUT, run_case

ROOT = Path(__file__).resolve().parents[2]

#: Both tracks are discovered together: cross-implementation cases and verified
#: bug regressions are the same kind of object to the runner.
CASE_ROOTS = [ROOT / "cases", ROOT / "bugs"]


@click.group()
@click.version_option()
def main() -> None:
    """Differential testing for statistical software."""


@main.command("list")
@click.option("--cases-dir", type=click.Path(path_type=Path), default=None)
def list_cases(cases_dir: Path | None) -> None:
    """List discovered cases.

    Args:
        cases_dir: Directory holding case definitions.
    """
    for case in discover_cases(*([cases_dir] if cases_dir else CASE_ROOTS)):
        backends = ",".join(b.name for b in case.backends)
        click.echo(f"{case.family:16} {case.id:28} [{backends}]  {case.title}")


@main.command()
@click.argument("names", nargs=-1)
@click.option("--all", "run_all", is_flag=True, help="Run every case.")
@click.option("--cases-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--reports-dir", type=click.Path(path_type=Path), default=ROOT / "reports"
)
@click.option("--timeout", default=DEFAULT_TIMEOUT, show_default=True)
@click.option(
    "--strict",
    is_flag=True,
    help="Exit non-zero if any quantity diverges more than the case documents.",
)
def run(
    names: tuple[str, ...],
    run_all: bool,
    cases_dir: Path | None,
    reports_dir: Path,
    timeout: int,
    strict: bool,
) -> None:
    """Run cases and write a report.

    Args:
        names: Case ids or family names. Ignored when `run_all` is set.
        run_all: Run every discovered case.
        cases_dir: Directory holding case definitions.
        reports_dir: Where to write `latest.md` and `latest.json`.
        timeout: Per-process timeout in seconds.
        strict: Exit non-zero on any undocumented divergence.
    """
    roots = [cases_dir] if cases_dir else CASE_ROOTS
    selected = select_cases(roots, [] if run_all else list(names))
    if not selected:
        click.echo("no cases selected", err=True)
        sys.exit(1)

    runs, new_findings = [], []
    for spec in selected:
        click.echo(f"running {spec.id} ... ", nl=False)
        case_run = run_case(spec, timeout=timeout)
        runs.append(case_run)

        comparisons = compare_case(case_run.results, spec)
        fresh = [c for c in comparisons if c.is_new_finding]
        new_findings.extend(fresh)
        errored = [r.backend for r in case_run.results if r.status == "error"]

        state = f"{len(comparisons)} quantities"
        if fresh:
            state += f", {len(fresh)} UNDOCUMENTED"
        if errored:
            state += f", errors in {','.join(errored)}"
        click.echo(state)

    md_path, json_path = report_module.write(runs, reports_dir)
    click.echo(f"\nwrote {md_path.relative_to(ROOT)} and {json_path.relative_to(ROOT)}")

    if new_findings:
        click.echo(f"\n{len(new_findings)} undocumented divergence(s):")
        for c in new_findings:
            click.echo(
                f"  {c.quantity}: observed {c.verdict}, expected {c.expected} "
                f"(reldiff {c.max_reldiff:.2e})"
            )
        if strict:
            sys.exit(1)


@main.command()
@click.option("--cases-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--reports-dir", type=click.Path(path_type=Path), default=ROOT / "reports"
)
def report(cases_dir: Path | None, reports_dir: Path) -> None:
    """Re-render the report from results already on disk, without re-running.

    Args:
        cases_dir: Directory holding case definitions.
        reports_dir: Where to write the report.
    """
    from concord.runner import CaseRun
    from concord.schema import Result

    runs = []
    for spec in discover_cases(*([cases_dir] if cases_dir else CASE_ROOTS)):
        results = []
        for backend in spec.backends:
            path = spec.directory / f"results.{backend.name}.json"
            if path.exists():
                results.append(Result.load(path))
        if results:
            runs.append(CaseRun(spec=spec, results=results))

    if not runs:
        click.echo("no results on disk; run `concord run --all` first", err=True)
        sys.exit(1)

    md_path, _ = report_module.write(runs, reports_dir)
    click.echo(f"wrote {md_path}")


if __name__ == "__main__":
    main()


@main.group()
def bug() -> None:
    """Work with the bug record."""


@bug.command("index")
@click.option("--bugs-dir", type=click.Path(path_type=Path), default=ROOT / "bugs")
def bug_index(bugs_dir: Path) -> None:
    """Validate every record and regenerate INDEX.md.

    Args:
        bugs_dir: Directory holding bug records.
    """
    from concord.archaeology.bugs import discover_bugs, render_index

    records = discover_bugs(bugs_dir)
    if not records:
        click.echo(f"no records under {bugs_dir}", err=True)
        sys.exit(1)
    (Path(bugs_dir) / "INDEX.md").write_text(render_index(records))
    click.echo(f"validated {len(records)} record(s), wrote {bugs_dir}/INDEX.md")


@bug.command("status")
@click.option("--bugs-dir", type=click.Path(path_type=Path), default=ROOT / "bugs")
def bug_status(bugs_dir: Path) -> None:
    """Print every record's pipeline state.

    Args:
        bugs_dir: Directory holding bug records.
    """
    from concord.archaeology.bugs import discover_bugs

    records = discover_bugs(bugs_dir)
    click.echo(f"{'bug':44} {'sev':7} {'calls':>6} {'probe':>6} {'papers':>7} status")
    for record in records:
        exposure = record.exposure
        calls = exposure.scripts_calling_function
        probe = exposure.scripts_meeting_probe
        papers = exposure.papers_in_window
        click.echo(
            f"{record.id:44} {record.severity:7} "
            f"{'--' if calls is None else calls:>6} "
            f"{'--' if probe is None else probe:>6} "
            f"{'--' if papers is None else papers:>7} "
            f"{record.status}"
        )


@bug.command("probe")
@click.argument("bug_id")
@click.option("--bugs-dir", type=click.Path(path_type=Path), default=ROOT / "bugs")
@click.option(
    "--call-sites",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/call_sites.csv",
)
def bug_probe(bug_id: str, bugs_dir: Path, call_sites: Path) -> None:
    """Narrow a record's exposure by its conditions probe.

    Args:
        bug_id: Record to probe.
        bugs_dir: Directory holding bug records.
        call_sites: Extracted call sites CSV.
    """
    from concord.archaeology.bugs import advance, load_bug, write_bug
    from concord.archaeology.link import load_call_index, probe_exposure, write_exposure

    record = load_bug(Path(bugs_dir) / bug_id)
    result = probe_exposure(
        record.functions, record.condition_probe, load_call_index(call_sites)
    )

    write_exposure(result, record.directory / "exposure.csv")
    record.exposure.scripts_calling_function = len(result.calling)
    record.exposure.scripts_meeting_probe = len(result.matching)
    write_bug(advance(record, "PROBED"))

    click.echo(
        f"{bug_id}: {len(result.calling)} call the function, "
        f"{len(result.matching)} match the probe "
        f"({result.narrowing:.0%})"
    )
    if result.unreadable:
        click.echo(f"  {len(result.unreadable)} script(s) could not be read")


@bug.command("papers")
@click.argument("bug_id")
@click.option("--bugs-dir", type=click.Path(path_type=Path), default=ROOT / "bugs")
@click.option(
    "--datasets-dir",
    type=click.Path(path_type=Path),
    default=Path.home() / "Documents/GitHub/softverse/data/datasets",
)
@click.option("--enrich/--no-enrich", default=False, help="Fetch titles from the APIs.")
def bug_papers(bug_id: str, bugs_dir: Path, datasets_dir: Path, enrich: bool) -> None:
    """Resolve a record's exposed scripts to the papers they came from.

    Args:
        bug_id: Record to link.
        bugs_dir: Directory holding bug records.
        datasets_dir: softverse's per-journal dataset tables.
        enrich: Whether to fetch titles from the Dataverse and Zenodo APIs.
    """
    import csv as _csv

    from concord.archaeology.bugs import advance, load_bug, write_bug
    from concord.archaeology.papers import enrich as enrich_paper
    from concord.archaeology.papers import (
        link_scripts,
        load_dataverse_index,
        write_papers,
    )

    record = load_bug(Path(bugs_dir) / bug_id)
    exposure_csv = record.directory / "exposure.csv"
    if not exposure_csv.exists():
        click.echo(f"{bug_id}: run `concord bug probe {bug_id}` first", err=True)
        sys.exit(1)

    with exposure_csv.open(newline="") as handle:
        scripts = [
            row["script"]
            for row in _csv.DictReader(handle)
            if row["matches_probe"] == "True"
        ]

    linkage = link_scripts(scripts, load_dataverse_index(datasets_dir))
    if enrich:
        for paper in linkage.papers:
            enrich_paper(paper, ROOT / "data/cache/papers")

    in_window = linkage.in_window(record.fixed_on, record.introduced_on)
    write_papers(
        linkage,
        record.directory / "papers.csv",
        record.fixed_on,
        record.introduced_on,
    )
    record.exposure.papers_in_window = len(in_window)
    if record.censored:
        record.exposure.papers_censored = len(in_window)
    write_bug(advance(record, "LINKED"))

    click.echo(
        f"{bug_id}: {len(scripts)} script(s) -> {len(linkage.papers)} archive(s), "
        f"{len(in_window)} published before the fix"
        + (" (window left-censored)" if record.censored else "")
    )
    if linkage.by_source:
        click.echo(f"  by source: {linkage.by_source}")
    if linkage.unresolved:
        click.echo(f"  {len(linkage.unresolved)} script(s) from an unindexed source")
    if linkage.undated():
        click.echo(f"  {len(linkage.undated())} archive(s) with no publication date")
