"""When a bug was reported, so that fixing it can be timed from something.

The study measures how long a defect *lived*. It cannot yet say how much of that
was spent undiscovered and how much was spent waiting, and those are different
facts about a maintainer and about a package. Splitting them needs a third date
between introduction and fix: when somebody said something.

Changelogs supply it more often than expected. **2,771 of 28,347 parsed entries
(9.8%)** cite an issue number, and an issue number plus a repository is a
timestamp. Two lookups get there:

* **package to repository**, from `URL` and `BugReports` in CRAN's own package
  database -- the same source the reverse-dependency counts come from, so no new
  authority is introduced;
* **issue number to creation date**, from the GitHub API through `gh`, which
  carries the user's own credentials rather than asking for a token here.

The number in a changelog is not always an issue in that repository. It can be a
version, a pull request, an R-Forge ticket, or a number in some other project's
tracker. So every match is checked against the one thing that must hold if it is
real: **an issue must be opened before the release that closes it**. A citation
that fails that is dropped and counted, because a latency computed from a
mismatched number is worse than a missing one -- it is a plausible number that is
about nothing.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

#: Ways a changelog refers to a tracker item. Deliberately narrow: a bare number
#: is far too common in prose to be evidence of anything.
ISSUE = re.compile(r"(?:#|issue\s+#?|gh-)(\d{1,6})\b", re.IGNORECASE)

#: A GitHub repository inside a URL field.
REPO = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git|/|$|,)")

#: Reads CRAN's package database for the fields that name a source repository.
#: Written without backslashes for the same reason `usage.REVERSE_SCRIPT` is: the
#: string crosses Python, a shell argument, and R's parser.
REPO_SCRIPT = """
db <- tools::CRAN_package_db()
out <- character()
for (i in seq_along(db$Package)) {
  for (field in c("URL", "BugReports")) {
    value <- db[[field]][[i]]
    if (is.na(value) || !nzchar(value)) next
    out <- c(out, paste(db$Package[[i]], value))
  }
}
writeLines(out)
"""


@dataclass
class Flag:
    """One changelog entry traced to the report that prompted it.

    Attributes:
        entry_id: The changelog entry, as `package@version#index`.
        package: Owning package.
        version: Release the entry belongs to.
        fixed_on: That release's date.
        repo: `owner/name` of the repository searched.
        issue: The issue number cited.
        flagged_on: When the issue was opened.
    """

    entry_id: str
    package: str
    version: str
    fixed_on: date | None
    repo: str
    issue: int
    flagged_on: date | None

    @property
    def response_days(self) -> int | None:
        """Days from the report to the release that carried the fix.

        Returns:
            The gap, or None when either date is missing.
        """
        if self.fixed_on is None or self.flagged_on is None:
            return None
        return (self.fixed_on - self.flagged_on).days

    @property
    def plausible(self) -> bool:
        """Whether the citation survives the one check that must hold.

        An issue cannot be opened by a release that already fixed it. A number
        failing this is not an issue in this repository -- it is a version, a
        pull request, or somebody else's ticket -- and the latency it would
        produce is a plausible number about nothing.

        Returns:
            True when the report precedes the release.
        """
        days = self.response_days
        return days is not None and days >= 0


def parse_repositories(output: str) -> dict[str, str]:
    """Map packages to GitHub repositories from CRAN's URL fields.

    Args:
        output: Lines of `package url`, as `REPO_SCRIPT` prints them.

    Returns:
        Package name to `owner/name`. A package naming several repositories
        keeps the first, which is `URL` before `BugReports` by construction.
    """
    found: dict[str, str] = {}
    for line in output.splitlines():
        package, _, value = line.partition(" ")
        if not value or package in found:
            continue
        match = REPO.search(value)
        if match:
            found[package] = f"{match.group(1)}/{match.group(2)}"
    return found


def fetch_repositories(timeout: int = 600) -> dict[str, str]:
    """Read every package's source repository from CRAN.

    Args:
        timeout: Seconds before giving up on R.

    Returns:
        Package name to `owner/name`.

    Raises:
        RuntimeError: If R produced nothing.
    """
    proc = subprocess.run(  # noqa: S603
        ["Rscript", "--vanilla", "-e", REPO_SCRIPT],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if not proc.stdout.strip():
        raise RuntimeError(f"CRAN_package_db() produced nothing\n{proc.stderr[-2000:]}")
    return parse_repositories(proc.stdout)


def cited(text: str) -> list[int]:
    """Issue numbers a changelog entry cites.

    Args:
        text: The entry's prose.

    Returns:
        The numbers, in order, without duplicates.
    """
    seen: list[int] = []
    for raw in ISSUE.findall(text):
        number = int(raw)
        if number not in seen:
            seen.append(number)
    return seen


def fetch_issue(repo: str, number: int, timeout: int = 60) -> date | None:
    """When an issue was opened.

    Uses `gh` rather than a bare HTTP call so the request carries the user's own
    credentials: unauthenticated GitHub allows 60 requests an hour, and this
    needs thousands.

    Args:
        repo: `owner/name`.
        number: Issue number.
        timeout: Seconds before giving up.

    Returns:
        The creation date, or None when the issue does not exist or cannot be
        read.
    """
    try:
        proc = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "gh",
                "api",
                f"repos/{repo}/issues/{number}",
                "--jq",
                ".created_at",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    stamp = proc.stdout.strip()
    if not stamp or proc.returncode != 0:
        return None
    try:
        return date.fromisoformat(stamp[:10])
    except ValueError:
        return None


class IssueCache:
    """Issue creation dates, fetched once.

    A miss is cached as much as a hit. Most misses are permanent -- the number
    was never an issue in this repository -- and re-asking GitHub about them
    every run would spend the rate limit on a known answer.

    Attributes:
        path: JSON file the dates are cached in.
        dates: `"repo#number"` to an ISO date or None.
    """

    def __init__(self, path: Path) -> None:
        """Load the cache.

        Args:
            path: JSON file to read and write.
        """
        self.path = path
        self.dates: dict[str, str | None] = (
            json.loads(path.read_text()) if path.exists() else {}
        )

    def get(self, repo: str, number: int, fetch=fetch_issue) -> date | None:
        """Return an issue's creation date, fetching on a miss.

        Args:
            repo: `owner/name`.
            number: Issue number.
            fetch: How to fetch, for tests.

        Returns:
            The creation date, or None.
        """
        key = f"{repo}#{number}"
        if key not in self.dates:
            found = fetch(repo, number)
            self.dates[key] = found.isoformat() if found else None
            self.write()
        stamp = self.dates[key]
        return date.fromisoformat(stamp) if stamp else None

    def write(self) -> None:
        """Persist the cache."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.dates, indent=2, sort_keys=True) + "\n")


FLAG_COLUMNS = [
    "entry_id",
    "package",
    "version",
    "fixed_on",
    "repo",
    "issue",
    "flagged_on",
    "response_days",
    "plausible",
]


def write_flags(flags: list[Flag], path: Path) -> None:
    """Write the tidy flagged table.

    Implausible rows are written too, flagged rather than dropped, so the share
    of citations that turned out not to be issues is visible instead of assumed
    away.

    Args:
        flags: One per resolved citation.
        path: Destination CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FLAG_COLUMNS)
        writer.writeheader()
        for flag in sorted(flags, key=lambda f: (f.package, f.entry_id, f.issue)):
            writer.writerow(
                {
                    "entry_id": flag.entry_id,
                    "package": flag.package,
                    "version": flag.version,
                    "fixed_on": flag.fixed_on or "",
                    "repo": flag.repo,
                    "issue": flag.issue,
                    "flagged_on": flag.flagged_on or "",
                    "response_days": (
                        "" if flag.response_days is None else flag.response_days
                    ),
                    "plausible": int(flag.plausible),
                }
            )
