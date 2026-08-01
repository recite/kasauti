"""Changelog archaeology: did a package used to be wrong, and who ran it then?

The pipeline runs in stages, each writing to disk so the expensive ones happen
once:

1. `calls` -- recover function-call sites from a corpus of replication scripts,
   using each language's own parser rather than regular expressions.
2. `loads` -- record which packages each script loads. Needed because a name two
   packages export cannot be attributed from the call site alone.
3. `frame` -- rank procedures and packages by corpus exposure. This is the
   sampling frame for the study.
4. `harvest` -- collect version histories, changelog text, and export lists for
   the packages the frame selects.
5. `classify` -- sort changelog entries into result-changing, behavior-changing,
   and inert.
6. `link` -- join bugs to the scripts that called the affected function, and
   `papers` to the archives those scripts came from.
7. `rank` -- order the remaining candidates by how many papers they could
   plausibly have reached, which is not the same as how many scripts call them.

Verification is the eighth stage and lives elsewhere: a verified record carries a
`case.yaml`, and milaan's runner executes it against pinned versions. The two
repositories share that engine because "does this package agree with its own past
self" and "does R agree with Python" are the same comparison.
"""

__all__: list[str] = []
