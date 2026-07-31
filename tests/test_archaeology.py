"""Changelog parsing and bug-to-corpus linkage."""

from datetime import date

import pytest

from kasauti.archaeology.frame import NON_COMPUTING_PYTHON
from kasauti.archaeology.harvest import (
    Harvest,
    Release,
    _parse_cran_date,
    _strip_r_comments,
    parse_namespace,
    r_definitions,
)
from kasauti.archaeology.link import (
    affected_functions,
    build_bugs,
    is_result_changing,
)
from kasauti.archaeology.parse import Entry, parse_news


def make_harvest(news, releases=()):
    return Harvest(
        package="pkg",
        ecosystem="cran",
        releases=[Release(v, d) for v, d in releases],
        news_text=news,
    )


class TestParseCranDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2024-09-15 21:50:01 UTC", date(2024, 9, 15)),
            ("2024-09-15", date(2024, 9, 15)),
            ("Mon Jul 19 23:28:55 2004; zeileis", date(2004, 7, 19)),
        ],
    )
    def test_recognises_the_formats_cran_uses(self, raw, expected):
        assert _parse_cran_date(raw) == expected

    def test_missing_or_unparseable_is_none(self):
        assert _parse_cran_date(None) is None
        assert _parse_cran_date("sometime last year") is None


class TestParseNamespace:
    def test_comments_inside_an_export_block_are_not_exports(self):
        # sandwich opens its export list with `## core ingredients`, which a
        # regex over raw text harvests as though it were a function name.
        namespace = 'export(\n  ## core ingredients\n  "sandwich",\n  vcovHC\n)'
        assert parse_namespace(namespace) == ["sandwich", "vcovHC"]

    def test_s3_methods_register_the_composite_not_the_generic(self):
        # A changelog says "vcovHC.mlm was wrong", so the composite is worth
        # having -- but `print` belongs to base R, not to the package.
        exports = parse_namespace("S3method(print, foo)\nS3method(vcovHC, mlm)")
        assert exports == ["print.foo", "vcovHC.mlm"]

    def test_operator_methods_are_quoted_and_still_register(self):
        # metafor writes `S3method("[", escalc)`; a word-only pattern skips it.
        assert parse_namespace('S3method("[", escalc)') == ["[.escalc"]

    def test_export_pattern_resolves_against_the_package_sources(self):
        # metafor exports by regex alone. Unresolved, it would report no exports
        # and so no candidates, which reads as a package with nothing wrong.
        exports = parse_namespace(
            'exportPattern("^[^\\\\.]")', {"rma", "rma.uni", ".hidden"}
        )
        assert exports == ["rma", "rma.uni"]

    def test_export_pattern_without_sources_yields_nothing_rather_than_guessing(self):
        assert parse_namespace('exportPattern("^[^.]")') == []

    def test_quoted_and_multiline_export_lists(self):
        exports = parse_namespace('export("[.escalc",\n       coef.rma)\nexport(rma)')
        assert exports == ["[.escalc", "coef.rma", "rma"]


class TestRDefinitions:
    def test_chained_assignment_names_every_function(self):
        # metafor defines its central estimator as `rma <- rma.uni <- function`;
        # matching only the innermost name loses `rma` entirely.
        assert r_definitions("rma <- rma.uni <- function(yi, vi) {") == {
            "rma",
            "rma.uni",
        }

    def test_ignores_non_function_bindings(self):
        assert r_definitions("threshold <- 0.05\nfit <- function(x) x") == {"fit"}


class TestStripRComments:
    def test_a_hash_inside_a_string_is_not_a_comment(self):
        assert _strip_r_comments('export("a#b")  # gone') == 'export("a#b")  '

    def test_line_structure_survives(self):
        assert _strip_r_comments("a # one\nb # two") == "a \nb "


class TestParseNews:
    def test_rd_sections(self):
        news = (
            r"\section{Changes in version 1.2-3 (2020-01-01)}{"
            r"\itemize{\item fixed an incorrect variance}}"
        )
        report = parse_news(make_harvest(news, [("1.2-3", date(2020, 1, 1))]))
        assert report.format == "rd"
        assert report.entries[0].version == "1.2-3"
        assert report.entries[0].released == date(2020, 1, 1)

    def test_all_caps_rd_heading(self):
        # lme4 writes \section{CHANGES IN VERSION 2.0-6}.
        news = r"\section{CHANGES IN VERSION 2.0-6}{\itemize{\item fixed the thing}}"
        assert parse_news(make_harvest(news)).entries[0].version == "2.0-6"

    def test_markdown_sections_with_trailing_parenthesis(self):
        # metafor writes "# metafor 5.0-1 (2026-04-26)".
        news = "# metafor 5.0-1 (2026-04-26)\n\n- fixed a wrong p-value\n"
        report = parse_news(make_harvest(news))
        assert report.format == "md"
        assert report.entries[0].version == "5.0-1"

    def test_changes_to_version_wording(self):
        # car writes "Changes to Version", not "Changes in version".
        news = "Changes to Version 3.1-4\n\n  o Fixed bugs in powerTransform.\n"
        report = parse_news(make_harvest(news))
        assert report.format == "txt"
        assert report.entries[0].version == "3.1-4"

    def test_bare_version_line(self):
        # mgcv's ChangeLog separates releases with a naked version number.
        news = "1.9-1\n\n* fixed an incorrect edf\n\n1.9-0\n\n* other change here\n"
        report = parse_news(make_harvest(news))
        assert report.format == "bare"
        assert {e.version for e in report.entries} == {"1.9-1", "1.9-0"}

    def test_gnu_changelog_dates_map_to_the_shipping_release(self):
        # nlme's ChangeLog dates every change but names no version. The change
        # shipped in the first release on or after that date.
        news = (
            "2020-06-01  A Maintainer  <a@b.c>\n\n"
            "\t* R/gnls.R: fix an incorrect standard error.\n"
        )
        harvest_result = make_harvest(
            news, [("3.1-100", date(2020, 1, 1)), ("3.1-101", date(2020, 7, 1))]
        )
        report = parse_news(harvest_result)
        assert report.format == "gnu"
        assert report.entries[0].version == "3.1-101"

    def test_change_after_every_known_release_is_unreleased(self):
        news = "2030-01-01  A  <a@b.c>\n\n\t* R/x.R: fix something incorrect.\n"
        report = parse_news(make_harvest(news, [("1.0", date(2020, 1, 1))]))
        assert report.entries[0].version == "unreleased"

    def test_unstructured_bullets_are_kept_not_collapsed(self):
        # MASS keeps a flat bullet list with no version headings at all. Those
        # changes are real even though none can be dated.
        news = (
            "Intro paragraph.\n\n- first change that is long enough\n"
            "- second change here\n"
        )
        report = parse_news(make_harvest(news))
        assert report.format == "unstructured"
        assert len(report.entries) >= 2
        assert report.undated == len(report.entries)

    def test_empty_news_yields_no_entries(self):
        report = parse_news(make_harvest("   "))
        assert report.entries == []
        assert report.version_coverage == 0.0

    def test_coverage_is_capped_at_one(self):
        news = "# 1.0\n\n- a change of sufficient length\n"
        report = parse_news(make_harvest(news, [("1.0", date(2020, 1, 1))]))
        assert report.version_coverage <= 1.0


class TestIsResultChanging:
    @pytest.mark.parametrize(
        "text",
        [
            "the variance was incorrect",
            "coxph gave the wrong answer",
            "fixed a bug in the standard errors",
            "p-values were erroneous",
        ],
    )
    def test_accepts_claims_of_a_wrong_number(self, text):
        assert is_result_changing(text)

    @pytest.mark.parametrize(
        "text",
        [
            "fixed a typo in the documentation",
            "corrected a broken url in the vignette",
            "improved the error message when x is missing",
            "added a new argument for weights",
            "the function is now faster",
        ],
    )
    def test_rejects_inert_and_non_claims(self, text):
        assert not is_result_changing(text)


class TestAffectedFunctions:
    def test_restricted_to_the_package_exports(self):
        # The base-R utilities a changelog mentions in passing must not count,
        # or `length` outranks every estimator in the ecosystem.
        text = "survfit uses both unique() and table() in various places"
        assert affected_functions(text, {"survfit", "coxph"}) == ["survfit"]

    def test_reads_backticked_names(self):
        text = "Bug fix in `vcovCL(..., type = 'HC2')` for `glm` objects"
        assert "vcovCL" in affected_functions(text, {"vcovCL", "vcovHC"})

    def test_reads_bare_prose_names(self):
        # survival writes "Fix a bug in survfit" far more often than "survfit()".
        text = "Fix a bug in survfit pointed out by a user"
        assert affected_functions(text, {"survfit", "coxph"}) == ["survfit"]

    def test_english_prose_is_not_mistaken_for_a_function(self):
        text = "the variance was incorrect for some models"
        assert affected_functions(text, {"coxph", "survfit"}) == []

    def test_display_functions_are_excluded(self):
        # A fix to a table formatter changes rendering, not coefficients.
        text = "fix display bug in etable() and in summary()"
        assert affected_functions(text, {"etable", "summary", "feols"}) == []


class TestSelfNamedPackage:
    def test_the_package_name_as_prose_is_not_a_function_call(self):
        # Matrix 1.5-0's crossprod entry scored 58 corpus scripts entirely on
        # the phrase "before Matrix 1.2-0". The two functions it is about
        # contribute zero, because base R owns both names.
        text = "Ditto for tcrossprod(), where the old result was even wrong "
        text += "when it had worked, before Matrix 1.2-0."
        assert affected_functions(text, {"Matrix", "tcrossprod"}, package="Matrix") == [
            "tcrossprod"
        ]

    def test_the_package_name_written_as_a_call_still_counts(self):
        # plm's changelog really does say "fixed a bug in plm()", and there the
        # name is the estimator.
        assert affected_functions(
            "fixed a bug in plm() with unbalanced panels", {"plm"}, package="plm"
        ) == ["plm"]

    def test_other_packages_names_are_untouched_by_the_rule(self):
        assert affected_functions(
            "zoo objects were mishandled", {"zoo"}, package="xts"
        ) == ["zoo"]


class TestPythonExclusion:
    def test_array_plumbing_is_dropped_the_way_r_display_names_are(self):
        # numpy exports `where`, `all`, and `array`. They are ordinary words in a
        # release note and calls in nearly every script; `where` alone drove 179
        # candidate entries before this list existed.
        text = "Fixed a bug where all values in the array were incorrect"
        exports = {"where", "all", "array", "values", "polyfit"}
        assert affected_functions(text, exports, NON_COMPUTING_PYTHON) == []

    def test_statistics_survive_the_exclusion(self):
        # `mean` and `quantile` compute numbers that reach a table, exactly as
        # `sd` and `quantile` do on the R side.
        for name in ("mean", "median", "std", "var", "quantile", "corrcoef"):
            assert name not in NON_COMPUTING_PYTHON

    def test_a_named_estimator_still_matches(self):
        text = "Fix a bug in Normalizer with norm='max', which was incorrect"
        assert affected_functions(
            text, {"Normalizer", "max"}, NON_COMPUTING_PYTHON
        ) == ["Normalizer"]


class TestBuildBugs:
    def test_ranks_by_distinct_scripts_exposed(self):
        entries = [
            Entry("p", "1.0", date(2020, 1, 1), "bug in rare() gave wrong values", 0),
            Entry("p", "1.1", date(2020, 2, 1), "bug in common() was incorrect", 0),
        ]
        exports = {"p": {"rare", "common"}}
        index = {"rare": {"a.R"}, "common": {"a.R", "b.R", "c.R"}}
        bugs, funnel = build_bugs(entries, exports, index)
        assert [b.functions[0] for b in bugs] == ["common", "rare"]
        assert bugs[0].total_exposed == 3
        assert funnel.result_changing == 2

    def test_funnel_narrows_and_records_each_drop(self):
        entries = [
            Entry("p", "1.0", None, "fixed a typo in the docs", 0),
            Entry("p", "1.0", None, "bug in notexported() was incorrect", 1),
            Entry("p", "1.0", None, "bug in uncalled() was incorrect", 2),
            Entry("p", "1.0", None, "bug in called() was incorrect", 3),
        ]
        bugs, funnel = build_bugs(
            entries, {"p": {"uncalled", "called"}}, {"called": {"a.R"}}
        )
        assert funnel.entries == 4
        assert funnel.result_changing == 3
        assert funnel.with_named_function == 2
        assert funnel.with_corpus_exposure == 1
        assert len(bugs) == 1

    def test_scripts_are_deduplicated_across_functions(self):
        entries = [
            Entry("p", "1.0", None, "bug in aa() and bb() were incorrect", 0),
        ]
        bugs, _ = build_bugs(
            entries, {"p": {"aa", "bb"}}, {"aa": {"x.R"}, "bb": {"x.R", "y.R"}}
        )
        assert bugs[0].total_exposed == 2

    def test_a_name_base_r_owns_counts_only_where_qualified(self):
        # Matrix exports `diag`. Nearly every `diag()` call in the corpus means
        # base R's, and counting them all put Matrix at the top of the queue on
        # 3,562 scripts it has nothing to do with.
        entries = [Entry("Matrix", "1.5-0", None, "diag<- was incorrect", 0)]
        bugs, _ = build_bugs(
            entries,
            {"Matrix": {"diag"}},
            {"diag": {"a.R", "b.R", "c.R"}},
            qualified={("diag", "Matrix"): {"c.R"}},
            shadowed={"diag"},
        )
        assert bugs[0].total_exposed == 1

    def test_a_shadowed_name_never_qualified_drops_out_entirely(self):
        entries = [Entry("Matrix", "1.5-0", None, "diag<- was incorrect", 0)]
        bugs, funnel = build_bugs(
            entries,
            {"Matrix": {"diag"}},
            {"diag": {"a.R"}},
            qualified={},
            shadowed={"diag"},
        )
        assert bugs == []
        assert funnel.with_named_function == 1
        assert funnel.with_corpus_exposure == 0

    def test_a_plotting_packages_name_is_not_credited_to_a_computing_one(self):
        # `alpha` is Cronbach's alpha in psych and colour transparency in
        # scales. In this corpus it is written scales::alpha eight times against
        # psych::alpha six, so counting bare alpha() put seven psych entries
        # near the top of the shortlist on the strength of ggplot2 code.
        entries = [Entry("psych", "2.4.4", None, "Fix a bug in alpha", 0)]
        bugs, _ = build_bugs(
            entries,
            {"psych": {"alpha"}},
            {"alpha": {"plot.R", "plot2.R", "scale.R"}},
            qualified={("alpha", "psych"): {"scale.R"}},
            shadowed={"alpha"},
        )
        assert bugs[0].total_exposed == 1

    def test_a_name_base_r_does_not_own_is_untouched(self):
        entries = [Entry("p", "1.0", None, "bug in vcovHC was incorrect", 0)]
        bugs, _ = build_bugs(
            entries,
            {"p": {"vcovHC"}},
            {"vcovHC": {"a.R", "b.R"}},
            qualified={},
            shadowed={"diag"},
        )
        assert bugs[0].total_exposed == 2


class TestClassification:
    def test_rules_flag_a_claimed_wrong_result(self):
        from kasauti.archaeology.classify import classify_by_rules

        entry = Entry("p", "1.0", None, "the variance was incorrect", 0)
        result = classify_by_rules(entry)
        assert result.category == "RESULT_CHANGING"
        assert result.source == "rules"
        assert result.confidence == "LOW"

    def test_rules_flag_prose_as_doc(self):
        from kasauti.archaeology.classify import classify_by_rules

        entry = Entry("p", "1.0", None, "fixed a typo in the documentation", 0)
        assert classify_by_rules(entry).category == "DOC"

    def test_rules_do_not_guess_silent(self):
        # The obvious pattern for a loud failure fires on 19% of candidates and
        # is a false positive on every one sampled: changelog authors write
        # "error" to mean a mistake in the code, not a raised exception.
        from kasauti.archaeology.classify import classify_by_rules

        entry = Entry("p", "1.0", None, "Small error in plot.survfit was fixed", 0)
        assert classify_by_rules(entry).silent is False

    def test_moves_published_numbers_needs_silence(self):
        from kasauti.archaeology.classify import Classification

        loud = Classification(category="RESULT_CHANGING", silent=False)
        quiet = Classification(category="RESULT_CHANGING", silent=True)
        behaviour = Classification(category="BEHAVIOR_CHANGE", silent=False)
        assert not loud.moves_published_numbers
        assert quiet.moves_published_numbers
        # A behaviour change moves results whether or not anyone calls it a bug.
        assert behaviour.moves_published_numbers

    def test_cache_round_trips_source(self, tmp_path):
        from kasauti.archaeology.classify import Classification, ClassificationCache

        cache = ClassificationCache(tmp_path / "c.json")
        cache.put(
            "p@1.0#0", Classification(category="DOC", silent=False, source="agent")
        )
        cache.save()
        assert ClassificationCache(tmp_path / "c.json").get("p@1.0#0").source == "agent"

    def test_pending_skips_what_is_cached_and_ranks_by_exposure(self, tmp_path):
        from kasauti.archaeology.classify import (
            Classification,
            ClassificationCache,
            pending_payload,
        )

        entries = [
            Entry("p", "1.0", None, "bug in a() was incorrect", 0),
            Entry("p", "1.1", None, "bug in b() was incorrect", 0),
            Entry("p", "1.2", None, "bug in c() was incorrect", 0),
        ]
        cache = ClassificationCache(tmp_path / "c.json")
        cache.put("p@1.0#0", Classification(category="DOC", silent=False))
        exposure = {"p@1.1#0": 5, "p@1.2#0": 50}

        payload = pending_payload(entries, cache, exposure)
        assert [r["entry_id"] for r in payload] == ["p@1.2#0", "p@1.1#0"]
        assert payload[0]["rule_baseline"] == "RESULT_CHANGING"

    def test_ingest_rejects_a_bad_record_by_name(self, tmp_path):
        from kasauti.archaeology.classify import ClassificationCache, ingest_reviewed

        cache = ClassificationCache(tmp_path / "c.json")
        merged, errors = ingest_reviewed(
            [
                {"entry_id": "p@1.0#0", "category": "DOC", "silent": False},
                {"entry_id": "p@1.1#0", "category": "NONSENSE", "silent": False},
                {"category": "DOC", "silent": False},
            ],
            cache,
        )
        assert merged == 1
        assert any("p@1.1#0" in e for e in errors)
        assert any("no entry_id" in e for e in errors)

    def test_ingest_defaults_to_agent_provenance(self, tmp_path):
        from kasauti.archaeology.classify import ClassificationCache, ingest_reviewed

        cache = ClassificationCache(tmp_path / "c.json")
        ingest_reviewed(
            [{"entry_id": "p@1.0#0", "category": "DOC", "silent": False}], cache
        )
        assert cache.get("p@1.0#0").source == "agent"

    def test_agreement_ignores_rule_generated_records(self, tmp_path):
        # A rate computed over records the rules themselves wrote would be
        # 100% agreement by construction.
        from kasauti.archaeology.classify import (
            Classification,
            ClassificationCache,
            agreement,
        )

        entries = [
            Entry("p", "1.0", None, "bug in a() was incorrect", 0),
            Entry("p", "1.1", None, "bug in b() was incorrect", 0),
        ]
        cache = ClassificationCache(tmp_path / "c.json")
        cache.put(
            "p@1.0#0", Classification(category="DOC", silent=False, source="agent")
        )
        cache.put(
            "p@1.1#0",
            Classification(category="RESULT_CHANGING", silent=True, source="rules"),
        )
        stats = agreement(entries, cache)
        assert stats.judged == 1
        assert stats.rules_disagreed == 1
