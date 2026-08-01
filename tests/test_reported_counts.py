"""The published artifacts must agree with each other and with the data.

Three counts of the same thing were once in the tree at the same time:
`docs/classification.md` said 211 judged of 386, `README.md` said 228 of 409, and
`data/classify/cache.json` held 242. Each was true when it was written. Nothing
noticed when the others stopped being true.

For a project whose whole discipline is that a number travels with its
denominator, that is a defect rather than untidiness, and it is exactly the kind
that regenerating one artifact and not another reintroduces. So the agreement is
asserted here rather than checked by eye.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: "**207 of 369** exposed entries" in the README, and "369 entries ... Of those,
#: **207** have been read" in the generated report. Different prose, same pair.
README_PAIR = re.compile(r"\*\*(\d+) of (\d+)\*\* exposed entries")
REPORT_TOTAL = re.compile(r"^(\d+) entries from (\d+) R packages", re.MULTILINE)
REPORT_JUDGED = re.compile(r"\*\*(\d+)\*\* have been read and judged")


def read(name: str) -> str:
    path = ROOT / name
    if not path.exists():
        pytest.skip(f"{name} has not been generated")
    return path.read_text()


def test_readme_and_the_generated_report_agree_on_coverage():
    readme = README_PAIR.search(read("README.md"))
    report = read("docs/classification.md")
    total = REPORT_TOTAL.search(report)
    judged = REPORT_JUDGED.search(report)

    assert readme, "README no longer states an 'N of M exposed entries' figure"
    assert total, "docs/classification.md no longer states an entry total"
    assert judged, "docs/classification.md no longer states a judged count"
    assert (int(readme.group(1)), int(readme.group(2))) == (
        int(judged.group(1)),
        int(total.group(1)),
    ), (
        "README and docs/classification.md disagree about how many entries are "
        "judged. Regenerate with `kasauti classify report` and update the README."
    )


def test_the_judged_count_is_bounded_by_the_cache():
    """Judged entries must be a subset of what has actually been classified.

    Not equality: the cache accumulates judgments, and an entry judged before a
    funnel change may no longer be exposed. The cache can legitimately exceed the
    report -- it cannot legitimately fall short, because then the report is
    claiming readings that were never made.
    """
    cache = json.loads(read("data/classify/cache.json"))
    judged = REPORT_JUDGED.search(read("docs/classification.md"))
    assert judged
    assert int(judged.group(1)) <= len(cache), (
        f"docs/classification.md claims {judged.group(1)} judged entries but the "
        f"cache holds only {len(cache)}"
    )


def test_the_screening_counts_agree_between_the_readme_and_the_report():
    """The screened verdicts are a denominator, so they must not drift apart.

    The whole argument for a screening tier is that failures become cheap enough
    to attempt and therefore cheap enough to count. A README quoting one set of
    counts while the generated report holds another destroys exactly that.
    """
    # Collapsed first, because the README wraps at 88 columns and the sentence
    # carrying these four numbers does not fit on one line.
    prose = " ".join(read("README.md").split())
    readme = re.search(
        r"\*\*(\d+) claims screened\*\*: (\d+) moved a number, (\d+) did not, "
        r"(\d+) could not be evaluated",
        prose,
    )
    assert readme, "README no longer states the screening counts"

    report = read("docs/screening.md")
    declared = re.search(r"\*\*(\d+)\*\* screened", report)
    verdicts = {
        name: int(found.group(1))
        for name in ("MOVED", "NOT_TRIGGERED", "UNEVALUABLE")
        if (found := re.search(rf"\| `{name}` \| (\d+) \|", report))
    }
    assert declared, "docs/screening.md no longer states how many were screened"
    assert len(verdicts) == 3, "docs/screening.md no longer states every verdict"

    assert int(readme.group(1)) == int(declared.group(1))
    assert (
        int(readme.group(2)),
        int(readme.group(3)),
        int(readme.group(4)),
    ) == (
        verdicts["MOVED"],
        verdicts["NOT_TRIGGERED"],
        verdicts["UNEVALUABLE"],
    ), (
        "README and docs/screening.md disagree about the screening verdicts. "
        "Regenerate with `kasauti screen report` and update the README."
    )


def test_the_package_count_agrees_across_the_frame_and_the_readme():
    """`stats` is in the frame for attribution but is not a selected package.

    Counting it made `docs/sampling-frame.md` say 132 where `README.md` and
    `data/frame/packages.csv` said 131 -- both correct, describing different
    things, and impossible to reconcile without reading the code.
    """
    selected = len(read("data/frame/packages.csv").strip().splitlines()) - 1
    readme = re.search(r"\*\*(\d+) R packages\*\*", read("README.md"))
    frame = re.search(r"\*\*(\d+)\*\* CRAN packages", read("docs/sampling-frame.md"))
    assert readme, "README no longer states a package count"
    assert frame, "docs/sampling-frame.md no longer states a CRAN package count"
    assert int(readme.group(1)) == int(frame.group(1)) == selected
