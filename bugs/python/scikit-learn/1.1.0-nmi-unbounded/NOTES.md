# scikit-learn 1.1.0: a bounded metric returning 1.25

> |Fix| Fixed a bug in `metrics.normalized_mutual_info_score` which could return
> unbounded values.
> — scikit-learn 1.1.0, 2022-05-12

Normalized mutual information is defined on [0, 1]. Under 1.0.2 it returns
**1.25**.

| `average_method` | 1.0.2 (buggy) | 1.1.0 (fixed) | |
|---|---|---|---|
| **`min`** | **1.25** | 0.0 | above the metric's upper bound |
| **`geometric`** | **1.25** | 0.0 | above the metric's upper bound |
| `arithmetic` (default) | 8.248170716e-16 | 0.0 | same to floating point |
| `max` | 4.124085358e-16 | 0.0 | same to floating point |

The input is two clusterings of ten points where one puts every point in a single
cluster. That labeling has zero entropy, so the mutual information is zero and the
normalized value is zero under any sensible normalizer. `min` and `geometric`
divide by the smaller entropy — zero — and returned 1.25 rather than failing.

The default `average_method` is `arithmetic`, which escapes it. A caller had to
have chosen `min` or `geometric`.

**How the input was found.** Not from the changelog, which says only "unbounded".
A search over 16,000 small random labelings, filtered to results outside [0, 1],
returned three hits under 1.0.2. Two of them — 1.0000000000000002 and
1.0000000000000004 — appear under *both* versions and are ordinary floating-point
overshoot that the fix did not address. Only the 1.25 case is the documented bug.
The literals are written into `data.py` so the case does not depend on the search
reproducing.

## Two things this bug taught the pipeline

### 1. Comparing near-zero against exact zero

`arithmetic` and `max` return 8.2e-16 and 4.1e-16 under 1.0.2 against an exact
0.0 under 1.1.0. The comparison engine flagged both as divergent, with a relative
difference of 8e-4 — because `|a-b| / max(|a|,|b|,floor)` divides by the 1e-12
floor when both values are tiny.

That is wrong. Two numbers that are both below the floor are indistinguishable at
the precision the floor represents. `relative_difference` now treats them as
equal, and a test pins it. Without the fix this case would have reported four
divergences instead of two, and the two real ones would have been buried among
noise.

### 2. Replication archives that bundle their dependencies

The probe initially found one exposed script in an archive for **"Old Boys' Clubs
and Upward Mobility among the Educational Elite"** (*Quarterly Journal of
Economics*, DOI 10.7910/DVN/GXLO3P, published 2021-11-14 — comfortably inside the
window).

The script was `test_supervised.py`: **scikit-learn's own test suite**, vendored
into the archive along with 3,838 other Python files, including `__config__.py`
and `__init___106.py`. The author had zipped an entire site-packages directory.

So the only apparent Python paper-level exposure in this corpus was a library
testing itself. Left in, it would have been a finding about a QJE paper that has
nothing to do with the paper.

`looks_vendored` now excludes scripts whose filenames mark them as library or
packaging code, and the probe reports how many it dropped. After filtering: **all
three** scripts calling `normalized_mutual_info_score` in the corpus are vendored
test files, and the real exposure is **zero**. The R bugs' counts are unchanged,
so the filter is not over-triggering.

The filter is name-based and conservative — an author who names an analysis
script `test_effects.R` is wrongly excluded. That direction is the right one to
err in: over-excluding shrinks a number already reported as an upper bound, while
under-excluding invents exposure that does not exist.

## Python archaeology costs more than R archaeology

R's source packages build against any recent R, so pinning `sandwich` 2.4-0 was
one `install.packages` call. Python needed three pins to run a 2021 release:

```yaml
cmd: ["uv", "run", "--quiet", "--no-project", "--python", "3.10",
      "--with", "scikit-learn==1.0.2", "--with", "numpy<2", "--with", "scipy<1.11",
      "python", "run_py.py"]
```

- **`--python 3.10`** — scikit-learn 1.0.2 ships no wheel for anything newer.
- **`numpy<2`** — the wheel is compiled against the numpy 1.x C ABI. Resolving
  numpy 2.x fails at import with `numpy.dtype size changed, may indicate binary
  incompatibility`, before any statistics run.
- **`--no-project`** — otherwise `uv` applies concord's own
  `requires-python = ">=3.11"` to the child environment.

This bounds how far back Python archaeology can reach: a fix released before
roughly 2022 requires an interpreter old enough that the whole compiled stack has
to be pinned with it, and eventually no combination resolves. R has no equivalent
ceiling. Bug selection for Python has to account for it.

## Reproducing

```bash
concord run sklearn_nmi_unbounded
concord bug probe python/scikit-learn/1.1.0-nmi-unbounded
```
