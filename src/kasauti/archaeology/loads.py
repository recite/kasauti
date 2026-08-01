"""Record which packages each corpus script loads.

Attribution has been wrong four times in this project, always the same way: a
name was credited to a package the script never used. Base R's exports were
credited to `Matrix`, plotting names to `psych`, a package's own name in its
changelog prose to its constructor. Each was fixed by asking for more evidence
before counting a call.

This is the fourth and last of those rules, and the one the earlier fixes could
not reach. `fixef` is exported by six packages in the frame -- `brms`, `fixest`,
`lme4`, `nlme`, `plm`, `rstanarm` -- and none of them is base R or a
non-inferential package, so neither existing shadow rule applies. Of the 28
corpus scripts calling `fixef`, twelve load `nlme`, six load `lme4`, and two load
`fixest`. Counting all 28 against a `fixest` bug overstates it fourteenfold.

The evidence needed is simply which packages a script loads, which
`call_sites.csv` does not carry: `extract_r.R` emits callee names and a
`pkg::` qualifier, so `library(fixest)` and `library(dplyr)` are indistinguishable
there -- both are just a call to `library`.

Deliberately a text scan rather than a parse. A load is a lexical fact and the
patterns are unambiguous, so the R parser buys nothing here, and the scan runs
over 16,000 scripts in about a minute against several minutes for `getParseData`.
The one cost is that a commented-out `library(fixest)` counts, which errs toward
crediting exposure rather than hiding it -- the conservative direction for a
number reported as an upper bound.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

#: `library(pkg)`, `require(pkg)`, `requireNamespace("pkg")`, and `pkg::fn`.
#: R accepts the package name quoted or bare in the first three.
R_LOAD = re.compile(
    r"""(?:library|require|requireNamespace|loadNamespace)\s*\(\s*["']?([A-Za-z][\w.]*)"""
    r"""|([A-Za-z][\w.]*)\s*::"""
)

#: `import pkg`, `import pkg as alias`, `from pkg import ...`, `from pkg.sub
#: import ...`. Only the top-level distribution is recorded, since that is the
#: granularity the frame attributes at.
PYTHON_LOAD = re.compile(
    r"""^\s*import\s+([A-Za-z_][\w]*)|^\s*from\s+([A-Za-z_][\w]*)""", re.MULTILINE
)

#: Extensions treated as each language's source.
SUFFIXES = {"R": (".R", ".r"), "Python": (".py",)}


def loads_in(source: str, language: str) -> set[str]:
    """Extract the packages one script loads.

    Args:
        source: The script's text.
        language: `R` or `Python`.

    Returns:
        Package names, top-level only.
    """
    pattern = R_LOAD if language == "R" else PYTHON_LOAD
    found = set()
    for match in pattern.finditer(source):
        name = next((g for g in match.groups() if g), None)
        if name:
            found.add(name.split(".")[0] if language == "Python" else name)
    return found


def scan(roots: list[Path], language: str) -> dict[str, set[str]]:
    """Scan a corpus for package loads.

    Args:
        roots: Directories to walk.
        language: `R` or `Python`.

    Returns:
        Script path to the packages it loads. Unreadable files map to an empty
        set rather than being dropped, so a script that could not be scanned is
        distinguishable from one that loads nothing.
    """
    out: dict[str, set[str]] = {}
    for root in roots:
        for suffix in SUFFIXES[language]:
            for path in Path(root).rglob(f"*{suffix}"):
                try:
                    out[str(path)] = loads_in(
                        path.read_text(errors="replace"), language
                    )
                except OSError:
                    out[str(path)] = set()
    return out


def write_loads(index: dict[str, set[str]], path: Path) -> int:
    """Write the index as a long-format CSV.

    Args:
        index: Script path to packages loaded.
        path: Destination CSV.

    Returns:
        Number of rows written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["script", "package"])
        for script in sorted(index):
            for package in sorted(index[script]):
                writer.writerow([script, package])
                rows += 1
    return rows


def by_archive(index: dict[str, set[str]]) -> dict[str, set[str]]:
    """Roll per-script loads up to the archive that contains them.

    Replication archives are multi-file, and the common shape is a master script
    that loads the packages and then `source()`s the analysis. So a file calling
    `felm` without `library(lfe)` above it is ordinary, not evidence of anything:
    116 of the 245 scripts calling `felm` look like that.

    Args:
        index: Script path to the packages it loads.

    Returns:
        Directory to every package loaded by any script in it.
    """
    rolled: dict[str, set[str]] = defaultdict(set)
    for script, packages in index.items():
        rolled[str(Path(script).parent)] |= packages
    return dict(rolled)


def read_loads(path: Path) -> dict[str, set[str]]:
    """Read the index back.

    Args:
        path: The CSV written by `write_loads`.

    Returns:
        Script path to the packages it loads.
    """
    index: dict[str, set[str]] = defaultdict(set)
    with Path(path).open() as handle:
        for row in csv.DictReader(handle):
            index[row["script"]].add(row["package"])
    return dict(index)
