"""Command-line entry point."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import click

# The harness lives in milaan, which asks the other question -- does R agree with
# Python today. A verified bug record is a version-regression case in exactly that
# sense (does this package agree with its own past self), so the two repositories
# share one runner rather than one copy each.
from milaan import report as report_module
from milaan.compare import compare_case
from milaan.loader import discover_cases, select_cases
from milaan.runner import DEFAULT_TIMEOUT, run_case

from kasauti.archaeology import library

ROOT = Path(__file__).resolve().parents[2]

#: Only bug records now. Cross-implementation comparisons moved to milaan; what
#: remains here are version regressions, one per verified bug, which the same
#: runner executes because they write the same result schema.
CASE_ROOTS = [ROOT / "bugs"]

#: What built and what refused to. Tracked, because the set of versions that will
#: not compile against a current toolchain is the hard limit on how far back this
#: study can reach, and rediscovering it costs a timeout per version.
LEDGER = ROOT / "data/builds.csv"

#: One JSON per screened changelog claim. Tracked: a claim that was tested and
#: moved nothing is a result, and the denominator is the point of screening.
SCREENS = ROOT / "screens"

#: One timeline per (package, probe): every release run, and every point where the
#: answer moved. The sampling unit the analysis rests on, so it is tracked.
SWEEPS = ROOT / "sweeps"


def _json_load(path: Path) -> dict:
    """Read a JSON file.

    Args:
        path: File to read.

    Returns:
        Its parsed contents.
    """
    import json as _json

    return _json.loads(path.read_text())


@click.group()
@click.version_option()
def main() -> None:
    """Changelog archaeology: which package bugs reached published work."""
    # Exported rather than written into each `case.yaml`, so a pinned backend can
    # say `${KASAUTI_RLIBS}/sandwich_2.4-0` and stay portable. Only defaulted:
    # setting it in the environment is how a second machine, or a scratch disk
    # with room for 700 builds, gets used without editing any case.
    os.environ.setdefault(library.ROOT_VARIABLE, str(library.DEFAULT_ROOT))


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
    from milaan.runner import CaseRun
    from milaan.schema import Result

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
        click.echo("no results on disk; run `kasauti run --all` first", err=True)
        sys.exit(1)

    md_path, _ = report_module.write(runs, reports_dir)
    click.echo(f"wrote {md_path}")


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
    from kasauti.archaeology.bugs import (
        discover_bugs,
        export_findings,
        render_by_paper,
        render_index,
    )

    records = discover_bugs(bugs_dir)
    if not records:
        click.echo(f"no records under {bugs_dir}", err=True)
        sys.exit(1)

    bugs_dir = Path(bugs_dir)
    (bugs_dir / "INDEX.md").write_text(render_index(records))
    (bugs_dir / "BY-PAPER.md").write_text(render_by_paper(records))
    export_findings(records, bugs_dir)

    languages = sorted({r.language for r in records})
    click.echo(
        f"validated {len(records)} record(s) across {', '.join(languages)}; "
        "wrote INDEX.md, BY-PAPER.md, findings.csv, findings.json"
    )


@bug.command("status")
@click.option("--bugs-dir", type=click.Path(path_type=Path), default=ROOT / "bugs")
def bug_status(bugs_dir: Path) -> None:
    """Print every record's pipeline state.

    Args:
        bugs_dir: Directory holding bug records.
    """
    from kasauti.archaeology.bugs import discover_bugs

    records = discover_bugs(bugs_dir)
    click.echo(f"{'bug':40} {'sev':7} {'calls':>6} {'probe':>6} {'papers':>7} status")
    for record in records:
        exposure = record.exposure
        calls = exposure.scripts_calling_function
        probe = exposure.scripts_meeting_probe
        papers = exposure.papers_in_window
        click.echo(
            f"{record.id:40} {record.severity:7} "
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
    from kasauti.archaeology.bugs import advance, load_bug, write_bug
    from kasauti.archaeology.link import load_call_index, probe_exposure, write_exposure

    record = load_bug(Path(bugs_dir) / bug_id, Path(bugs_dir))
    # The call index is per language: a Python bug must be probed against Python
    # call sites, or it silently finds nothing and reports zero exposure.
    language = {"r": "R", "python": "Python"}.get(record.language, "R")
    result = probe_exposure(
        record.functions,
        record.condition_probe,
        load_call_index(call_sites, language=language)[0],
        package=record.package,
        loads=archive_loads(LOADS_CSV),
        contested=contested_names(cache_root=ROOT / "data/cache"),
    )

    write_exposure(result, record.path / "exposure.csv")
    record.exposure.scripts_calling_function = len(result.calling)
    record.exposure.scripts_meeting_probe = len(result.matching)
    write_bug(advance(record, "PROBED"))

    click.echo(
        f"{bug_id}: {len(result.calling)} call the function, "
        f"{len(result.matching)} match the probe "
        f"({result.narrowing:.0%})"
    )
    if result.vendored:
        click.echo(
            f"  {len(result.vendored)} excluded as vendored library code "
            "(bundled site-packages, not author analysis)"
        )
    if result.unreadable:
        click.echo(f"  {len(result.unreadable)} script(s) could not be read")


@bug.command("rank")
@click.option("--bugs-dir", type=click.Path(path_type=Path), default=ROOT / "bugs")
@click.option(
    "--cache",
    "cache_file",
    type=click.Path(path_type=Path),
    default=ROOT / "data/classify/cache.json",
)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--call-sites",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/call_sites.csv",
)
@click.option(
    "--datasets-dir",
    type=click.Path(path_type=Path),
    default=Path.home() / "Documents/GitHub/softverse/data/datasets",
)
@click.option("--limit", type=int, default=15, show_default=True)
def bug_rank(bugs_dir, cache_file, cache_root, call_sites, datasets_dir, limit) -> None:
    """Order unverified candidates by how many papers they could have moved."""
    from kasauti.archaeology.bugs import discover_bugs
    from kasauti.archaeology.classify import ClassificationCache
    from kasauti.archaeology.harvest import harvest
    from kasauti.archaeology.papers import load_dataverse_index
    from kasauti.archaeology.rank import rank

    entries, exposure, _, _ = _exposed_entries(cache_root, call_sites)
    store = ClassificationCache(cache_file)
    already = {b.entry_id for b in discover_bugs(bugs_dir) if b.entry_id}

    candidates, packages = [], set()
    for entry in entries:
        found = store.get(entry.entry_id)
        if not found or entry.entry_id in already:
            continue
        if not found.moves_published_numbers or found.severity != "HIGH":
            continue
        packages.add(entry.package)
        candidates.append(
            (
                entry.entry_id,
                entry.package,
                found.functions,
                exposure.get(entry.entry_id, 0),
                entry.text,
                entry.released,
                found.introduced_version,
            )
        )

    releases = {
        p: [(r.version, r.released) for r in harvest(p, "cran", cache_root).releases]
        for p in sorted(packages)
    }
    index = load_dataverse_index(datasets_dir)
    dates = sorted(p.published for p in index.values() if p.published)

    ranked = rank(candidates, releases, dates)
    click.echo(
        f"{len(ranked)} unverified candidates against {len(dates)} dated archives\n"
    )
    click.echo(
        f"{'reach':>6} {'scripts':>7} {'in-window':>9}  {'entry':24s} "
        f"{'fixed':10s} window"
    )
    for c in ranked[:limit]:
        mark = "~" if c.censored else " "
        fixed = c.fixed_on.isoformat() if c.fixed_on else "--"
        click.echo(
            f"{c.expected:6.1f} {c.scripts:7d} {c.archives_in_window:9d}{mark} "
            f"{c.entry_id:24s} {fixed:10s} {c.window_basis}"
        )
    click.echo(
        "\n~ marks a left-censored window: no known start, so the count is an "
        "upper bound on\n  how much of the corpus the bug could have reached."
    )


@bug.command("bisect")
@click.argument("bug_id")
@click.option("--bugs-dir", type=click.Path(path_type=Path), default=ROOT / "bugs")
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option("--write/--no-write", default=True, help="Record the result on the bug.")
def bug_bisect(bug_id: str, bugs_dir: Path, cache_root: Path, write: bool) -> None:
    """Find when the bug was introduced, by running old versions.

    Args:
        bug_id: Record to bisect.
        bugs_dir: Directory holding bug records.
        cache_root: Harvest cache, for the release history.
        write: Whether to store the measured date on the record.
    """
    import json as _json

    import yaml as _yaml

    from kasauti.archaeology import library
    from kasauti.archaeology.bisect import (
        Probe,
        classify_run,
        run_backend,
        search,
    )
    from kasauti.archaeology.bugs import load_bug, write_bug
    from kasauti.archaeology.harvest import harvest

    record = load_bug(Path(bugs_dir) / bug_id, Path(bugs_dir))
    case = record.path / "case.yaml"
    if not case.exists():
        click.echo(f"{bug_id}: no case.yaml, so there is no reproducer", err=True)
        sys.exit(1)

    ledger = library.Ledger.load(LEDGER)
    spec = _yaml.safe_load(case.read_text())
    pinned = [
        b
        for b in spec.get("backends", [])
        if any(library.mentions_root(arg) for arg in b["cmd"])
    ]
    if not pinned:
        click.echo(
            f"{bug_id}: no version-pinned backend. This record distinguishes its "
            "versions by a flag or an environment, so there is nothing to install.",
            err=True,
        )
        sys.exit(1)

    references = {}
    for name in ("buggy", "fixed", "unadjusted", "adjusted"):
        path = record.path / f"results.{name}.json"
        if path.exists():
            references[name] = _json.loads(path.read_text())
    if len(references) < 2:
        click.echo(
            f"{bug_id}: needs two reference outputs to compare against", err=True
        )
        sys.exit(1)
    buggy_ref, fixed_ref = (references[k] for k in list(references)[:2])

    releases = harvest(record.package, "cran", cache_root).releases
    older: list[tuple[str, date | None]] = [
        (r.version, r.released)
        for r in releases
        if r.released and record.fixed_on and r.released < record.fixed_on
    ]
    if not older:
        click.echo(f"{bug_id}: no dated releases before the fix", err=True)
        sys.exit(1)

    click.echo(
        f"{bug_id}: bisecting {len(older)} releases before {record.fixed_in} "
        f"({older[0][0]} .. {older[-1][0]})"
    )

    def evaluate(version: str, released) -> Probe:
        lib, detail = library.ensure(record.package, version, ledger)
        if lib is None:
            return Probe(version, released, "UNEVALUABLE", f"build failed: {detail}")
        observed = run_backend(record.path, pinned[0]["cmd"], lib)
        outcome, why = classify_run(observed, buggy_ref, fixed_ref)
        return Probe(version, released, outcome, why)

    found = search(
        older,
        evaluate,
        on_probe=lambda p: click.echo(
            f"  {p.version:12s} {p.released!s:12s} {p.outcome}"
            + (f" -- {p.detail[:60]}" if p.detail else "")
        ),
    )

    click.echo(f"\n{len(found.probes)} version(s) tested")

    if found.first_buggy and write:
        # Recorded whether or not the introduction was bracketed: the oldest
        # version seen to be wrong is a floor on the lifetime either way. It is
        # kept out of `introduced_on`, because closing the window at a date the
        # bug may predate would hide papers rather than over-count them.
        record.oldest_buggy_on = found.first_buggy.released

    if not found.bracketed:
        if found.first_buggy:
            floor = ""
            if record.fixed_on and found.first_buggy.released:
                days = (record.fixed_on - found.first_buggy.released).days
                floor = f" -- wrong for at least {days / 365.25:.1f} years"
            click.echo(
                f"  buggy as far back as {found.first_buggy.version} "
                f"({found.first_buggy.released}), the oldest version that could be "
                f"evaluated{floor}"
            )
            click.echo(
                "  the introduction was not bracketed, so the window stays "
                "left-censored"
            )
            if write:
                write_bug(record)
        else:
            click.echo("  no version could be judged; nothing measured")
        return

    below, above = found.last_fixed, found.first_buggy
    if below is None or above is None:  # pragma: no cover - `bracketed` covers it
        return
    label = "not yet written" if below.outcome == "ABSENT" else "correct"
    click.echo(
        f"  {below.version} ({below.released}): {label}\n"
        f"  {above.version} ({above.released}): wrong"
    )
    if found.arrived_with_the_feature:
        click.echo(
            "  the bug arrived with the feature -- nobody broke this, it was "
            "wrong when written"
        )
    if record.fixed_on and found.introduced_on:
        days = (record.fixed_on - found.introduced_on).days
        click.echo(f"  lived {days} days ({days / 365.25:.1f} years) before the fix")

    if write:
        record.introduced_in = above.version
        record.introduced_on = found.introduced_on
        record.introduction_evidence = "bisected"
        write_bug(record)
        click.echo(f"  recorded on {bug_id}; re-run `bug papers` to tighten the window")


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

    from kasauti.archaeology.bugs import advance, load_bug, write_bug
    from kasauti.archaeology.papers import enrich as enrich_paper
    from kasauti.archaeology.papers import (
        link_scripts,
        load_dataverse_index,
        write_papers,
    )

    record = load_bug(Path(bugs_dir) / bug_id, Path(bugs_dir))
    exposure_csv = record.path / "exposure.csv"
    if not exposure_csv.exists():
        click.echo(f"{bug_id}: run `kasauti bug probe {bug_id}` first", err=True)
        sys.exit(1)

    with exposure_csv.open(newline="") as handle:
        scripts = [
            row["script"]
            for row in _csv.DictReader(handle)
            if row["matches_probe"] == "True"
        ]

    linkage = link_scripts(scripts, load_dataverse_index(datasets_dir))
    # The cache is always read; --enrich only decides whether a miss may hit the
    # network. A Zenodo archive's publication date exists nowhere else, so a run
    # that skipped the cache silently erased dates an earlier run had resolved --
    # and erasing a date moves the paper count, which is the study's headline.
    for paper in linkage.papers:
        enrich_paper(paper, ROOT / "data/cache/papers", network=enrich)

    # With no fix date, no archive can be placed relative to the bug at all.
    # Recording zero would read as "no papers affected" when the truth is "not
    # determinable" -- the same conflation the censored bucket exists to avoid.
    undated_fix = record.fixed_on is None
    in_window = linkage.in_window(record.fixed_on, record.introduced_on)
    write_papers(
        linkage,
        record.path / "papers.csv",
        record.fixed_on,
        record.introduced_on,
    )
    record.exposure.papers_in_window = None if undated_fix else len(in_window)
    if record.censored and not undated_fix:
        record.exposure.papers_censored = len(in_window)
    # Publication is a late proxy for analysis, so the lag-0 count is a lower
    # bound rather than a neutral estimate. The curve reports how much the answer
    # depends on that, instead of picking a lag and presenting it as measured.
    record.exposure.papers_by_lag = linkage.window_curve(
        record.fixed_on, record.introduced_on
    )
    write_bug(advance(record, "LINKED"))

    if undated_fix:
        window = "window undeterminable: the changelog does not date the fix"
    else:
        window = f"{len(in_window)} published before the fix" + (
            " (window left-censored)" if record.censored else ""
        )
    click.echo(
        f"{bug_id}: {len(scripts)} script(s) -> {len(linkage.papers)} archive(s), "
        f"{window}"
    )
    if record.exposure.papers_by_lag:
        curve = ", ".join(
            f"{lag}y: {n}" for lag, n in sorted(record.exposure.papers_by_lag.items())
        )
        click.echo(f"  by analysis lag ({curve})")
    if linkage.by_source:
        click.echo(f"  by source: {linkage.by_source}")
    if linkage.unresolved:
        click.echo(f"  {len(linkage.unresolved)} script(s) from an unindexed source")
    if linkage.undated():
        click.echo(f"  {len(linkage.undated())} archive(s) with no publication date")


#: The selected packages, written by `kasauti frame packages` and checked in.
PACKAGES_CSV = ROOT / "data/frame/packages.csv"

#: Base R packages, which have no CRAN tarball and so no changelog to mine, but
#: whose exports the frame still needs in order to attribute `lm` and `glm`.
BASE_IN_FRAME = ["stats"]

#: Every package shipped with R. A CRAN package that exports one of these names
#: is masking it, and a bare call is almost certainly base R's -- `Matrix`
#: exports `diag`, `head`, `crossprod`, and `rowMeans`, and a script calling
#: `diag()` on an ordinary matrix means none of them.
SHADOWING_BASE = [
    "base",
    "stats",
    "utils",
    "methods",
    "graphics",
    "grDevices",
    "tools",
]


def base_shadow(cache_root: Path | None = None) -> set[str]:
    """Names a computing package may claim only where the call is qualified.

    Two sources, and the second one was learned from a wrong answer. Base R is
    obvious: `Matrix` exports `diag` and `crossprod`, and a bare `diag()` means
    base R's. The non-inferential packages are the same problem one layer out.
    `alpha` is Cronbach's alpha in `psych` and colour transparency in `scales`,
    and in this corpus it is written `scales::alpha` eight times against
    `psych::alpha` six -- so counting bare `alpha()` put seven `psych` entries
    near the top of the shortlist on the strength of ggplot2 code.

    Nothing is lost by shadowing them: these are exactly the packages already
    excluded from the frame for not computing anything, so a name they own has
    no business being attributed to a package that does.

    Args:
        cache_root: Harvest cache root. Omit to shadow against base R only,
            which is all a unit test needs.

    Returns:
        Every shadowed name.
    """
    from kasauti.archaeology.frame import base_exports
    from kasauti.archaeology.harvest import harvest
    from kasauti.archaeology.taskviews import NON_INFERENTIAL, load_usage

    shadow = set().union(*base_exports(SHADOWING_BASE).values())
    if cache_root is None:
        return shadow

    usage = load_usage(ROOT / "data/frame/package_usage.csv")
    for package in sorted(NON_INFERENTIAL):
        if usage.get(package, 0) > 0:
            shadow |= set(harvest(package, "cran", cache_root).exports)
    return shadow


def classify_packages() -> list[str]:
    """The packages whose changelogs feed the classification queue.

    R only for now: the Python funnel has no export restriction, so its
    candidates are noisier, and mixing two different-quality samples into one
    rate makes the rate meaningless.

    Returns:
        Package names, most-used in the corpus first.
    """
    from kasauti.archaeology.taskviews import read_selection

    return [s.package for s in read_selection(PACKAGES_CSV)]


def screen_requests(fixtures: Path, packages: list[str] | None = None) -> list:
    """Read every screen the fixture catalogues declare.

    Args:
        fixtures: Directory holding one subdirectory per package.
        packages: Packages to read. Defaults to all of them.

    Returns:
        The requests, in catalogue order.
    """
    import yaml as _yaml

    from kasauti.archaeology.screen import Request

    requests = []
    for catalogue in sorted(Path(fixtures).glob("*/screens.yaml")):
        spec = _yaml.safe_load(catalogue.read_text())
        package = spec["package"]
        if packages and package not in packages:
            continue
        for row in spec.get("screens", []):
            requests.append(
                Request(
                    entry_id=row["entry"],
                    package=package,
                    fixed_in=str(row["fixed_in"]),
                    script=row["script"],
                    functions=list(row.get("functions") or []),
                    conditions=(row.get("conditions") or "").strip(),
                )
            )
    return requests


@main.group()
def screen() -> None:
    """Test a changelog claim against the release before the fix."""


@screen.command("queue")
@click.option("--fixtures", type=click.Path(path_type=Path), default=ROOT / "fixtures")
def screen_queue(fixtures: Path) -> None:
    """List every claim a fixture catalogue declares, and whether it has run.

    Args:
        fixtures: Directory holding the fixture catalogues.
    """
    requests = screen_requests(Path(fixtures))
    if not requests:
        click.echo(f"no screens declared under {fixtures}", err=True)
        sys.exit(1)

    click.echo(f"{'entry':24} {'script':24} {'verdict':16} detail")
    for request in requests:
        path = SCREENS / request.package / f"{request.slug}.json"
        if path.exists():
            found = _json_load(path)
            verdict, detail = found["verdict"], found["detail"]
        else:
            verdict, detail = "--", "not run"
        click.echo(f"{request.entry_id:24} {request.script:24} {verdict:16} {detail}")


@screen.command("run")
@click.argument("entries", nargs=-1)
@click.option("--fixtures", type=click.Path(path_type=Path), default=ROOT / "fixtures")
@click.option("--package", multiple=True, help="Screen a whole package.")
@click.option("--ledger", type=click.Path(path_type=Path), default=LEDGER)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option("--force", is_flag=True, help="Re-run screens already on disk.")
def screen_run(
    entries: tuple[str, ...],
    fixtures: Path,
    package: tuple[str, ...],
    ledger: Path,
    cache_root: Path,
    force: bool,
) -> None:
    """Run screens and write one JSON per claim.

    Args:
        entries: Changelog entry ids to screen. Defaults to everything declared.
        fixtures: Directory holding the fixture catalogues.
        package: Restrict to these packages.
        ledger: Build ledger.
        cache_root: Harvest cache, for the release history.
        force: Re-run screens that already have a result on disk.
    """
    import subprocess as _subprocess

    from kasauti.archaeology import screen as screening
    from kasauti.archaeology.harvest import harvest

    requests = screen_requests(Path(fixtures), list(package) or None)
    if entries:
        requests = [r for r in requests if r.entry_id in entries]
    if not requests:
        click.echo("no screens selected", err=True)
        sys.exit(1)

    book = library.Ledger.load(Path(ledger))
    generated: set[Path] = set()
    counts: dict[str, int] = {}

    for request in requests:
        out = SCREENS / request.package / f"{request.slug}.json"
        if out.exists() and not force:
            click.echo(f"{request.entry_id}: already screened (--force to re-run)")
            continue

        directory = Path(fixtures) / request.package
        data = directory / "data.csv"
        if directory not in generated:
            # Regenerated rather than tracked, on the same reasoning the cases
            # use: the generator is the artifact, the CSV is its output.
            _subprocess.run(  # noqa: S603
                ["python3", str(directory / "data.py")],  # noqa: S607
                cwd=directory,
                check=True,
                capture_output=True,
            )
            generated.add(directory)
        if not data.exists():
            click.echo(f"{request.entry_id}: {data} was not generated", err=True)
            sys.exit(1)

        releases = [
            (r.version, r.released)
            for r in harvest(request.package, "cran", Path(cache_root)).releases
        ]
        click.echo(f"{request.entry_id}: screening {request.fixed_in} ... ", nl=False)
        found = screening.run(request, directory, releases, book)
        found.write(SCREENS / request.package)
        counts[found.verdict] = counts.get(found.verdict, 0) + 1
        click.echo(
            f"{found.verdict} ({found.before} -> {found.after}) -- {found.detail}"
        )

    if counts:
        click.echo(
            "\n" + ", ".join(f"{n} {verdict}" for verdict, n in sorted(counts.items()))
        )


@screen.command("report")
@click.option("--fixtures", type=click.Path(path_type=Path), default=ROOT / "fixtures")
@click.option(
    "--out", type=click.Path(path_type=Path), default=ROOT / "docs/screening.md"
)
def screen_report(fixtures: Path, out: Path) -> None:
    """Write the screening coverage report.

    Args:
        fixtures: Directory holding the fixture catalogues.
        out: Markdown file to write.
    """
    from kasauti.archaeology.screen import Screen, render_report

    requests = screen_requests(Path(fixtures))
    screens = []
    for request in requests:
        path = SCREENS / request.package / f"{request.slug}.json"
        if not path.exists():
            continue
        screens.append(Screen.load(path))

    names = sorted({r.package for r in requests})
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(render_report(screens, len(requests), names))
    click.echo(f"wrote {out} -- {len(screens)} of {len(requests)} claim(s) screened")


@main.command("sweep")
@click.argument("packages", nargs=-1)
@click.option("--fixtures", type=click.Path(path_type=Path), default=ROOT / "fixtures")
@click.option("--probe", multiple=True, help="Probe scripts to run. Default: all.")
@click.option("--ledger", type=click.Path(path_type=Path), default=LEDGER)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--changes", type=click.Path(path_type=Path), default=ROOT / "data/changes.csv"
)
@click.option("--since", default=None, help="Skip releases before this ISO date.")
def sweep_command(
    packages: tuple[str, ...],
    fixtures: Path,
    probe: tuple[str, ...],
    ledger: Path,
    cache_root: Path,
    changes: Path,
    since: str | None,
) -> None:
    """Run every probe against every release, and record where numbers moved.

    Args:
        packages: Packages to sweep. Defaults to every one with a fixture.
        fixtures: Directory holding the fixtures.
        probe: Probe scripts to run. Defaults to every script the catalogue names.
        ledger: Build ledger.
        cache_root: Harvest cache, for the release history.
        changes: Tidy change table to write.
        since: Skip releases published before this date.
    """
    import subprocess as _subprocess

    import yaml as _yaml

    from kasauti.archaeology.harvest import harvest
    from kasauti.archaeology.sweep import sweep

    floor = date.fromisoformat(since) if since else None
    names = list(packages) or sorted(
        p.parent.name for p in Path(fixtures).glob("*/screens.yaml")
    )
    if not names:
        click.echo(f"no fixtures under {fixtures}", err=True)
        sys.exit(1)

    book = library.Ledger.load(Path(ledger))

    for name in names:
        directory = Path(fixtures) / name
        catalogue = _yaml.safe_load((directory / "screens.yaml").read_text())
        scripts = list(probe) or sorted(
            {row["script"] for row in catalogue.get("screens", [])}
        )
        _subprocess.run(  # noqa: S603
            ["python3", str(directory / "data.py")],  # noqa: S607
            cwd=directory,
            check=True,
            capture_output=True,
        )
        # An undated release cannot sit on a timeline, so it is excluded here
        # rather than swept and then silently unusable by the analysis.
        releases: list[tuple[str, date | None]] = [
            (r.version, r.released)
            for r in harvest(name, "cran", Path(cache_root)).releases
            if r.released and (floor is None or r.released >= floor)
        ]

        for script in scripts:
            click.echo(f"{name}/{script}: {len(releases)} release(s)")
            timeline = sweep(
                name,
                script,
                directory,
                releases,
                book,
                on_release=lambda o: click.echo(
                    f"  {o.version:12s} {o.state}"
                    + (f" -- {o.detail[:70]}" if o.detail else "")
                ),
            )
            timeline.write(SWEEPS / name)
            click.echo(
                f"  {timeline.observed} observed, {timeline.gaps} gap(s), "
                f"{len(timeline.changes)} change point(s)"
            )

    total = _rebuild_changes(Path(changes), SWEEPS)
    click.echo(f"\nwrote {changes} -- {total} change point(s) across every sweep")


def _rebuild_changes(path: Path, sweeps: Path) -> int:
    """Write the tidy change table from every timeline on disk.

    Rebuilt from the stored timelines rather than from the run that just
    finished, so sweeping one package does not silently drop the others out of
    the table the analysis reads.

    Args:
        path: Destination CSV.
        sweeps: Directory holding stored timelines.

    Returns:
        How many change points were written.
    """
    from kasauti.archaeology.sweep import Change, write_changes

    stored: list = []
    for file in sorted(sweeps.glob("*/*.json")):
        payload = _json_load(file)
        for row in payload["changes"]:
            stored.append(
                Change(
                    package=payload["package"],
                    probe=payload["probe"],
                    at=row["at"],
                    at_on=date.fromisoformat(row["at_on"]) if row["at_on"] else None,
                    after=row["after"],
                    after_on=(
                        date.fromisoformat(row["after_on"]) if row["after_on"] else None
                    ),
                    gaps=row["gaps"],
                    moved=row["moved"],
                    max_reldiff=row["max_reldiff"],
                )
            )
    write_changes(stored, path)
    return len(stored)


@main.command("episodes")
@click.option("--fixtures", type=click.Path(path_type=Path), default=ROOT / "fixtures")
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--out", type=click.Path(path_type=Path), default=ROOT / "data/episodes.csv"
)
@click.option(
    "--changes", type=click.Path(path_type=Path), default=ROOT / "data/changes.csv"
)
def episodes_command(
    fixtures: Path, cache_root: Path, out: Path, changes: Path
) -> None:
    """Turn every stored timeline into durations, with their censoring.

    Both tidy tables are written here, from the same pass over the same stored
    timelines, because an episode table that disagreed with the change table it
    was derived from would be the hardest kind of error to notice.

    Args:
        fixtures: Directory holding the fixture catalogues.
        cache_root: Harvest cache, for the changelog text.
        out: Destination episode CSV.
        changes: Destination change CSV.
    """
    import yaml as _yaml

    from kasauti.archaeology.episodes import build as build_episodes
    from kasauti.archaeology.episodes import write_episodes
    from kasauti.archaeology.harvest import harvest
    from kasauti.archaeology.parse import parse_news
    from kasauti.archaeology.sweep import Change, Observation

    # Which functions a probe exercises comes from the catalogue that declares
    # it, so the NEWS join asks about the same names the probe calls.
    exercised: dict[tuple[str, str], list[str]] = {}
    for catalogue in sorted(Path(fixtures).glob("*/screens.yaml")):
        spec = _yaml.safe_load(catalogue.read_text())
        for row in spec.get("screens", []):
            key = (spec["package"], row["script"])
            exercised.setdefault(key, []).extend(row.get("functions") or [])

    parsed: dict[str, list] = {}
    every = []
    for file in sorted(SWEEPS.glob("*/*.json")):
        payload = _json_load(file)
        package, probe = payload["package"], payload["probe"]
        if package not in parsed:
            parsed[package] = parse_news(
                harvest(package, "cran", Path(cache_root))
            ).entries

        observations = [
            Observation(
                version=o["version"],
                released=date.fromisoformat(o["released"]) if o["released"] else None,
                state=o["state"],
                detail=o["detail"],
                quantities=o["quantities"],
            )
            for o in payload["observations"]
        ]
        points = [
            Change(
                package=package,
                probe=probe,
                at=c["at"],
                at_on=date.fromisoformat(c["at_on"]) if c["at_on"] else None,
                after=c["after"],
                after_on=date.fromisoformat(c["after_on"]) if c["after_on"] else None,
                gaps=c["gaps"],
                moved=c["moved"],
                max_reldiff=c["max_reldiff"],
            )
            for c in payload["changes"]
        ]
        every.extend(
            build_episodes(
                points,
                observations,
                package,
                probe,
                entries=parsed[package],
                functions=sorted(set(exercised.get((package, probe), []))),
            )
        )

    write_episodes(every, Path(out))
    total = _rebuild_changes(Path(changes), SWEEPS)

    closed = [e for e in every if e.end == "CLOSED"]
    documented = [e for e in closed if e.closed_documented]
    click.echo(f"wrote {changes} -- {total} change point(s)")
    click.echo(f"wrote {out} -- {len(every)} episode(s) from {len(parsed)} package(s)")
    click.echo(
        f"  {len(closed)} closed, {len(every) - len(closed)} still running at the "
        f"last release\n  {len(documented)} of {len(closed)} closing changes are "
        "named in the changelog"
    )


#: The tables a reader is expected to reanalyse, in pipeline order. Hashed so a
#: claim in a write-up traces to the bytes it came from, and so a table
#: regenerated from a changed input cannot pass for the one that was analysed.
RELEASED = [
    "data/frame/packages.csv",
    "data/frame/cran_usage.csv",
    "data/frame/sample.csv",
    "data/frame/batteries.csv",
    "data/frame/sampling_frame.csv",
    "data/builds.csv",
    "data/changes.csv",
    "data/episodes.csv",
]


@main.command("manifest")
@click.option(
    "--out", type=click.Path(path_type=Path), default=ROOT / "data/manifest.json"
)
def manifest(out: Path) -> None:
    """Record the size and hash of every released table.

    Args:
        out: Manifest to write.
    """
    import hashlib
    import json as _json

    rows = {}
    for name in RELEASED:
        path = ROOT / name
        if not path.exists():
            rows[name] = {"present": False}
            continue
        raw = path.read_bytes()
        rows[name] = {
            "present": True,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            # Rows rather than bytes is what a reader checks against a paper, so
            # both travel: bytes catch a whitespace change, rows catch a dropped
            # observation.
            "rows": max(raw.count(b"\n") - 1, 0),
        }

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(_json.dumps(rows, indent=2, sort_keys=True) + "\n")

    missing = [name for name, row in rows.items() if not row["present"]]
    click.echo(f"wrote {out} -- {len(rows) - len(missing)} of {len(rows)} table(s)")
    for name in missing:
        click.echo(f"  missing: {name}")


@main.group()
def build() -> None:
    """Inspect what installs, and how far back it does."""


@build.command("audit")
@click.argument("packages", nargs=-1)
@click.option("--ledger", type=click.Path(path_type=Path), default=LEDGER)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=None,
    help="Also write the report as Markdown.",
)
def build_audit(
    packages: tuple[str, ...], ledger: Path, cache_root: Path, out: Path | None
) -> None:
    """Report how far back each package can be built, and what stops it.

    Args:
        packages: Packages to report on. Defaults to every package in the ledger.
        ledger: Build ledger.
        cache_root: Harvest cache, for the release history.
        out: Optional Markdown file to write.
    """
    from kasauti.archaeology.harvest import harvest

    book = library.Ledger.load(Path(ledger))
    adopted = library.adopt(book)
    if adopted:
        click.echo(f"adopted {adopted} version(s) already installed under the root\n")

    names = list(packages) or sorted({package for package, _ in book.builds})
    if not names:
        click.echo("nothing built yet", err=True)
        sys.exit(1)

    rows = []
    click.echo(
        f"{'package':16} {'releases':>8} {'tried':>6} {'built':>6} {'failed':>7} "
        f"{'floor':12} reaches back to"
    )
    for name in names:
        releases = harvest(name, "cran", Path(cache_root)).releases
        versions = [r.version for r in releases]
        counts = library.reach(name, versions, book)
        oldest = library.floor(name, versions, book)
        dated = next((r.released for r in releases if r.version == oldest), None)
        rows.append((name, len(versions), counts, oldest, dated))
        click.echo(
            f"{name:16} {len(versions):8d} {counts['tried']:6d} {counts['built']:6d} "
            f"{counts['failed']:7d} {oldest or '--':12} {dated or '--'}"
        )
    click.echo(
        "\nThe floor is the oldest version that builds against this toolchain, not "
        "the oldest\nthat exists. Everything before it is out of reach, and a bug "
        "living there can be\nbounded but not dated."
    )

    grouped = library.walls(book)
    if grouped:
        click.echo("\nWhat stopped the failures:")
        for description, pairs in grouped.items():
            click.echo(f"  {len(pairs):3d}  {description}")

    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(_render_reach(rows, grouped))
        click.echo(f"\nwrote {out}")


def _render_reach(rows: list, grouped: dict[str, list[tuple[str, str]]]) -> str:
    """Render the buildability report.

    Args:
        rows: One `(package, releases, counts, floor, floor_date)` per package.
        grouped: Failures grouped by the wall they hit.

    Returns:
        Markdown.
    """
    tried = sum(r[2]["tried"] for r in rows)
    built = sum(r[2]["built"] for r in rows)
    lines = [
        "# How far back this reaches",
        "",
        f"{tried} archived version(s) have been built against R "
        f"{library.r_version()}; **{built}** succeeded.",
        "",
        "Every backward-reaching measurement here -- screening a claim against the "
        "release before its fix, bisecting an introduction, sweeping a version "
        "history -- first has to install a decade-old source package against a "
        "current toolchain. Where that fails, the study stops, and the boundary is "
        "a property of today's compilers rather than of the package.",
        "",
        "## Floors",
        "",
        "| package | releases | tried | built | floor | reaches back to |",
        "|---|---|---|---|---|---|",
    ]
    for name, releases, counts, oldest, dated in rows:
        lines.append(
            f"| `{name}` | {releases} | {counts['tried']} | {counts['built']} | "
            f"{oldest or '--'} | {dated or '--'} |"
        )

    lines += [
        "",
        "Only versions this study actually asked for have been tried, so `tried` is "
        "not a sample of the history -- it is the set of releases some claim needed.",
        "",
        "## Walls",
        "",
        "| n | what stopped it |",
        "|---|---|",
        *(
            f"| {len(pairs)} | {description} |"
            for description, pairs in grouped.items()
        ),
        "",
        "**Building is not the only wall, and it is the one that announces itself.** "
        "`psych` 1.5.8 installs cleanly and then refuses to run: its own code says "
        '`if (class(x) == "try-error")`, which R has treated as an error since 4.2 '
        "when the condition has length greater than one. A package can therefore be "
        "buildable and unusable, so the floor above is a lower bound on how far back "
        "the archaeology reaches, never a promise.",
        "",
    ]
    return "\n".join(lines)


@main.group()
def frame() -> None:
    """Build the sampling frame: which packages, and which procedures."""


@frame.command("usage")
@click.option("--packages-csv", type=click.Path(path_type=Path), default=PACKAGES_CSV)
@click.option(
    "--cache",
    type=click.Path(path_type=Path),
    default=ROOT / "data/cache/usage.json",
)
@click.option(
    "--out", type=click.Path(path_type=Path), default=ROOT / "data/frame/cran_usage.csv"
)
@click.option(
    "--window",
    default="2024-01-01:2024-12-31",
    show_default=True,
    help="cranlogs period. Fixed and recorded so a count cannot drift.",
)
@click.option("--refresh", is_flag=True, help="Re-fetch rather than use the cache.")
def frame_usage(
    packages_csv: Path, cache: Path, out: Path, window: str, refresh: bool
) -> None:
    """Measure usage without reference to any one field.

    Args:
        packages_csv: Selected packages, for their corpus counts.
        cache: Where the raw measurements are cached.
        out: Destination CSV.
        window: cranlogs period for the download count.
        refresh: Re-fetch even when the cache exists.
    """
    from kasauti.archaeology.taskviews import read_selection
    from kasauti.archaeology.usage import load_usage, write_usage

    selected = read_selection(Path(packages_csv))
    names = [s.package for s in selected]
    corpus = {s.package: s.usage for s in selected}

    measured = load_usage(names, window, Path(cache), refresh=refresh)
    for package, entry in measured.items():
        entry.corpus = corpus.get(package, 0)

    rows = list(measured.values())
    write_usage(rows, Path(out))

    unknown = [r.package for r in rows if r.downloads == 0]
    click.echo(f"wrote {out} -- {len(rows)} package(s), window {window}")
    click.echo(
        "  corpus archives and CRAN reverse dependencies measure different "
        "things:\n  a package can be central to a field and depended on by "
        "nothing, or the reverse."
    )
    if unknown:
        click.echo(f"  {len(unknown)} package(s) reported no downloads: {unknown[:6]}")


@frame.command("sample")
@click.option(
    "--usage-csv",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/cran_usage.csv",
)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--out", type=click.Path(path_type=Path), default=ROOT / "data/frame/sample.csv"
)
@click.option("--per-stratum", default=3, show_default=True)
@click.option("--seed", default=20260801, show_default=True)
@click.option(
    "--max-releases",
    default=200,
    show_default=True,
    help="Skip packages whose history costs more than this to sweep.",
)
def frame_sample(
    usage_csv: Path,
    cache_root: Path,
    out: Path,
    per_stratum: int,
    seed: int,
    max_releases: int,
) -> None:
    """Draw the stratified sample of packages to sweep.

    Args:
        usage_csv: Field-neutral usage table.
        cache_root: Harvest cache, for release counts.
        out: Destination CSV.
        per_stratum: How many packages to draw from each non-certainty cell.
        seed: Random seed, recorded in the output.
        max_releases: Skip packages whose sweep would cost more than this.
    """
    from kasauti.archaeology.harvest import harvest
    from kasauti.archaeology.sample import Candidate, draw, stratify, write_sample
    from kasauti.archaeology.usage import read_usage

    table = read_usage(Path(usage_csv))
    candidates, skipped = [], []
    for package, entry in table.items():
        releases = len(harvest(package, "cran", Path(cache_root)).releases)
        if releases == 0 or releases > max_releases:
            skipped.append((package, releases))
            continue
        candidates.append(
            Candidate(
                package=package,
                corpus=entry.corpus,
                strong=entry.strong,
                compiled=entry.compiled,
                releases=releases,
            )
        )

    strata = stratify(candidates, per_stratum=per_stratum)
    selected = draw(strata, seed=seed)
    write_sample(selected, Path(out))

    click.echo(f"{'stratum':22} {'size':>5} {'take':>5} {'p':>7}  cost")
    for stratum in strata:
        cost = (
            sum(c.releases for c in stratum.members[: stratum.take])
            // max(stratum.take, 1)
            * stratum.take
        )
        click.echo(
            f"{stratum.name:22} {len(stratum.members):5d} {stratum.take:5d} "
            f"{stratum.probability:7.3f}  ~{cost} release(s)"
        )

    click.echo(
        f"\nwrote {out} -- {len(selected)} package(s), seed {seed}, "
        f"{sum(s.releases for s in selected)} release(s) to sweep"
    )
    if skipped:
        click.echo(
            f"  {len(skipped)} package(s) outside the design: no dated releases, "
            f"or more than {max_releases} of them"
        )


@frame.command("battery")
@click.argument("packages", nargs=-1)
@click.option(
    "--sample-csv",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/sample.csv",
)
@click.option(
    "--frame-csv",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/sampling_frame.csv",
)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/batteries.csv",
)
@click.option("--size", default=3, show_default=True, help="Probes per package.")
def frame_battery(
    packages: tuple[str, ...],
    sample_csv: Path,
    frame_csv: Path,
    cache_root: Path,
    out: Path,
    size: int,
) -> None:
    """Propose which functions to probe, from what the corpus calls.

    Args:
        packages: Packages to build batteries for. Defaults to the drawn sample.
        sample_csv: The stratified sample.
        frame_csv: Corpus-ranked procedure frame.
        cache_root: Harvest cache, for the shadow set.
        out: Destination CSV.
        size: How many functions to probe per package.
    """
    from kasauti.archaeology.battery import build as build_battery
    from kasauti.archaeology.battery import read_frame, write_batteries
    from kasauti.archaeology.frame import NON_COMPUTING
    from kasauti.archaeology.sample import read_sample
    from kasauti.archaeology.taskviews import load_usage

    names = list(packages) or [s.package for s in read_sample(Path(sample_csv))]
    corpus = read_frame(Path(frame_csv))
    shadowed = base_shadow(Path(cache_root))

    usage = load_usage(ROOT / "data/frame/package_usage.csv")
    batteries = [
        build_battery(name, corpus, shadowed, NON_COMPUTING, usage=usage, size=size)
        for name in names
    ]
    write_batteries(batteries, Path(out))

    click.echo(f"{'package':16} {'coverage':>9} {'calls':>7}  probes")
    for battery in sorted(batteries, key=lambda b: -b.covered):
        chosen = ", ".join(f"{p.function}({p.scripts:.0f})" for p in battery.probes)
        click.echo(
            f"{battery.package:16} {battery.coverage:9.1%} {battery.calls:7.0f}  "
            f"{chosen or '-- nothing survives the filters'}"
        )

    empty = [b.package for b in batteries if not b.probes]
    click.echo(f"\nwrote {out}")
    click.echo(
        "  coverage is the share of this package's corpus calls the battery "
        "reaches.\n  A change in a function no probe calls is invisible to the "
        "sweep, and this is\n  how much of that there is."
    )
    if empty:
        click.echo(
            f"  {len(empty)} package(s) yield no probe at all: {', '.join(empty)}.\n"
            "  A package the corpus never calls for computation cannot be swept "
            "for one,\n  which is the frame correcting itself rather than a gap."
        )


@frame.command("packages")
@click.option(
    "--views",
    "views_cache",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/taskviews.json",
)
@click.option(
    "--usage",
    "usage_csv",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/package_usage.csv",
)
@click.option("--out", type=click.Path(path_type=Path), default=PACKAGES_CSV)
@click.option(
    "--min-usage",
    type=int,
    default=10,
    help="Corpus archives a package must appear in to qualify.",
)
def frame_packages(views_cache, usage_csv, out, min_usage) -> None:
    """Select packages: CRAN Task Views intersected with corpus usage."""
    from kasauti.archaeology.taskviews import (
        INFERENTIAL_VIEWS,
        NON_INFERENTIAL,
        load_usage,
        load_views,
        select,
        write_selection,
    )

    members = load_views(views_cache)
    usage = load_usage(usage_csv)
    selected = select(members, usage, minimum=min_usage)
    write_selection(selected, out)

    pool = {p for packages in members.values() for p in packages}
    excluded = sorted(
        p for p in pool if p in NON_INFERENTIAL and usage.get(p, 0) >= min_usage
    )
    click.echo(
        f"{len(selected)} packages selected from {len(pool)} across "
        f"{len(INFERENTIAL_VIEWS)} task views, at >= {min_usage} corpus archives"
    )
    click.echo(f"  excluded as non-inferential: {', '.join(excluded)}")
    click.echo(f"  written to {out}")


#: Where the corpus of replication scripts lives. Outside this repository
#: because it is a gigabyte, and it belongs to softverse.
CORPUS = Path.home() / "Documents/GitHub/softverse/outputs/scripts"


@frame.command("extract")
@click.option("--corpus", type=click.Path(path_type=Path), default=CORPUS)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/call_sites.csv",
)
@click.option(
    "--report",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/extraction_report.json",
)
def frame_extract(corpus, out, report) -> None:
    """Recover every function call in the corpus, using each language's parser."""
    import json as _json

    from kasauti.archaeology.calls import extract_python, extract_r, write_call_sites

    corpus = Path(corpus)
    if not corpus.exists():
        click.echo(f"no corpus at {corpus}", err=True)
        sys.exit(1)

    r_files = sorted(p for s in (".R", ".r") for p in corpus.rglob(f"*{s}"))
    py_files = sorted(corpus.rglob("*.py"))
    click.echo(f"extracting from {len(r_files)} R and {len(py_files)} Python scripts")

    reports = [extract_r(r_files), extract_python(py_files)]
    write_call_sites(reports, Path(out))

    coverage = {}
    for item in reports:
        coverage[item.language] = {
            "files_seen": item.files_seen,
            "files_parsed": item.files_parsed,
            "files_failed": item.files_failed,
            "parse_rate": round(item.parse_rate, 4),
            "call_sites": len(item.call_sites),
        }
        # Scripts that fail to parse are counted, never dropped: the rate is a
        # property of the archives, and hiding it would overstate coverage.
        click.echo(
            f"{item.language:7s} {item.files_parsed}/{item.files_seen} parsed "
            f"({item.parse_rate:.1%}), {len(item.call_sites)} call sites"
        )
    Path(report).write_text(_json.dumps(coverage, indent=2))
    click.echo(f"wrote {out} and {report}")


@frame.command("loads")
@click.option("--corpus", type=click.Path(path_type=Path), default=CORPUS)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/package_loads.csv",
)
def frame_loads(corpus, out) -> None:
    """Record which packages each corpus script loads."""
    from kasauti.archaeology.loads import scan, write_loads

    corpus = Path(corpus)
    if not corpus.exists():
        click.echo(f"no corpus at {corpus}", err=True)
        sys.exit(1)

    index: dict[str, set[str]] = {}
    for language in ("R", "Python"):
        found = scan([corpus], language)
        index.update(found)
        loading = sum(1 for packages in found.values() if packages)
        click.echo(f"{language:7s} {len(found):6d} scripts, {loading} load a package")

    rows = write_loads(index, Path(out))
    click.echo(f"{rows} script-package pairs -> {out}")


@frame.command("harvest")
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option("--refresh", is_flag=True, help="Re-fetch even if cached.")
def frame_harvest(cache_root, refresh) -> None:
    """Fetch every selected package's changelog, releases, and exports."""
    from kasauti.archaeology.harvest import harvest
    from kasauti.archaeology.parse import parse_news

    packages = classify_packages() + BASE_IN_FRAME
    no_news, no_exports = [], []
    for index, package in enumerate(packages, start=1):
        if package in BASE_IN_FRAME:
            continue
        got = harvest(package, "cran", Path(cache_root), refresh=refresh)
        entries = len(parse_news(got).entries)
        if not got.news_text:
            no_news.append(package)
        if not got.exports:
            no_exports.append(package)
        click.echo(
            f"[{index:3d}/{len(packages)}] {package:20s} "
            f"{got.news_bytes:8d} bytes  {entries:5d} entries  "
            f"{len(got.exports):5d} exports"
        )

    click.echo(f"\n{len(packages) - 1} CRAN packages harvested")
    if no_news:
        click.echo(f"  no changelog ({len(no_news)}): {', '.join(no_news)}")
    if no_exports:
        click.echo(f"  no exports ({len(no_exports)}): {', '.join(no_exports)}")


@frame.command("build")
@click.option(
    "--call-sites",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/call_sites.csv",
)
@click.option(
    "--extraction",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/extraction_report.json",
)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--out-csv",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/sampling_frame.csv",
)
@click.option(
    "--out-md", type=click.Path(path_type=Path), default=ROOT / "docs/sampling-frame.md"
)
def frame_build(call_sites, extraction, cache_root, out_csv, out_md) -> None:
    """Rank the procedures the corpus calls, and write the frame."""
    import json as _json

    from kasauti.archaeology.calls import read_call_sites
    from kasauti.archaeology.frame import build_frame, render_report, write_frame

    coverage = _json.loads(Path(extraction).read_text())
    scripts_parsed = {lang: stats["files_parsed"] for lang, stats in coverage.items()}
    built = build_frame(
        read_call_sites(call_sites),
        scripts_parsed,
        Path(cache_root),
        packages=classify_packages() + BASE_IN_FRAME,
    )

    write_frame(built, Path(out_csv))
    Path(out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(out_md).write_text(render_report(built, coverage))
    click.echo(
        f"{len(built.rows)} procedures across {len(built.packages)} packages; "
        f"wrote {out_csv} and {out_md}"
    )
    if built.no_exports:
        click.echo(f"  no exports resolved: {', '.join(built.no_exports)}")


#: PyPI projects mined alongside the CRAN frame. Four, and that is not an
#: oversight in the selection: of 6,233 parsed Python scripts in the corpus, the
#: inferential imports are numpy (2,914), scipy (881), sklearn (254), and
#: statsmodels (46), and the next econometrics library, linearmodels, appears in
#: four. Adding Python packages would add changelog text and no exposure.
PYTHON_PACKAGES = ["statsmodels", "scikit-learn", "scipy", "numpy"]


#: Which packages each corpus script loads, built by `kasauti frame loads`.
LOADS_CSV = ROOT / "data/frame/package_loads.csv"


def archive_loads(path: Path = LOADS_CSV) -> dict[str, set[str]]:
    """Packages loaded anywhere inside each corpus archive.

    Args:
        path: The index written by `kasauti frame loads`.

    Returns:
        Directory to packages, or empty when the index has not been built --
        in which case the contested-name rule simply does not fire, which is
        the old over-counting behaviour rather than a silent zero.
    """
    from kasauti.archaeology.loads import by_archive, read_loads

    return by_archive(read_loads(path)) if Path(path).exists() else {}


def contested_names(cache_root: Path) -> set[str]:
    """Names more than one frame package exports.

    Computed from the export lists rather than listed, the same way the base-R
    and non-inferential shadows are.

    Args:
        cache_root: Harvest cache holding each package's exports.

    Returns:
        Contested names, excluding those base R already shadows.
    """
    from kasauti.archaeology.link import load_exports

    exports = load_exports(classify_packages() + BASE_IN_FRAME, cache_root)
    owners: dict[str, int] = {}
    for names in exports.values():
        for name in names:
            owners[name] = owners.get(name, 0) + 1
    return {n for n, count in owners.items() if count > 1} - base_shadow(cache_root)


def _exposed_entries(
    cache_root: Path,
    call_sites: Path,
    packages: list[str] | None = None,
    language: str = "R",
    loads_csv: Path = LOADS_CSV,
):
    """Load the entries that have corpus exposure, with their exposure counts.

    Args:
        cache_root: Harvest cache directory.
        call_sites: Extracted call sites CSV.
        packages: Packages to mine. Defaults to the selected frame.
        language: `R` or `Python`. The two are mined separately because their
            call indexes are separate: matching a Python callee named `index`
            against R's export list attributes a pandas method to `plm`.
        loads_csv: Per-script package loads, used to settle names more than one
            frame package exports.

    Returns:
        An `(entries, exposure, per_package, funnel)` tuple. `exposure` maps
        entry id to the number of corpus scripts calling an affected function;
        `per_package` maps package to `(entries_parsed, entries_exposed)`, so a
        package that contributes nothing is visible rather than assumed clean.
    """
    from kasauti.archaeology.frame import NON_COMPUTING_PYTHON
    from kasauti.archaeology.harvest import harvest
    from kasauti.archaeology.link import build_bugs, load_call_index, load_exports
    from kasauti.archaeology.parse import parse_news

    ecosystem = "cran" if language == "R" else "pypi"
    packages = packages or (classify_packages() if language == "R" else PYTHON_PACKAGES)
    entries, parsed = [], {}
    for package in packages:
        found = parse_news(harvest(package, ecosystem, cache_root)).entries
        parsed[package] = len(found)
        entries += found

    index, qualified = load_call_index(call_sites, language=language)
    if language == "R":
        exports = load_exports(packages + BASE_IN_FRAME, cache_root)
        shadowed, excluded = base_shadow(cache_root), None
        # A name more than one frame package exports needs the owner to have
        # been loaded.
        owners: dict[str, int] = {}
        for names in exports.values():
            for name in names:
                owners[name] = owners.get(name, 0) + 1
        contested = {n for n, count in owners.items() if count > 1} - shadowed
        loads = archive_loads(loads_csv)
    else:
        # Python's equivalent of NAMESPACE is the imported module itself, so
        # exports come from the harvest rather than from a second source. There
        # is no base-language export list to shadow against: a script calling a
        # builtin does not import it, so it never reaches the call index.
        exports = {p: set(harvest(p, "pypi", cache_root).exports) for p in packages}
        shadowed, excluded = set(), NON_COMPUTING_PYTHON
        contested, loads = set(), {}

    bugs, funnel = build_bugs(
        entries,
        exports,
        index,
        qualified,
        shadowed=shadowed,
        excluded=excluded,
        contested=contested,
        loads=loads,
    )
    exposure = {b.entry.entry_id: b.total_exposed for b in bugs}
    exposed = [b.entry for b in bugs]

    seen: dict[str, int] = {}
    for entry in exposed:
        seen[entry.package] = seen.get(entry.package, 0) + 1
    per_package = {p: (parsed[p], seen.get(p, 0)) for p in packages}
    return exposed, exposure, per_package, funnel


@main.group()
def classify() -> None:
    """Classify changelog entries, and measure the rules against the reading."""


@classify.command("pending")
@click.option("--limit", type=int, default=None, help="Maximum entries to queue.")
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=ROOT / "data/classify/pending.json",
)
@click.option(
    "--cache",
    "cache_file",
    type=click.Path(path_type=Path),
    default=ROOT / "data/classify/cache.json",
)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--call-sites",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/call_sites.csv",
)
@click.option(
    "--language",
    type=click.Choice(["R", "Python"]),
    default="R",
    help="Which funnel to queue from.",
)
def classify_pending(limit, out, cache_file, cache_root, call_sites, language) -> None:
    """Write the queue of entries still needing judgment.

    Args:
        limit: Maximum entries to queue.
        out: Destination JSON.
        cache_file: Classification cache.
        cache_root: Harvest cache directory.
        call_sites: Extracted call sites CSV.
        language: Which funnel to queue from.
    """
    import json as _json

    from kasauti.archaeology.classify import ClassificationCache, pending_payload

    entries, exposure, _, _ = _exposed_entries(
        cache_root, call_sites, language=language
    )
    store = ClassificationCache(cache_file)
    payload = pending_payload(entries, store, exposure, limit)

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(_json.dumps(payload, indent=2))
    click.echo(
        f"{len(entries)} exposed entries, {len(store)} already classified; "
        f"queued {len(payload)} to {out}"
    )


@classify.command("ingest")
@click.option(
    "--reviewed",
    type=click.Path(path_type=Path),
    default=ROOT / "data/classify/reviewed.json",
)
@click.option(
    "--cache",
    "cache_file",
    type=click.Path(path_type=Path),
    default=ROOT / "data/classify/cache.json",
)
def classify_ingest(reviewed, cache_file) -> None:
    """Merge reviewed classifications into the cache.

    Args:
        reviewed: JSON of reviewed records.
        cache_file: Classification cache.
    """
    import json as _json

    from kasauti.archaeology.classify import ClassificationCache, ingest_reviewed

    if not Path(reviewed).exists():
        click.echo(f"no reviewed file at {reviewed}", err=True)
        sys.exit(1)

    store = ClassificationCache(cache_file)
    merged, errors = ingest_reviewed(_json.loads(Path(reviewed).read_text()), store)
    click.echo(f"merged {merged} record(s); cache now holds {len(store)}")
    for error in errors:
        click.echo(f"  REJECTED {error}", err=True)
    if errors:
        sys.exit(1)


@classify.command("report")
@click.option(
    "--cache",
    "cache_file",
    type=click.Path(path_type=Path),
    default=ROOT / "data/classify/cache.json",
)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--call-sites",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/call_sites.csv",
)
@click.option(
    "--out", type=click.Path(path_type=Path), default=ROOT / "docs/classification.md"
)
def classify_report(cache_file, cache_root, call_sites, out) -> None:
    """Report the classification, and the rules' agreement with it.

    Args:
        cache_file: Classification cache.
        cache_root: Harvest cache directory.
        call_sites: Extracted call sites CSV.
        out: Destination markdown.
    """
    from kasauti.archaeology.classify import ClassificationCache, agreement

    entries, exposure, per_package, _ = _exposed_entries(cache_root, call_sites)
    store = ClassificationCache(cache_file)
    stats = agreement(entries, store)

    judged = stats.judged
    if not judged:
        click.echo(
            "nothing classified yet; run `kasauti classify pending` first", err=True
        )
        sys.exit(1)

    # Every entry is read by hand, so the queue is finite and the tail is real.
    # An unjudged tail is acceptable; an unreported one is not, because a
    # shortlist drawn from a partial reading looks exactly like a complete one.
    unjudged = [e for e in entries if not store.get(e.entry_id)]
    tail_below = (
        max(exposure.get(e.entry_id, 0) for e in unjudged) if unjudged else None
    )

    lines = [
        "# Classification of exposed changelog entries",
        "",
        f"{len(entries)} entries from {len(per_package)} R packages survive the",
        "funnel with corpus exposure. Of those, "
        f"**{judged}** have been read and judged.",
        "",
        "R only. The Python funnel has no export restriction, so its candidates are",
        "noisier; mixing two different-quality samples into one rate would make the",
        "rate meaningless.",
        "",
        "## Coverage",
        "",
        f"Entries are queued in descending corpus exposure, so the {judged} judged",
        "are the most-exposed ones. What is left unread is the tail:",
        "",
        f"* judged: **{judged}** of {len(entries)} ({judged / len(entries):.0%})",
        f"* unjudged: **{len(unjudged)}**"
        + (
            f", none exposed to more than **{tail_below}** corpus scripts"
            if tail_below is not None
            else ""
        ),
        "",
        "Every finding below is drawn from the judged set only. A bug sitting in",
        "the unjudged tail has not been ruled out; it has not been looked at.",
        "",
        "## What the reading changed",
        "",
        "The regular-expression layer agreed with the reading on "
        f"**{stats.rules_agreed}**",
        f"of {judged} entries and disagreed on **{stats.rules_disagreed}** "
        f"({stats.rules_disagreed / judged:.0%}).",
        "",
        "This is the validation a hand-coded gold set was going to provide. The rules",
        "are the baseline, the reading is the reference, and the disagreement rate is",
        "how much the reading was worth.",
        "",
        "| rules said | reading said | n |",
        "|---|---|---|",
    ]
    for pair, count in stats.confusion.items():
        rule, read = pair.split("->")
        mark = "" if rule == read else " **"
        lines.append(f"| {rule} | {read}{mark} | {count} |")

    lines += [
        "",
        "## Distribution",
        "",
        "| category | n |",
        "|---|---|",
    ]
    for name, count in sorted(stats.categories.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")

    silent = stats.silent
    lines += [
        "",
        f"Silent (quietly wrong, no error or warning): "
        f"**{silent.get(True, 0)}**; loud: {silent.get(False, 0)}.",
        "",
        f"**{stats.moves_published_numbers}** entries could have moved a number "
        "in a published table -- silent result-changing bugs, plus behaviour",
        "changes, which move results whether or not anyone calls them defects.",
        "",
        "## Shortlist: silent, result-changing, high severity",
        "",
        "The queue the verification pass draws from. Each of these changed an",
        "estimate, standard error, or p-value, under conditions an applied user",
        "could plausibly hit, with nothing to signal it had happened.",
        "",
        "| entry | functions | conditions |",
        "|---|---|---|",
    ]
    store_all = ClassificationCache(cache_file)
    shortlist = []
    for entry in entries:
        found = store_all.get(entry.entry_id)
        if (
            found
            and found.category == "RESULT_CHANGING"
            and found.silent
            and found.severity == "HIGH"
        ):
            shortlist.append((entry, found))
    shortlist.sort(key=lambda pair: pair[0].entry_id)
    for entry, found in shortlist:
        functions = ", ".join(f"`{f}`" for f in found.functions) or "--"
        lines.append(
            f"| `{entry.entry_id}` | {functions} | "
            f"{' '.join(found.conditions.split())} |"
        )
    lines.append("")

    # Packages that yielded nothing are the point of this table. Absence of
    # candidates is either a package that admits little or a package the harvest
    # could not read, and the two are indistinguishable unless both are listed.
    silent_packages = sorted(p for p, (_, found) in per_package.items() if not found)
    lines += [
        "## Yield by package",
        "",
        "Changelog candor varies enormously, and a package with no candidates has",
        "not been shown to be correct. Both columns travel together for that",
        "reason.",
        "",
        "| package | entries parsed | exposed candidates |",
        "|---|---|---|",
    ]
    for package, (parsed, exposed_n) in sorted(
        per_package.items(), key=lambda kv: (-kv[1][1], kv[0])
    ):
        lines.append(f"| `{package}` | {parsed} | {exposed_n} |")
    lines += [
        "",
        f"**{len(silent_packages)}** of {len(per_package)} packages yielded no "
        "exposed candidate at all.",
        "",
    ]

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(lines) + "\n")
    disagreed = stats.rules_disagreed
    click.echo(
        f"{judged}/{len(entries)} judged; rules disagreed on {disagreed} "
        f"({disagreed / judged:.0%}); wrote {out}"
    )


@main.command("dashboard")
@click.option(
    "--out", type=click.Path(path_type=Path), default=ROOT / "docs/index.html"
)
@click.option("--bugs-dir", type=click.Path(path_type=Path), default=ROOT / "bugs")
@click.option(
    "--cache",
    "cache_file",
    type=click.Path(path_type=Path),
    default=ROOT / "data/classify/cache.json",
)
@click.option(
    "--cache-root", type=click.Path(path_type=Path), default=ROOT / "data/cache"
)
@click.option(
    "--call-sites",
    type=click.Path(path_type=Path),
    default=ROOT / "data/frame/call_sites.csv",
)
def dashboard(out, bugs_dir, cache_file, cache_root, call_sites) -> None:
    """Render the record as a self-contained page for GitHub Pages.

    Args:
        out: Destination HTML file.
        bugs_dir: Directory holding bug records.
        cache_file: Classification cache.
        cache_root: Harvest cache directory.
        call_sites: Extracted call sites CSV.
    """
    from collections import Counter

    from kasauti.archaeology.bugs import discover_bugs
    from kasauti.archaeology.classify import ClassificationCache, agreement
    from kasauti.archaeology.harvest import harvest
    from kasauti.archaeology.parse import parse_news
    from kasauti.dashboard import Dashboard
    from kasauti.dashboard import write as write_page

    python_packages = ["statsmodels", "scikit-learn", "scipy", "numpy"]
    r_packages = classify_packages()
    py_entries = sum(
        len(parse_news(harvest(p, "pypi", cache_root)).entries) for p in python_packages
    )

    entries, exposure, _, counts_at = _exposed_entries(cache_root, call_sites)
    r_entries = counts_at.entries
    store = ClassificationCache(cache_file)
    stats = agreement(entries, store)
    counts = Counter(stats.categories)

    funnel = [
        {"label": "changelog entries (R)", "n": r_entries},
        {"label": "claim a wrong result", "n": counts_at.result_changing},
        {"label": "name a computing function", "n": counts_at.with_named_function},
        {"label": "called in the corpus", "n": len(entries)},
        {"label": "read as result-changing", "n": counts.get("RESULT_CHANGING", 0)},
    ]

    records = discover_bugs(bugs_dir)
    bug_rows = [
        {
            "id": b.id,
            "language": b.language,
            "severity": b.severity,
            "status": b.status,
            "calls": b.exposure.scripts_calling_function,
            "probe": b.exposure.scripts_meeting_probe,
            "papers": b.exposure.papers_in_window,
            "conditions": " ".join(b.conditions.split())[:150],
        }
        for b in records
    ]

    verified_entry_ids = {b.entry_id for b in records if b.entry_id}
    shortlist = []
    for entry in entries:
        found = store.get(entry.entry_id)
        if (
            found
            and found.category == "RESULT_CHANGING"
            and found.silent
            and found.severity == "HIGH"
            and entry.entry_id not in verified_entry_ids
        ):
            shortlist.append(
                {
                    "entry_id": entry.entry_id,
                    "exposure": exposure.get(entry.entry_id, 0),
                    "functions": ", ".join(found.functions),
                    "conditions": " ".join(found.conditions.split())[:130],
                }
            )
    shortlist.sort(key=lambda s: -s["exposure"])

    payload = Dashboard(
        corpus={
            "entries": r_entries + py_entries,
            "packages": len(r_packages) + len(python_packages),
            "note": (
                f"{r_entries:,} entries from {len(r_packages)} R packages and "
                f"{py_entries:,} from {len(python_packages)} Python projects. Only the "
                "R side is classified: the Python funnel has no export restriction, so "
                "mixing the two would make the rate meaningless."
            ),
        },
        funnel=funnel,
        classification={
            "confusion": [
                {"rules": k.split("->")[0], "read": k.split("->")[1], "n": v}
                for k, v in stats.confusion.items()
            ],
            "moves_published": stats.moves_published_numbers,
        },
        bugs=bug_rows,
        shortlist=shortlist[:20],
    )
    written = write_page(payload, out)
    click.echo(
        f"wrote {written} ({len(bug_rows)} records, {len(shortlist)} shortlisted)"
    )


if __name__ == "__main__":
    main()
