"""Join changelog entries to the replication scripts they could have affected.

A bug matters to a published result only if three things line up: the package was
loaded, the affected function was actually called, and the analysis was run while
the bug was live. This module narrows on the first two and reports the funnel at
every step, because the size of the drop is itself the result.

The one subtlety that dominates accuracy: the function a bug is *about* is one the
package exports, not one it merely mentions. A `survival` entry reading "uses both
unique and table in various places" is about `survfit`, not about `unique`. Taking
every name in the text at face value ranks `length` -- called by a third of the
corpus -- as the most affected function in the ecosystem.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from concord.archaeology.calls import read_call_sites
from concord.archaeology.frame import NON_COMPUTING, r_namespace_exports
from concord.archaeology.parse import Entry

#: Language asserting that a number the package previously returned was wrong.
#: Deliberately narrow: "improved", "changed", and "updated" are excluded because
#: they do not claim the old output was incorrect.
RESULT_CHANGING = re.compile(
    r"\b(incorrect(?:ly)?|erroneous(?:ly)?|wrong(?:ly)?|miscalculat\w*|"
    r"mis-?comput\w*|was not correct|were not correct|not correctly|"
    r"bug in|bug when|fixed a bug|off by|inconsisten\w*|"
    r"gave the wrong|returned the wrong|reported the wrong)\b",
    re.IGNORECASE,
)

#: Language marking a fix that could not have altered a published number: it
#: touched prose, packaging, or a message rather than a computation.
INERT = re.compile(
    r"\b(typo|spelling|documentation|vignette|CRAN check|NOTE from|"
    r"error message|warning message|help page|man page|Rd file|"
    r"broken (?:url|link)|reference[sd]? to|citation)\b",
    re.IGNORECASE,
)

#: Any identifier-shaped token. Changelogs name the affected function three ways
#: -- "bug in coxph()", "bug in `coxph`", and plain "Fix a bug in coxph" -- and
#: survival, the most thoroughly documented package in the frame, uses the third
#: most often. Matching bare identifiers and then intersecting with the package's
#: own exports gets all three without admitting English prose, since a word only
#: survives if the package actually exports it.
IDENTIFIER = re.compile(r"\b([A-Za-z][A-Za-z0-9._]+)\b")


@dataclass
class Bug:
    """A changelog entry judged to have changed results, with its blast radius.

    Attributes:
        entry: The changelog entry.
        functions: Affected functions, restricted to the package's own exports.
        fixed_in: Version that shipped the fix.
        fixed_on: Date that version was released.
        exposed_scripts: Corpus scripts calling any affected function.
    """

    entry: Entry
    functions: list[str]
    fixed_in: str
    fixed_on: date | None
    exposed_scripts: dict[str, set[str]] = field(default_factory=dict)

    @property
    def total_exposed(self) -> int:
        """Distinct scripts calling at least one affected function.

        Returns:
            The size of the union across affected functions.
        """
        return (
            len(set().union(*self.exposed_scripts.values()))
            if self.exposed_scripts
            else 0
        )


@dataclass
class Funnel:
    """Counts at each narrowing step, so the attrition is visible.

    Attributes:
        entries: Changelog entries parsed.
        result_changing: Entries whose text claims a wrong result.
        with_named_function: Of those, entries naming a function the package
            exports.
        with_corpus_exposure: Of those, entries whose function is called by at
            least one corpus script.
        exposed_scripts: Distinct scripts touched by any bug.
    """

    entries: int = 0
    result_changing: int = 0
    with_named_function: int = 0
    with_corpus_exposure: int = 0
    exposed_scripts: int = 0


def is_result_changing(text: str) -> bool:
    """Whether an entry claims a previously returned number was wrong.

    Args:
        text: The entry's prose.

    Returns:
        True when result-changing language is present and no inert marker is.
    """
    return bool(RESULT_CHANGING.search(text)) and not INERT.search(text)


def affected_functions(text: str, exports: set[str]) -> list[str]:
    """Extract the functions an entry is about.

    Two restrictions, each of which changes the ranking completely:

    * Only the owning package's exports. Otherwise the base-R utilities a
      changelog mentions in passing -- `length`, `unique`, `sum` -- swamp
      everything, because every script calls them.
    * Not the display and extraction layer. A fix to `etable`, fixest's LaTeX
      formatter, changes how a table renders, not what the coefficient is; left
      in, such fixes take every top slot because table formatters are called by
      every script that reports a regression.

    Args:
        text: The entry's prose.
        exports: Names the package exports.

    Returns:
        Sorted affected function names.
    """
    named = {m.group(1) for m in IDENTIFIER.finditer(text)}
    return sorted((named & exports) - NON_COMPUTING)


def build_bugs(
    entries: list[Entry],
    package_exports: dict[str, set[str]],
    call_index: dict[str, set[str]],
) -> tuple[list[Bug], Funnel]:
    """Turn parsed entries into ranked bugs with corpus exposure.

    Args:
        entries: All parsed changelog entries.
        package_exports: Package name to the set of names it exports.
        call_index: Function name to the corpus scripts calling it.

    Returns:
        A `(bugs, funnel)` pair, bugs sorted by exposure descending.
    """
    funnel = Funnel(entries=len(entries))
    bugs = []
    for entry in entries:
        if not is_result_changing(entry.text):
            continue
        funnel.result_changing += 1

        exports = package_exports.get(entry.package, set())
        functions = affected_functions(entry.text, exports)
        if not functions:
            continue
        funnel.with_named_function += 1

        exposed = {f: call_index[f] for f in functions if call_index.get(f)}
        if not exposed:
            continue
        funnel.with_corpus_exposure += 1

        bugs.append(
            Bug(
                entry=entry,
                functions=functions,
                fixed_in=entry.version,
                fixed_on=entry.released,
                exposed_scripts=exposed,
            )
        )

    funnel.exposed_scripts = len(
        set().union(*(s for b in bugs for s in b.exposed_scripts.values()))
        if bugs
        else set()
    )
    bugs.sort(key=lambda b: (-b.total_exposed, b.entry.entry_id))
    return bugs, funnel


def load_call_index(path: Path, language: str = "R") -> dict[str, set[str]]:
    """Build a function-to-scripts index from extracted call sites.

    Args:
        path: CSV written by `calls.write_call_sites`.
        language: Which language's calls to index.

    Returns:
        Function name to the set of script paths calling it.
    """
    index: dict[str, set[str]] = defaultdict(set)
    for site in read_call_sites(path):
        if site.language == language:
            index[site.fname].add(site.path)
    return dict(index)


def load_exports(packages: list[str]) -> dict[str, set[str]]:
    """Fetch each package's exported names from its installed namespace.

    Args:
        packages: Package names.

    Returns:
        Package name to its set of exports.
    """
    by_function = r_namespace_exports(packages)
    exports: dict[str, set[str]] = defaultdict(set)
    for function, owners in by_function.items():
        for owner in owners:
            exports[owner].add(function)
    return dict(exports)
