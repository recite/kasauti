"""Command-line entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from kasauti import report as report_module
from kasauti.compare import compare_case
from kasauti.loader import discover_cases, select_cases
from kasauti.runner import DEFAULT_TIMEOUT, run_case

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
    from kasauti.runner import CaseRun
    from kasauti.schema import Result

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
    if enrich:
        for paper in linkage.papers:
            enrich_paper(paper, ROOT / "data/cache/papers")

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


def base_shadow() -> set[str]:
    """Names base R exports, which a CRAN package may claim only when qualified.

    Returns:
        Every name exported by a package shipped with R.
    """
    from kasauti.archaeology.frame import base_exports

    return set().union(*base_exports(SHADOWING_BASE).values())


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


@main.group()
def frame() -> None:
    """Build the sampling frame: which packages, and which procedures."""


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


def _exposed_entries(
    cache_root: Path,
    call_sites: Path,
    packages: list[str] | None = None,
    language: str = "R",
):
    """Load the entries that have corpus exposure, with their exposure counts.

    Args:
        cache_root: Harvest cache directory.
        call_sites: Extracted call sites CSV.
        packages: Packages to mine. Defaults to the selected frame.
        language: `R` or `Python`. The two are mined separately because their
            call indexes are separate: matching a Python callee named `index`
            against R's export list attributes a pandas method to `plm`.

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
        shadowed, excluded = base_shadow(), None
    else:
        # Python's equivalent of NAMESPACE is the imported module itself, so
        # exports come from the harvest rather than from a second source. There
        # is no base-language export list to shadow against: a script calling a
        # builtin does not import it, so it never reaches the call index.
        exports = {p: set(harvest(p, "pypi", cache_root).exports) for p in packages}
        shadowed, excluded = set(), NON_COMPUTING_PYTHON

    bugs, funnel = build_bugs(
        entries, exports, index, qualified, shadowed=shadowed, excluded=excluded
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
