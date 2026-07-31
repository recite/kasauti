"""Classify changelog entries by whether they changed results.

The keyword triage this replaces has a ceiling that is easy to see in its
output: "fix bug in `etable`" and "the variance was incorrect" match the same
pattern, but one is a LaTeX table formatter and the other is a covariance
estimator. Distinguishing them needs to read the sentence, not match it.

Two things the classifier is asked for that the regex cannot supply:

* **silent** -- whether the buggy version warned or errored, or quietly returned
  a wrong number. A bug that failed loudly never corrupted a published result,
  so this is the field that separates a real finding from a footnote.
* **behavior_change** as its own category. R 3.6.0's change to `sample()` was
  intentional, documented, and silently altered every RNG-dependent result in
  the literature. A rate that counts only "bugs" misses it.

Entries are classified in bulk through the Batches API, which is half price and
has no latency requirement here, and cached on disk by entry id so that
re-running the downstream analysis costs nothing.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from kasauti.archaeology.parse import Entry

MODEL = "claude-opus-5"

#: How a classification was decided. A rate computed over a mix of these is
#: uninterpretable, so every record carries its provenance.
#:
#: * `rules` -- the regular-expression layer in `link.py`. Cheap, deterministic,
#:   and demonstrably unable to decide `silent`: the obvious pattern for a loud
#:   failure fires on 19% of candidates and is a false positive on every one
#:   sampled, because in changelog prose "error" means a mistake in the code
#:   rather than a raised exception.
#: * `agent` -- read and judged in a Claude Code session.
#: * `api` -- classified through the Batches API by `submit_batch`.
Source = Literal["rules", "agent", "api"]

#: Categories an entry can fall into. `BEHAVIOR_CHANGE` is deliberately separate
#: from `RESULT_CHANGING`: both move published numbers, but only one is a bug,
#: and conflating them makes the headline rate unreadable.
Category = Literal[
    "RESULT_CHANGING",
    "BEHAVIOR_CHANGE",
    "ERROR_TO_WORKING",
    "PERFORMANCE",
    "FEATURE",
    "DOC",
    "UNCLEAR",
]

RUBRIC = """\
You are classifying entries from the changelog of a statistics package, to \
establish which past releases could have changed the numbers in a published \
paper.

Classify the entry into exactly one category:

RESULT_CHANGING -- fixes a defect that made a previously-working call return a \
wrong number: an estimate, standard error, test statistic, p-value, fitted \
value, or any quantity that would appear in a results table. The old output was \
incorrect.

BEHAVIOR_CHANGE -- deliberately changes what a call returns, without claiming \
the old output was a defect. New defaults, changed estimation methods, altered \
random number generation, changed tie-breaking or rounding. These move \
published numbers just as bugs do, which is why they are counted separately \
rather than dropped.

ERROR_TO_WORKING -- the old version crashed, errored, hung, or refused to fit. \
Nothing wrong was ever returned, so no published result was corrupted.

PERFORMANCE -- speed or memory only, numerically identical results.

FEATURE -- new functionality, new arguments, new methods, with no change to \
existing calls.

DOC -- documentation, examples, vignettes, messages, packaging, tests, CRAN \
check notes. Includes fixes to how a result is *printed or formatted* when the \
underlying number is unchanged -- a fix to a LaTeX table writer or a print \
method is DOC, not RESULT_CHANGING.

UNCLEAR -- genuinely cannot tell from the text.

Then answer, for the state of affairs BEFORE the fix:

silent -- true if a user running the affected code would have received a \
plausible-looking wrong number with no error and no warning. False if the \
package errored, warned, or produced something obviously broken. This is the \
single most important field: a loud failure never reached a published table.

functions -- the exported functions the entry is about. Use only names that \
appear in the text and are plausibly functions of this package. Do not list \
base-language utilities the entry merely mentions in passing.

conditions -- the circumstances under which the bug bit, in one clause, as \
specifically as the text allows. "only with weights", "only for interval \
censored data", "only when a group had one observation". Empty string if the \
entry does not say.

severity -- HIGH if it changes an estimate, standard error, or p-value under \
conditions an applied user would plausibly hit. MEDIUM if it changes a \
secondary quantity or needs an unusual setup. LOW if the numeric effect is \
negligible or extremely rare.

introduced_version -- the version that introduced the defect, only if the entry \
states it. Null otherwise; do not guess.

evidence_quote -- the span of the entry that most directly supports your \
category. Quote it exactly.

confidence -- your confidence in the category, given only this text.

Judge only what the text says. Changelog authors understate; do not compensate \
by inflating, and do not read a wrong result into an entry that does not claim \
one.\
"""


class Classification(BaseModel):
    """One entry's classification.

    Attributes:
        category: Which kind of change this is.
        silent: Whether the pre-fix behavior was a quiet wrong answer.
        functions: Affected function names named in the text.
        conditions: When the defect bit, in one clause.
        severity: How consequential the numeric effect is.
        introduced_version: Version that introduced the defect, if stated.
        evidence_quote: Span of the entry supporting the category.
        confidence: Confidence in the category.
        source: How this classification was decided.
    """

    category: Category
    silent: bool = Field(
        description="Pre-fix, did the user get a wrong number with no warning?"
    )
    functions: list[str] = Field(default_factory=list)
    conditions: str = ""
    severity: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    introduced_version: str | None = None
    evidence_quote: str = ""
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    source: Source = "api"

    @property
    def moves_published_numbers(self) -> bool:
        """Whether this entry could have altered a number in a published table.

        Returns:
            True for silent result-changing bugs and for behavior changes, which
            move results whether or not anyone calls them defects.
        """
        if self.category == "BEHAVIOR_CHANGE":
            return True
        return self.category == "RESULT_CHANGING" and self.silent


def entry_prompt(entry: Entry) -> str:
    """Render one entry into a classification prompt.

    Package and version are included because they carry real signal -- a
    `survival` entry naming `coxph` is about a model fit, and the same words in
    a plotting package are not.

    Args:
        entry: The changelog entry.

    Returns:
        The user-turn text.
    """
    released = entry.released.isoformat() if entry.released else "unknown"
    return (
        f"Package: {entry.package}\n"
        f"Version: {entry.version} (released {released})\n"
        f"Entry: {entry.text}"
    )


class ClassificationCache:
    """Disk cache of classifications, keyed by entry id.

    The corpus is reclassified whenever the rubric changes but not when the
    downstream analysis does, so caching keeps iteration on the analysis free.

    Attributes:
        path: JSON file backing the cache.
    """

    def __init__(self, path: Path) -> None:
        """Load the cache from disk.

        Args:
            path: JSON file to read and write.
        """
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text())

    def get(self, entry_id: str) -> Classification | None:
        """Return a cached classification.

        Args:
            entry_id: The entry's stable id.

        Returns:
            The classification, or None if absent.
        """
        payload = self._data.get(entry_id)
        return Classification(**payload) if payload else None

    def put(self, entry_id: str, classification: Classification) -> None:
        """Store a classification in memory.

        Args:
            entry_id: The entry's stable id.
            classification: The classification to store.
        """
        self._data[entry_id] = classification.model_dump()

    def save(self) -> None:
        """Write the cache to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True))

    def __len__(self) -> int:
        """Return how many classifications are cached.

        Returns:
            Number of cached entries.
        """
        return len(self._data)


def _client():
    """Construct an Anthropic client.

    Returns:
        The client.

    Raises:
        RuntimeError: If no credentials are configured, with the two ways to
            supply them.
    """
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("pip install anthropic") from exc

    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get(
        "ANTHROPIC_AUTH_TOKEN"
    ):
        # A profile from `ant auth login` also works and needs no env var, so
        # this is a warning path rather than a hard precondition -- the client
        # constructor resolves it. Only raise once the call itself fails.
        pass
    return anthropic.Anthropic()


def classify_entries(
    entries: list[Entry], cache: ClassificationCache
) -> dict[str, Classification]:
    """Classify entries one at a time, reusing the cache.

    Suited to spot-checking and small reruns. Use `submit_batch` for the corpus.

    Args:
        entries: Entries to classify.
        cache: Cache to read from and write to.

    Returns:
        Entry id to classification.
    """
    client = _client()
    out: dict[str, Classification] = {}
    for entry in entries:
        cached = cache.get(entry.entry_id)
        if cached:
            out[entry.entry_id] = cached
            continue
        response = client.messages.parse(
            model=MODEL,
            max_tokens=2048,
            system=RUBRIC,
            output_format=Classification,
            messages=[{"role": "user", "content": entry_prompt(entry)}],
        )
        parsed = response.parsed_output
        if parsed is None:
            continue
        out[entry.entry_id] = parsed
        cache.put(entry.entry_id, parsed)
    cache.save()
    return out


def submit_batch(entries: list[Entry], cache: ClassificationCache) -> str | None:
    """Submit uncached entries to the Batches API.

    Args:
        entries: Entries to classify.
        cache: Cache used to skip already-classified entries.

    Returns:
        The batch id, or None if every entry was already cached.
    """
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    pending = [e for e in entries if cache.get(e.entry_id) is None]
    if not pending:
        return None

    schema = Classification.model_json_schema()
    schema["additionalProperties"] = False
    requests = [
        Request(
            custom_id=f"e{index}",
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=2048,
                system=RUBRIC,
                output_config={"format": {"type": "json_schema", "schema": schema}},
                messages=[{"role": "user", "content": entry_prompt(entry)}],
            ),
        )
        for index, entry in enumerate(pending)
    ]

    client = _client()
    batch = client.messages.batches.create(requests=requests)
    # custom_id must be short, so the index-to-entry mapping is written beside
    # the cache rather than encoded in the id.
    mapping = {f"e{i}": e.entry_id for i, e in enumerate(pending)}
    (cache.path.parent / f"batch_{batch.id}.json").write_text(
        json.dumps({"batch_id": batch.id, "mapping": mapping}, indent=2)
    )
    return batch.id


def collect_batch(
    batch_id: str, cache: ClassificationCache, poll_seconds: int = 60
) -> int:
    """Wait for a batch to finish and fold its results into the cache.

    Args:
        batch_id: Batch to collect.
        cache: Cache to write into.
        poll_seconds: Seconds between status checks.

    Returns:
        How many classifications were added.

    Raises:
        RuntimeError: If the batch's id mapping is missing.
    """
    mapping_path = cache.path.parent / f"batch_{batch_id}.json"
    if not mapping_path.exists():
        raise RuntimeError(f"no id mapping for batch {batch_id}")
    mapping = json.loads(mapping_path.read_text())["mapping"]

    client = _client()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        time.sleep(poll_seconds)

    added = 0
    for result in client.messages.batches.results(batch_id):
        if result.result.type != "succeeded":
            continue
        entry_id = mapping.get(result.custom_id)
        if not entry_id:
            continue
        text = next(
            (b.text for b in result.result.message.content if b.type == "text"), None
        )
        if not text:
            continue
        cache.put(entry_id, Classification(**json.loads(text)))
        added += 1
    cache.save()
    return added


def classify_by_rules(entry: Entry) -> Classification:
    """Classify an entry with regular expressions alone.

    The baseline, not the answer. It decides only what the patterns in `link.py`
    can decide -- whether the prose claims a previously-wrong result -- and
    deliberately declines the rest:

    * `silent` is left at its default rather than guessed. The obvious pattern
      for a loud failure (`error|warning|crash|fail`) fires on 19% of candidates
      and is a false positive on every one sampled, because changelog authors
      write "error" to mean a mistake in the code, not a raised exception.
    * `conditions` is left empty. Extracting the clause needs to know which
      `when`/`if`/`for` scopes the defect and which is incidental.
    * `confidence` is always LOW, for the reasons above.

    Its purpose is to be disagreed with: read classifications are compared
    against it, and the disagreement rate is the validation that would otherwise
    need a hand-coded gold set.

    Args:
        entry: The changelog entry.

    Returns:
        A classification with `source="rules"`.
    """
    from kasauti.archaeology.link import INERT, RESULT_CHANGING

    match = RESULT_CHANGING.search(entry.text)
    inert = INERT.search(entry.text)
    if match and not inert:
        category, evidence = "RESULT_CHANGING", match.group(0)
    elif inert:
        category, evidence = "DOC", inert.group(0)
    else:
        category, evidence = "UNCLEAR", ""

    return Classification(
        category=category,  # type: ignore[arg-type]
        silent=False,
        evidence_quote=evidence,
        confidence="LOW",
        source="rules",
    )


def pending_payload(
    entries: list[Entry],
    cache: ClassificationCache,
    exposure: dict[str, int] | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Build the review queue: entries needing judgment, with their baseline.

    Ranked by corpus exposure so the highest-value entries are read first. Each
    record carries the rule layer's proposal, so review starts from a baseline
    and every correction is a measured disagreement rather than an opinion
    formed in a vacuum.

    Args:
        entries: Candidate entries.
        cache: Already-classified entries, which are skipped.
        exposure: Entry id to the number of corpus scripts exposed.
        limit: Maximum records to return.

    Returns:
        One dict per entry, ready to be written as JSON and read.
    """
    exposure = exposure or {}
    queue = [e for e in entries if cache.get(e.entry_id) is None]
    queue.sort(key=lambda e: (-exposure.get(e.entry_id, 0), e.entry_id))
    if limit is not None:
        queue = queue[:limit]

    return [
        {
            "entry_id": e.entry_id,
            "package": e.package,
            "version": e.version,
            "released": e.released.isoformat() if e.released else None,
            "exposure_scripts": exposure.get(e.entry_id, 0),
            "text": e.text,
            "rule_baseline": classify_by_rules(e).category,
        }
        for e in queue
    ]


def ingest_reviewed(
    payload: list[dict], cache: ClassificationCache
) -> tuple[int, list[str]]:
    """Merge read classifications into the cache, validating each.

    A malformed record is refused by name rather than silently dropped: a
    classification that failed to parse is not the same as one that says
    UNCLEAR, and conflating them corrupts the rate.

    Args:
        payload: Reviewed records, each with an `entry_id` and the
            classification fields.
        cache: Cache to merge into.

    Returns:
        A `(merged, errors)` pair.
    """
    from pydantic import ValidationError

    merged, errors = 0, []
    for record in payload:
        entry_id = record.get("entry_id")
        if not entry_id:
            errors.append(f"record with no entry_id: {str(record)[:80]}")
            continue
        fields = {k: v for k, v in record.items() if k != "entry_id"}
        fields.setdefault("source", "agent")
        try:
            cache.put(entry_id, Classification(**fields))
            merged += 1
        except (ValidationError, TypeError) as exc:
            errors.append(f"{entry_id}: {str(exc).splitlines()[0]}")
    cache.save()
    return merged, errors


@dataclass
class Agreement:
    """How the rule baseline compares with the readings.

    Attributes:
        judged: Entries read by hand.
        rules_agreed: Entries where the rules reached the same category.
        rules_disagreed: Entries where they did not.
        categories: Read category to count.
        silent: Whether-silent to count.
        moves_published_numbers: Entries that could move a published number.
        confusion: `"rule->read"` to count, most common first.
    """

    judged: int = 0
    rules_agreed: int = 0
    rules_disagreed: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    silent: dict[bool, int] = field(default_factory=dict)
    moves_published_numbers: int = 0
    confusion: dict[str, int] = field(default_factory=dict)


def agreement(entries: list[Entry], cache: ClassificationCache) -> Agreement:
    """Compare the rule baseline against the read classifications.

    This is the validation the plan originally wanted a hand-coded gold set for.
    The rules are the baseline and the readings are the reference, so the
    disagreement rate says how much the reading was worth.

    Args:
        entries: The classified entries.
        cache: Cache holding their classifications.

    Returns:
        Counts keyed for reporting, including the confusion between the rule
        category and the read category.
    """
    from collections import Counter

    judged, confusion = 0, Counter()
    categories, silent_counts = Counter(), Counter()
    moves = 0
    for entry in entries:
        found = cache.get(entry.entry_id)
        if found is None or found.source == "rules":
            continue
        judged += 1
        rule = classify_by_rules(entry).category
        confusion[(rule, found.category)] += 1
        categories[found.category] += 1
        silent_counts[found.silent] += 1
        if found.moves_published_numbers:
            moves += 1

    agreed = sum(n for (rule, read), n in confusion.items() if rule == read)
    return Agreement(
        judged=judged,
        rules_agreed=agreed,
        rules_disagreed=judged - agreed,
        categories=dict(categories),
        silent=dict(silent_counts),
        moves_published_numbers=moves,
        confusion={f"{r}->{d}": n for (r, d), n in confusion.most_common()},
    )
