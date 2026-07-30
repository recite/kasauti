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


@click.group()
@click.version_option()
def main() -> None:
    """Differential testing for statistical software."""


@main.command("list")
@click.option("--cases-dir", type=click.Path(path_type=Path), default=ROOT / "cases")
def list_cases(cases_dir: Path) -> None:
    """List discovered cases.

    Args:
        cases_dir: Directory holding case definitions.
    """
    for case in discover_cases(cases_dir):
        backends = ",".join(b.name for b in case.backends)
        click.echo(f"{case.family:16} {case.id:28} [{backends}]  {case.title}")


@main.command()
@click.argument("names", nargs=-1)
@click.option("--all", "run_all", is_flag=True, help="Run every case.")
@click.option("--cases-dir", type=click.Path(path_type=Path), default=ROOT / "cases")
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
    cases_dir: Path,
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
    selected = select_cases(cases_dir, [] if run_all else list(names))
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
@click.option("--cases-dir", type=click.Path(path_type=Path), default=ROOT / "cases")
@click.option(
    "--reports-dir", type=click.Path(path_type=Path), default=ROOT / "reports"
)
def report(cases_dir: Path, reports_dir: Path) -> None:
    """Re-render the report from results already on disk, without re-running.

    Args:
        cases_dir: Directory holding case definitions.
        reports_dir: Where to write the report.
    """
    from concord.runner import CaseRun
    from concord.schema import Result

    runs = []
    for spec in discover_cases(cases_dir):
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
