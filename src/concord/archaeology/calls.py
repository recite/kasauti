"""Extract function-call sites from a corpus of replication scripts.

softverse records which packages a script *imports*. That is too coarse for either
question here: a script that loads `sandwich` is affected by a bug in `vcovCL` only
if it calls `vcovCL`. This module recovers call sites, using each language's own
parser rather than regular expressions, because a regex cannot distinguish a call
from a string, a comment, or a variable that happens to share the name.

Scripts that fail to parse are counted and reported rather than dropped. In a
corpus of published replication archives that rate is itself a result.
"""

from __future__ import annotations

import ast
import csv
import subprocess
import tempfile
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

R_EXTRACTOR = Path(__file__).with_name("extract_r.R")


@dataclass
class CallSite:
    """One function called in one file.

    Attributes:
        path: Path to the script.
        fname: Bare function name as written, e.g. `vcovCL`.
        qualifier: Namespace qualifier if the call was written `pkg::fn`, else "".
        n: How many times it appears in that file.
        language: `R` or `Python`.
    """

    path: str
    fname: str
    qualifier: str
    n: int
    language: str


@dataclass
class ExtractionReport:
    """Coverage of one extraction pass.

    Attributes:
        language: Which language was scanned.
        files_seen: Files handed to the parser.
        files_parsed: Files the parser accepted.
        files_failed: Files the parser rejected.
        call_sites: The extracted calls.
    """

    language: str
    files_seen: int = 0
    files_parsed: int = 0
    files_failed: int = 0
    call_sites: list[CallSite] = field(default_factory=list)

    @property
    def parse_rate(self) -> float:
        """Share of files the parser accepted.

        Returns:
            A proportion in [0, 1], or 0.0 when no files were seen.
        """
        return self.files_parsed / self.files_seen if self.files_seen else 0.0


def _dotted_name(node: ast.AST) -> str | None:
    """Render an attribute or name chain as a dotted string.

    Args:
        node: The `func` of an `ast.Call`.

    Returns:
        A dotted name such as `sm.OLS`, or None if the callee is an expression
        rather than a name (e.g. `funcs[i]()`).
    """
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _import_bindings(tree: ast.Module) -> dict[str, str]:
    """Map every name a module binds to the module it came from.

    Python attribution is only as good as alias resolution: `sm.OLS` means
    statsmodels only because of `import statsmodels.api as sm` at the top, and
    a bare `OLS` means statsmodels only because of `from statsmodels.api import
    OLS`. Without this the name `index` or `time` is indistinguishable from a
    method on an arbitrary object.

    Args:
        tree: Parsed module.

    Returns:
        Local binding name to the dotted module path it resolves to.
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                bindings[alias.asname or alias.name] = node.module
    return bindings


def extract_python(paths: list[Path]) -> ExtractionReport:
    """Recover call sites from Python scripts via the `ast` module.

    The `qualifier` is the module the callee resolves to through the file's own
    imports, not the literal text before the dot. An unresolvable callee -- a
    method on a local object, say -- gets an empty qualifier and will not be
    attributed to any package.

    Args:
        paths: Script paths.

    Returns:
        The extraction report.
    """
    report = ExtractionReport(language="Python", files_seen=len(paths))
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            # Corpus scripts routinely contain invalid escape sequences that the
            # compiler warns about. Those warnings are about the scripts, not
            # about us, and would drown the output at corpus scale.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                tree = ast.parse(source)
        except (SyntaxError, ValueError, OSError, RecursionError):
            report.files_failed += 1
            continue
        report.files_parsed += 1

        bindings = _import_bindings(tree)
        counts: Counter[tuple[str, str]] = Counter()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _dotted_name(node.func)
            if dotted is None:
                continue
            parts = dotted.split(".")
            bare = parts[-1]
            root = parts[0]
            if root not in bindings:
                # Not traceable to an import: a method on a local object, or a
                # locally defined function. Left unattributed on purpose.
                qualifier = ""
            elif len(parts) == 1:
                # `from statsmodels.api import OLS` then a bare `OLS(...)`.
                qualifier = bindings[root]
            else:
                qualifier = ".".join([bindings[root], *parts[1:-1]])
            counts[(bare, qualifier)] += 1

        report.call_sites.extend(
            CallSite(str(path), fname, qualifier, n, "Python")
            for (fname, qualifier), n in counts.items()
        )
    return report


def extract_r(
    paths: list[Path], timeout: int = 3600, chunk_size: int = 500
) -> ExtractionReport:
    """Recover call sites from R scripts via R's own parser.

    Work is batched rather than run one process per file, which matters at corpus
    scale, but is chunked rather than run as a single process over everything: a
    script that crashes R takes down only its own chunk, and the loss is counted
    instead of silently ending the pass.

    Args:
        paths: Script paths.
        timeout: Seconds before a chunk's R process is killed.
        chunk_size: Files per R process.

    Returns:
        The merged extraction report.
    """
    report = ExtractionReport(language="R", files_seen=len(paths))
    for start in range(0, len(paths), chunk_size):
        chunk = paths[start : start + chunk_size]
        try:
            partial = _extract_r_chunk(chunk, timeout=timeout)
        except (RuntimeError, subprocess.TimeoutExpired):
            # The whole chunk is unaccounted for. Counting it as failed keeps the
            # coverage denominator honest.
            report.files_failed += len(chunk)
            continue
        report.files_parsed += partial.files_parsed
        report.files_failed += partial.files_failed
        report.call_sites.extend(partial.call_sites)
    return report


def _extract_r_chunk(paths: list[Path], timeout: int) -> ExtractionReport:
    """Run the R extractor over one batch of files.

    Args:
        paths: Script paths for this batch.
        timeout: Seconds before the R process is killed.

    Returns:
        The batch's extraction report.

    Raises:
        RuntimeError: If the R extractor exits non-zero.
    """
    report = ExtractionReport(language="R", files_seen=len(paths))
    if not paths:
        return report

    with tempfile.TemporaryDirectory() as tmp:
        listing = Path(tmp) / "files.txt"
        listing.write_text("\n".join(str(p) for p in paths))
        out = Path(tmp) / "calls.csv"

        proc = subprocess.run(  # noqa: S603
            ["Rscript", "--vanilla", str(R_EXTRACTOR), str(listing), str(out)],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"R extractor failed:\n{proc.stderr[-2000:]}")

        # The extractor's last line reads "parsed N files, M failed to parse".
        words = proc.stdout.replace(",", " ").split()
        numbers = [int(w) for w in words if w.isdigit()]
        if len(numbers) >= 2:
            report.files_failed = numbers[1]
            report.files_parsed = numbers[0] - numbers[1]

        if out.exists():
            with out.open(newline="") as handle:
                for row in csv.DictReader(handle):
                    report.call_sites.append(
                        CallSite(
                            path=row["file"],
                            fname=row["fname"],
                            qualifier=row["qualifier"],
                            n=int(row["n"]),
                            language="R",
                        )
                    )
    return report


def write_call_sites(reports: list[ExtractionReport], path: Path) -> None:
    """Write all call sites to a CSV.

    Args:
        reports: Extraction reports to merge.
        path: Destination CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["language", "path", "fname", "qualifier", "n"])
        for report in reports:
            for site in report.call_sites:
                writer.writerow(
                    [site.language, site.path, site.fname, site.qualifier, site.n]
                )


def read_call_sites(path: Path) -> list[CallSite]:
    """Read call sites back from CSV.

    Args:
        path: Source CSV written by `write_call_sites`.

    Returns:
        The call sites.
    """
    with Path(path).open(newline="") as handle:
        return [
            CallSite(
                path=row["path"],
                fname=row["fname"],
                qualifier=row["qualifier"],
                n=int(row["n"]),
                language=row["language"],
            )
            for row in csv.DictReader(handle)
        ]
