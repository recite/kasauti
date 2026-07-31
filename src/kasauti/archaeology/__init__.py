"""Changelog archaeology: did a package used to be wrong, and who ran it then?

The pipeline runs in stages, each writing to disk so the expensive ones happen
once:

1. `calls` -- recover function-call sites from a corpus of replication scripts,
   using each language's own parser rather than regular expressions.
2. `frame` -- rank procedures and packages by corpus exposure. This is the
   sampling frame for both halves of the project.
3. `harvest` -- collect version histories and changelog text for the packages the
   frame selects.
4. `classify` -- sort changelog entries into result-changing, behavior-changing,
   and inert.
5. `link` -- join bugs to the scripts that called the affected function during the
   window when it was broken.
6. `verify` -- run a sampled script under the buggy and the fixed version and diff
   the numbers, through the same comparison engine the translation suite uses.
"""
