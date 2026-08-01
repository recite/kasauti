"""Trace a script back to the paper whose replication archive it came from.

Exposure counted in scripts is hard to read. Counted in papers it is a claim
about the literature, and it supplies the date the exposure window needs: a
replication archive published before a fix was released can only have been built
with a version that still had the bug.

The corpus has two sources with different identifier schemes, and they resolve
differently:

* **Dataverse** -- 12,054 repository directories, 3,782 R scripts. The directory
  name is the Harvard persistent id suffix, so `TBKLWV` joins to `DVN/TBKLWV` in
  softverse's own dataset tables. DOI, publication date, and publisher come from
  those files at no cost and with complete coverage.
* **Zenodo** -- 175 repository directories, 5,355 R scripts. The directory name
  is the record id, so the DOI is `10.5281/zenodo.<id>` by construction, but the
  date requires an API call. 175 calls, cached, is cheap.

Scripts from any other source resolve to nothing and are reported as
unresolvable rather than dropped: a paper count that quietly excludes part of the
corpus reads as coverage it does not have.
"""

from __future__ import annotations

import contextlib
import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

HARVARD_API = "https://dataverse.harvard.edu/api/datasets/export"
ZENODO_API = "https://zenodo.org/api/records"
USER_AGENT = "kasauti/0.1 (research; differential testing of statistical software)"

#: Lags in years between running an analysis and publishing it, reported as a
#: sensitivity curve. Zero stays the headline everywhere -- it is the only value
#: that assumes nothing -- but it is a *lower* bound rather than a neutral
#: estimate, because publication trails the work by one to four years in this
#: literature and testing publication dates against a fix date therefore
#: excludes analyses that were genuinely run while the bug was live.
#:
#: Measured: `sandwich` 3.0-2 links three dated archives and none is in window at
#: lag 0, one at lag 1, and all three at lag 2. No single lag is adopted as the
#: answer; the curve is reported so a reader can apply their own.
LAGS = (0, 1, 2, 3)

#: Replication archives are titled "Replication Data for: <paper title>" on
#: Dataverse and "Replication package for: <paper title>" on Zenodo. Stripping
#: the prefix recovers the paper's own title.
TITLE_PREFIX = re.compile(
    r"^\s*(replication|data|code|supplementary)[^:]{0,40}:\s*", re.IGNORECASE
)


@dataclass
class Paper:
    """A replication archive, standing in for the paper it accompanies.

    Attributes:
        repo_id: Directory name in the corpus, and the archive's local key.
        source: `dataverse` or `zenodo`.
        doi: Persistent identifier of the archive.
        published: Publication date of the archive.
        publisher: Repository that hosts it.
        journal: Journal slug, where the corpus records one.
        title: Paper title, once enriched.
        author: First author, once enriched.
    """

    repo_id: str
    source: str
    doi: str | None = None
    published: date | None = None
    publisher: str | None = None
    journal: str | None = None
    title: str | None = None
    author: str | None = None

    def analysed_on(self, lag_years: int = 0) -> date | None:
        """When the analysis behind this archive was plausibly run.

        Publication is a *late* proxy for analysis. Social science papers appear
        one to four years after the work is done, so testing the publication date
        against a fix date systematically excludes analyses that were genuinely
        run while the bug was live.

        Args:
            lag_years: Years between running the analysis and publishing it.

        Returns:
            The shifted date, or None when the archive is undated. February 29
            is walked back a day rather than raising, which costs nothing and
            avoids losing an archive to a calendar edge.
        """
        if self.published is None:
            return None
        if lag_years == 0:
            return self.published
        try:
            return self.published.replace(year=self.published.year - lag_years)
        except ValueError:
            return self.published.replace(
                year=self.published.year - lag_years, day=self.published.day - 1
            )

    def in_window(
        self,
        fixed_on: date | None,
        introduced_on: date | None,
        lag_years: int = 0,
    ) -> bool:
        """Whether this archive's analysis was run while the bug was live.

        Necessary, not sufficient: the analysis also had to meet the bug's
        triggering conditions. An archive with no recorded date is excluded --
        it cannot be placed on the timeline either way, and counting it would
        inflate the numerator.

        Args:
            fixed_on: Release date of the version that fixed the bug.
            introduced_on: Release date of the version that introduced it, or
                None when the window is left-censored.
            lag_years: Years to shift the publication date back by, to stand in
                for when the analysis was actually run. Zero -- the default and
                the reported headline -- assumes the analysis happened on
                publication day, which is the most conservative assumption
                available and therefore a lower bound rather than a neutral one.

        Returns:
            True when the analysis date falls inside the window.
        """
        analysed = self.analysed_on(lag_years)
        if analysed is None or fixed_on is None:
            return False
        if analysed >= fixed_on:
            return False
        return introduced_on is None or analysed >= introduced_on


def repo_id_from_path(path: str | Path) -> tuple[str, str] | None:
    """Recover the corpus source and repository id from a script path.

    Args:
        path: Path to a script inside the corpus.

    Returns:
        A `(source, repo_id)` pair, or None when the path is from a source with
        no known identifier scheme.
    """
    parts = Path(path).parts
    for index, part in enumerate(parts):
        if part in ("dataverse", "zenodo") and index + 1 < len(parts):
            return part, parts[index + 1]
    return None


def load_dataverse_index(datasets_dir: Path) -> dict[str, Paper]:
    """Build the Dataverse repo-id index from softverse's dataset tables.

    Args:
        datasets_dir: `softverse/data/datasets/`, one CSV per journal.

    Returns:
        Repository id to `Paper`, with DOI, date, and publisher filled in.
    """
    index: dict[str, Paper] = {}
    for path in sorted(Path(datasets_dir).glob("*.csv")):
        journal = path.stem.replace("_datasets", "")
        try:
            rows = list(csv.DictReader(path.open(newline="")))
        except (OSError, csv.Error):
            continue
        for row in rows:
            identifier = (row.get("identifier") or "").strip()
            if "/" not in identifier:
                continue
            repo_id = identifier.split("/", 1)[1]
            published = None
            raw_date = (row.get("publicationDate") or "").strip()
            if raw_date:
                try:
                    published = date.fromisoformat(raw_date[:10])
                except ValueError:
                    published = None
            index[repo_id] = Paper(
                repo_id=repo_id,
                source="dataverse",
                doi=(row.get("persistentUrl") or "").strip() or None,
                published=published,
                publisher=(row.get("publisher") or "").strip() or None,
                journal=journal,
            )
    return index


def zenodo_paper(repo_id: str) -> Paper:
    """Construct a Zenodo paper record without calling the API.

    The DOI follows from the record id, so an unenriched record is still useful
    for identifying the archive; only the date needs a fetch.

    Args:
        repo_id: Zenodo record id.

    Returns:
        A `Paper` with its DOI set.
    """
    return Paper(
        repo_id=repo_id,
        source="zenodo",
        doi=f"https://doi.org/10.5281/zenodo.{repo_id}",
        publisher="Zenodo",
    )


def _clean_title(raw: str | None) -> str | None:
    """Strip the replication-archive prefix from an archive title.

    Args:
        raw: The archive title.

    Returns:
        The paper's own title, or None.
    """
    if not raw:
        return None
    return TITLE_PREFIX.sub("", raw).strip().strip('"') or None


def enrich(
    paper: Paper, cache_dir: Path, timeout: int = 30, network: bool = True
) -> Paper:
    """Fetch title, author, and date for one archive, using a disk cache.

    Called only for archives attached to a record being promoted, so the request
    volume stays in the dozens rather than the thousands.

    Args:
        paper: The archive to enrich, mutated in place.
        cache_dir: Directory holding cached API responses.
        timeout: Seconds before giving up on a request.
        network: Whether a cache miss may go to the API. False reads the cache
            and stops, which is what makes re-running the linkage safe: a
            Zenodo archive's date exists nowhere but this cache, so a run that
            skipped it silently erased dates a previous run had resolved, and
            that erasure changed the paper counts.

    Returns:
        The same `Paper`, with whatever the cache or API supplied.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{paper.source}_{paper.repo_id}.json"

    if cached.exists():
        payload = json.loads(cached.read_text())
    elif not network:
        return paper
    else:
        try:
            if paper.source == "zenodo":
                response = requests.get(
                    f"{ZENODO_API}/{paper.repo_id}",
                    timeout=timeout,
                    headers={"User-Agent": USER_AGENT},
                )
            else:
                response = requests.get(
                    HARVARD_API,
                    params={
                        "exporter": "dataverse_json",
                        "persistentId": f"doi:10.7910/DVN/{paper.repo_id}",
                    },
                    timeout=timeout,
                    headers={"User-Agent": USER_AGENT},
                )
            response.raise_for_status()
            payload = response.json()
            cached.write_text(json.dumps(payload))
        except (requests.RequestException, ValueError):
            return paper

    if paper.source == "zenodo":
        meta = payload.get("metadata") or {}
        paper.title = _clean_title(meta.get("title"))
        creators = meta.get("creators") or []
        paper.author = creators[0].get("name") if creators else None
        raw_date = meta.get("publication_date")
        if raw_date and paper.published is None:
            with contextlib.suppress(ValueError):
                paper.published = date.fromisoformat(raw_date[:10])
        return paper

    try:
        fields = payload["datasetVersion"]["metadataBlocks"]["citation"]["fields"]
    except (KeyError, TypeError):
        return paper
    values = {f.get("typeName"): f.get("value") for f in fields}
    paper.title = _clean_title(values.get("title"))
    authors = values.get("author") or []
    if authors:
        paper.author = (authors[0].get("authorName") or {}).get("value")
    return paper


@dataclass
class PaperLinkage:
    """The result of resolving a set of scripts to archives.

    Attributes:
        papers: Distinct archives the scripts came from.
        unresolved: Scripts whose source has no known identifier scheme.
        by_source: How many archives came from each corpus source.
    """

    papers: list[Paper]
    unresolved: list[str]
    by_source: dict[str, int]

    def in_window(
        self,
        fixed_on: date | None,
        introduced_on: date | None,
        lag_years: int = 0,
    ) -> list[Paper]:
        """Archives whose analysis was plausibly run while the bug was live.

        Args:
            fixed_on: Release date of the fix.
            introduced_on: Release date of the introducing version, if known.
            lag_years: Years between analysis and publication.

        Returns:
            The subset inside the window.
        """
        return [
            p for p in self.papers if p.in_window(fixed_on, introduced_on, lag_years)
        ]

    def window_curve(
        self,
        fixed_on: date | None,
        introduced_on: date | None,
        lags: tuple[int, ...] = LAGS,
    ) -> dict[int, int] | None:
        """In-window counts across a range of analysis lags.

        The curve is the honest form of this measurement. A single number
        pretends to know when the work was done; the curve says how the answer
        depends on that, and lets a reader pick their own assumption.

        Args:
            fixed_on: Release date of the fix.
            introduced_on: Release date of the introducing version, if known.
            lags: Lags in years to evaluate.

        Returns:
            Lag to count, or None when the fix is undated -- in which case no
            archive can be placed on the timeline at any lag, and zero would
            read as "none affected" rather than "not determinable".
        """
        if fixed_on is None:
            return None
        return {lag: len(self.in_window(fixed_on, introduced_on, lag)) for lag in lags}

    def undated(self) -> list[Paper]:
        """Archives with no publication date.

        These cannot be placed on the timeline, so they are neither in nor out
        of any window and are reported separately.

        Returns:
            Archives lacking a date.
        """
        return [p for p in self.papers if p.published is None]


def link_scripts(paths: list[str], dataverse_index: dict[str, Paper]) -> PaperLinkage:
    """Resolve script paths to the archives that contain them.

    Args:
        paths: Script paths from the corpus.
        dataverse_index: Index from `load_dataverse_index`.

    Returns:
        The linkage, including the scripts that could not be resolved.
    """
    papers: dict[tuple[str, str], Paper] = {}
    unresolved: list[str] = []

    for path in paths:
        parsed = repo_id_from_path(path)
        if parsed is None:
            unresolved.append(str(path))
            continue
        source, repo_id = parsed
        key = (source, repo_id)
        if key in papers:
            continue
        if source == "dataverse":
            found = dataverse_index.get(repo_id)
            if found is None:
                unresolved.append(str(path))
                continue
            papers[key] = found
        else:
            papers[key] = zenodo_paper(repo_id)

    by_source: dict[str, int] = {}
    for source, _ in papers:
        by_source[source] = by_source.get(source, 0) + 1

    return PaperLinkage(
        papers=sorted(papers.values(), key=lambda p: (p.source, p.repo_id)),
        unresolved=sorted(unresolved),
        by_source=by_source,
    )


def write_papers(linkage: PaperLinkage, path: Path, bug_fixed_on, bug_introduced_on):
    """Write a bug's paper linkage to CSV.

    Args:
        linkage: The resolved linkage.
        path: Destination CSV.
        bug_fixed_on: Release date of the fix, for the window column.
        bug_introduced_on: Release date of the introducing version, if known.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["source", "repo_id", "doi", "published", "journal", "in_window", "title"]
        )
        for paper in linkage.papers:
            writer.writerow(
                [
                    paper.source,
                    paper.repo_id,
                    paper.doi or "",
                    paper.published.isoformat() if paper.published else "",
                    paper.journal or "",
                    paper.in_window(bug_fixed_on, bug_introduced_on),
                    paper.title or "",
                ]
            )
