"""Split raw changelog text into dated, per-version entries.

R packages write changelogs in at least three formats -- `NEWS.Rd` markup, a
markdown `NEWS.md`, and a loose plain-text convention -- and no two packages agree
on the details. The parser recognizes all three and falls back to treating the
whole file as one undated block rather than returning nothing, so that a package
with an unusual format shows up as poorly parsed instead of silently bug-free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from concord.archaeology.harvest import Harvest

#: `\section{Changes in version 3.8-3 (2024-12-16)}`, and lme4's all-caps
#: `\section{CHANGES IN VERSION 2.0-6}`.
RD_SECTION = re.compile(
    r"\\section\{[^}]*?version\s+"
    r"(?P<version>[0-9][0-9A-Za-z.\-]*)"
    r"(?:[^}]*?(?P<date>\d{4}-\d{2}-\d{2}))?[^}]*\}",
    re.IGNORECASE,
)

#: `## sandwich 3.1-2` or `# metafor 5.0-1 (2026-04-26)`. Trailing text after the
#: date is allowed: metafor closes with a parenthesis.
MD_SECTION = re.compile(
    r"^#{1,4}\s+(?:[A-Za-z][\w.]*\s+)?v?"
    r"(?P<version>\d[0-9A-Za-z.\-]*)"
    r"(?:.*?(?P<date>\d{4}-\d{2}-\d{2}))?.*$",
    re.MULTILINE,
)

#: `Changes in version 2.4-1 (2019-03-04)`, and car's `Changes to Version 3.1-5`.
TXT_SECTION = re.compile(
    r"^[ \t]*changes?\s+(?:in|to|for)\s+(?:version)?\s*"
    r"(?P<version>\d[0-9A-Za-z.\-]*)"
    r"(?:.*?(?P<date>\d{4}-\d{2}-\d{2}))?",
    re.MULTILINE | re.IGNORECASE,
)

#: A line that is nothing but a version number, which is how mgcv's ChangeLog
#: separates releases. Restricted to the dashed CRAN form (`1.9-4`) rather than
#: any dotted number: an unrestricted version of this matched stray numeric lines
#: inside reStructuredText and, because detection picks whichever grammar matches
#: most, beat the correct grammar on scipy and numpy.
BARE_SECTION = re.compile(
    r"^[ \t]*(?P<version>\d+\.\d+-\d+[0-9A-Za-z.\-]*)[ \t]*$" r"(?P<date>)",
    re.MULTILINE,
)

#: quantreg's ChangeLog: `3.04 September 19 2001`, a version and a long-form date
#: on one line. The date is left to the release timeline rather than parsed.
VERDATE_SECTION = re.compile(
    r"^[ \t]*(?P<version>\d+\.\d+[-.]?\d*)[ \t]+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[ \t]+\d{1,2}?.*$"
    r"(?P<date>)",
    re.MULTILINE,
)

#: reStructuredText release notes, over an underline of `=`, `-`, `~`, or `^`.
#: Four projects, three heading conventions: `Version 1.3.2` (scikit-learn),
#: `Release 0.14.0` (statsmodels), and `SciPy 0.10.0 Release Notes` (scipy and
#: numpy). One leading word covers all three, since "Version" and "Release" are
#: themselves just words in that position.
RST_SECTION = re.compile(
    r"^[ \t]*[A-Za-z][\w.\-]*[ \t]+v?"
    r"(?P<version>\d[0-9A-Za-z.]*)"
    r"(?:[ \t]+release[ \t]+notes)?[ \t]*\n"
    r"[=~^\-]{3,}[ \t]*$"
    r"(?P<date>)",
    re.MULTILINE | re.IGNORECASE,
)

#: GNU-style ChangeLog: `2026-04-24  Sebastian Meyer  <...>`. Used by nlme and
#: other R-core packages. These carry a date but no version, so the version is
#: recovered by asking which release the date falls before.
GNU_SECTION = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+\S.*$(?P<version>)",
    re.MULTILINE,
)

#: `\item` in Rd, `-`/`*`/`o` bullets elsewhere.
RD_ITEM = re.compile(r"\\item\s*")
BULLET = re.compile(r"^[ \t]*[-*o•]\s+", re.MULTILINE)


@dataclass
class Entry:
    """One changelog bullet.

    Attributes:
        package: Package the entry belongs to.
        version: Version the entry was released in.
        released: Release date, taken from the release timeline where the
            changelog itself does not carry one.
        text: The bullet's prose, whitespace-normalized.
        index: Position within its version's section, for stable identifiers.
    """

    package: str
    version: str
    released: date | None
    text: str
    index: int

    @property
    def entry_id(self) -> str:
        """A stable identifier for this entry.

        Returns:
            `package@version#index`.
        """
        return f"{self.package}@{self.version}#{self.index}"


@dataclass
class ParseReport:
    """Coverage of parsing one package's changelog.

    Attributes:
        package: Package name.
        format: Which grammar matched: `rd`, `md`, `txt`, or `unstructured`.
        versions_found: Version sections the parser recognized.
        versions_released: Releases the registry knows about, the denominator.
        entries: The parsed entries.
        undated: Entries whose version could not be matched to a release date.
    """

    package: str
    format: str
    versions_found: int
    versions_released: int
    entries: list[Entry] = field(default_factory=list)
    undated: int = 0

    @property
    def version_coverage(self) -> float:
        """Share of released versions the changelog documents.

        A low value means the package releases more often than it explains
        itself, and its bug count should not be compared with a package that
        documents everything.

        Returns:
            A proportion, capped at 1.0.
        """
        if not self.versions_released:
            return 0.0
        return min(1.0, self.versions_found / self.versions_released)


def _strip_rd(text: str) -> str:
    """Remove Rd markup, keeping the prose.

    Args:
        text: Rd-formatted fragment.

    Returns:
        Plain text.
    """
    text = re.sub(
        r"\\(?:code|pkg|file|emph|bold|dQuote|sQuote|link)\{([^{}]*)\}", r"\1", text
    )
    text = re.sub(r"\\[a-zA-Z]+\{", " ", text)
    text = text.replace("}", " ").replace("{", " ")
    return re.sub(r"\s+", " ", text).strip()


def _normalize(text: str) -> str:
    """Collapse whitespace in a bullet.

    Args:
        text: Raw bullet text.

    Returns:
        Single-spaced text.
    """
    return re.sub(r"\s+", " ", text).strip()


#: Grammars in preference order. Ties go to the earlier entry, which puts the
#: explicit "changes in version X" forms ahead of the looser bare-version and
#: date-led ones -- those match aggressively and would otherwise win on packages
#: that also use a real section header.
GRAMMARS: list[tuple[str, re.Pattern[str]]] = [
    ("rd", RD_SECTION),
    ("md", MD_SECTION),
    ("txt", TXT_SECTION),
    ("rst", RST_SECTION),
    ("verdate", VERDATE_SECTION),
    ("bare", BARE_SECTION),
    ("gnu", GNU_SECTION),
]


def _detect(news: str) -> tuple[str, re.Pattern[str]]:
    """Choose the grammar that best matches a changelog.

    Args:
        news: Raw changelog text.

    Returns:
        A `(format_name, pattern)` pair. `unstructured` when nothing matches.
    """
    best_name, best_pattern, best_count = "unstructured", RD_SECTION, 0
    for name, pattern in GRAMMARS:
        count = len(pattern.findall(news))
        if count > best_count:
            best_name, best_pattern, best_count = name, pattern, count
    return best_name, best_pattern


def parse_news(harvest_result: Harvest) -> ParseReport:
    """Split a harvested changelog into entries.

    Args:
        harvest_result: The package's harvest.

    Returns:
        The parse report, including entries and coverage figures.
    """
    news = harvest_result.news_text
    release_dates = {
        r.version: r.released for r in harvest_result.releases if r.released
    }
    total_releases = len(harvest_result.releases)

    if not news.strip():
        return ParseReport(
            package=harvest_result.package,
            format="unstructured",
            versions_found=0,
            versions_released=total_releases,
        )

    fmt, pattern = _detect(news)
    matches = list(pattern.finditer(news))
    if not matches:
        # Some packages -- MASS is the clearest case -- keep a running bullet
        # list with no version headings at all. The changes are real and worth
        # classifying even though none of them can be dated, so they are kept as
        # version-less entries rather than collapsed into one opaque blob.
        bullets = [b for b in _split_bullets(news, "txt") if len(b) >= 12]
        return ParseReport(
            package=harvest_result.package,
            format="unstructured",
            versions_found=0,
            versions_released=total_releases,
            entries=[
                Entry(harvest_result.package, "unknown", None, text, index)
                for index, text in enumerate(bullets)
            ],
            undated=len(bullets),
        )

    timeline = sorted(
        ((r.released, r.version) for r in harvest_result.releases if r.released),
    )

    entries, undated = [], 0
    for position, match in enumerate(matches):
        start = match.end()
        end = (
            matches[position + 1].start() if position + 1 < len(matches) else len(news)
        )
        body = news[start:end]
        version = match.group("version") or ""

        released = release_dates.get(version) if version else None
        if released is None and match.groupdict().get("date"):
            try:
                released = date.fromisoformat(match.group("date"))
            except (ValueError, TypeError):
                released = None
        if not version and released is not None:
            # GNU-style logs date each change but never name a version. The
            # release that shipped a change is the first one dated on or after
            # it, which is exactly the version a user would have had to install
            # to receive the change.
            version = _release_containing(released, timeline)

        for index, bullet in enumerate(_split_bullets(body, fmt)):
            if len(bullet) < 12:
                continue
            if released is None:
                undated += 1
            entries.append(
                Entry(harvest_result.package, version, released, bullet, index)
            )

    # Counted from the entries rather than from the section headers: the
    # date-led grammars have no version in the header at all, and would
    # otherwise report a single empty one.
    return ParseReport(
        package=harvest_result.package,
        format=fmt,
        versions_found=len(
            {e.version for e in entries if e.version not in ("", "unknown")}
        ),
        versions_released=total_releases,
        entries=entries,
        undated=undated,
    )


def _release_containing(when: date, timeline: list[tuple[date, str]]) -> str:
    """Return the first release dated on or after a change.

    Args:
        when: Date the change was made.
        timeline: `(release_date, version)` pairs, sorted ascending.

    Returns:
        The version that shipped the change, or `"unreleased"` if the change
        postdates every known release.
    """
    for released, version in timeline:
        if released >= when:
            return version
    return "unreleased"


def _split_bullets(body: str, fmt: str) -> list[str]:
    """Split one version's section into individual bullets.

    Args:
        body: The section text.
        fmt: Grammar in use, which decides the bullet marker.

    Returns:
        Normalized bullet strings.
    """
    if fmt == "gnu":
        # GNU entries are tab-indented lines beginning with a file reference.
        pieces = re.split(r"\n(?=\t\*)", body)
        return [b for b in (_normalize(p.lstrip("\t* ")) for p in pieces) if b]

    if fmt == "rd":
        pieces = RD_ITEM.split(body)
        bullets = [_strip_rd(p) for p in pieces[1:]] if len(pieces) > 1 else []
        if not bullets:
            bullets = [_strip_rd(body)]
        return [b for b in bullets if b]

    pieces = BULLET.split(body)
    bullets = [_normalize(p) for p in pieces[1:]] if len(pieces) > 1 else []
    if not bullets:
        # Some packages use blank-line-separated paragraphs instead of bullets.
        bullets = [_normalize(p) for p in re.split(r"\n\s*\n", body)]
    return [b for b in bullets if b]
