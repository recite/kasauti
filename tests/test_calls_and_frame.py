"""Call-site extraction and sampling-frame construction."""

import json

import pytest

from kasauti.archaeology.calls import CallSite, extract_python, extract_r
from kasauti.archaeology.frame import (
    NON_COMPUTING,
    SHADOWED,
    attribute_python,
    build_frame,
)

#: Enough of each package's real export list to exercise attribution, written
#: into a synthetic harvest cache so the frame tests need neither the network nor
#: an R installation carrying these packages.
FAKE_EXPORTS = {
    "plm": ["index", "plm", "vcovHC"],
    "MASS": ["select", "glm.nb", "rlm"],
    "stats": ["lm", "glm", "summary", "t.test"],
    "sandwich": ["vcovHC", "vcovCL", "NeweyWest"],
    "empty": [],
}


def write(tmp_path, name, source):
    path = tmp_path / name
    path.write_text(source)
    return path


@pytest.fixture
def cache_root(tmp_path):
    """A harvest cache holding only export lists, which is all the frame reads."""
    root = tmp_path / "cache"
    (root / "cran").mkdir(parents=True)
    for package, exports in FAKE_EXPORTS.items():
        (root / "cran" / f"{package}.json").write_text(
            json.dumps(
                {
                    "package": package,
                    "ecosystem": "cran",
                    "releases": [],
                    "news_text": "",
                    "news_source": "",
                    "exports": exports,
                    "errors": [],
                }
            )
        )
    return root


class TestExtractPython:
    def test_resolves_aliased_module_imports(self, tmp_path):
        path = write(
            tmp_path,
            "a.py",
            "import statsmodels.api as sm\nsm.OLS(y, X).fit()\n",
        )
        (site,) = [s for s in extract_python([path]).call_sites if s.fname == "OLS"]
        assert site.qualifier == "statsmodels.api"

    def test_resolves_from_imports_of_bare_names(self, tmp_path):
        path = write(
            tmp_path,
            "a.py",
            "from sklearn.linear_model import LogisticRegression\n"
            "LogisticRegression().fit(x, y)\n",
        )
        (site,) = [
            s
            for s in extract_python([path]).call_sites
            if s.fname == "LogisticRegression"
        ]
        assert site.qualifier == "sklearn.linear_model"

    def test_unimported_callee_is_left_unattributed(self, tmp_path):
        # `df.index()` must not be mistaken for a package function; this is what
        # made the first version of the frame attribute pandas methods to plm.
        path = write(tmp_path, "a.py", "df = load()\ndf.index()\n")
        sites = {s.fname: s for s in extract_python([path]).call_sites}
        assert sites["index"].qualifier == ""

    def test_deep_module_path_is_preserved(self, tmp_path):
        path = write(tmp_path, "a.py", "import scipy\nscipy.stats.norm.ppf(0.975)\n")
        (site,) = [s for s in extract_python([path]).call_sites if s.fname == "ppf"]
        assert site.qualifier == "scipy.stats.norm"

    def test_counts_repeated_calls(self, tmp_path):
        path = write(tmp_path, "a.py", "import numpy as np\nnp.mean(x)\nnp.mean(y)\n")
        (site,) = [s for s in extract_python([path]).call_sites if s.fname == "mean"]
        assert site.n == 2

    def test_unparseable_file_is_counted_not_raised(self, tmp_path):
        path = write(tmp_path, "bad.py", "def (:\n")
        report = extract_python([path])
        assert report.files_failed == 1
        assert report.files_parsed == 0
        assert report.parse_rate == 0.0


@pytest.mark.slow
class TestExtractR:
    def test_finds_calls_and_namespace_qualifiers(self, tmp_path):
        path = write(
            tmp_path,
            "a.R",
            "m <- lm(y ~ x, data = d)\nv <- sandwich::vcovHC(m, type='HC1')\n",
        )
        sites = {s.fname: s for s in extract_r([path]).call_sites}
        assert sites["lm"].qualifier == ""
        assert sites["vcovHC"].qualifier == "sandwich"

    def test_name_in_a_string_or_comment_is_not_a_call(self, tmp_path):
        # The whole reason for using R's parser instead of grep.
        path = write(
            tmp_path,
            "a.R",
            '# we could use coxph here\nmsg <- "call coxph(x)"\nlm(y ~ x)\n',
        )
        names = {s.fname for s in extract_r([path]).call_sites}
        assert "lm" in names
        assert "coxph" not in names

    def test_variable_sharing_a_function_name_is_not_a_call(self, tmp_path):
        path = write(tmp_path, "a.R", "glm <- 5\nprint(glm)\n")
        names = {s.fname for s in extract_r([path]).call_sites}
        assert "glm" not in names

    def test_unparseable_file_is_counted(self, tmp_path):
        good = write(tmp_path, "good.R", "lm(y ~ x)\n")
        bad = write(tmp_path, "bad.R", "lm(y ~ x\n")
        report = extract_r([good, bad])
        assert report.files_parsed == 1
        assert report.files_failed == 1


class TestAttributePython:
    def test_matches_a_submodule_to_its_package(self):
        assert attribute_python("statsmodels.api") == "statsmodels"
        assert attribute_python("scipy.stats.norm") == "scipy.stats"

    def test_does_not_match_a_mere_prefix_string(self):
        # "scipy.statsomething" is not under "scipy.stats".
        assert attribute_python("scipy.statsomething") is None

    def test_unknown_and_empty_return_none(self):
        assert attribute_python("pandas") is None
        assert attribute_python("") is None


class TestBuildFrame:
    def test_python_calls_are_not_attributed_via_r_exports(self, cache_root):
        # `index` is exported by plm. A pandas method called `index` must not be
        # counted as a plm call.
        sites = [CallSite("a.py", "index", "", 1, "Python")]
        frame = build_frame(sites, {"Python": 1}, cache_root, packages=["plm"])
        assert frame.rows == []

    def test_shadowed_name_needs_a_matching_qualifier(self, cache_root):
        sites = [
            CallSite("a.R", "select", "", 1, "R"),
            CallSite("b.R", "select", "dplyr", 1, "R"),
            CallSite("c.R", "select", "MASS", 1, "R"),
        ]
        frame = build_frame(sites, {"R": 3}, cache_root, packages=["MASS"])
        (row,) = frame.rows
        assert row.fname == "select"
        assert row.scripts == 1  # only c.R, the one that said MASS::
        assert frame.shadow_dropped == 2

    def test_counts_distinct_scripts_not_total_calls(self, cache_root):
        sites = [
            CallSite("a.R", "lm", "", 200, "R"),
            CallSite("b.R", "lm", "", 1, "R"),
        ]
        (row,) = build_frame(sites, {"R": 2}, cache_root, packages=["stats"]).rows
        assert row.scripts == 2
        assert row.calls == 201
        assert row.share == 1.0

    def test_non_computing_names_are_excluded(self, cache_root):
        sites = [CallSite("a.R", "summary", "", 1, "R")]
        assert build_frame(sites, {"R": 1}, cache_root, packages=["stats"]).rows == []

    def test_ambiguous_name_records_every_owner(self, cache_root):
        sites = [CallSite("a.R", "vcovHC", "", 1, "R")]
        frame = build_frame(sites, {"R": 1}, cache_root, packages=["sandwich", "plm"])
        (row,) = frame.rows
        assert row.ambiguous
        assert set(row.packages) == {"sandwich", "plm"}

    def test_unattributed_names_are_reported_not_silently_dropped(self, cache_root):
        sites = [CallSite("a.R", "ggplot", "", 1, "R")]
        frame = build_frame(sites, {"R": 1}, cache_root, packages=["stats"])
        assert frame.rows == []
        assert ("ggplot", 1) in frame.unattributed_top

    def test_reports_packages_whose_exports_did_not_resolve(self, cache_root):
        # A package contributing nothing because its export list is empty must
        # not be mistaken for a package nobody calls.
        frame = build_frame([], {"R": 0}, cache_root, packages=["sandwich", "empty"])
        assert frame.no_exports == ["empty"]


def test_shadowed_and_non_computing_do_not_overlap():
    # A name in both would be dropped twice over, and the shadow count would be
    # misleading.
    assert not (SHADOWED & NON_COMPUTING)


class TestPackageLoads:
    def test_r_load_forms(self):
        from kasauti.archaeology.loads import loads_in

        source = (
            'library(fixest)\nrequire("dplyr")\n'
            "suppressMessages(library(lme4))\nx <- MASS::ginv(m)\n"
        )
        assert loads_in(source, "R") == {"fixest", "dplyr", "lme4", "MASS"}

    def test_python_load_forms_record_the_distribution(self):
        from kasauti.archaeology.loads import loads_in

        source = (
            "import numpy as np\nfrom statsmodels.api import OLS\n"
            "import scipy.stats\nfrom sklearn.linear_model import LogisticRegression\n"
        )
        assert loads_in(source, "Python") == {
            "numpy",
            "statsmodels",
            "scipy",
            "sklearn",
        }

    def test_loads_roll_up_to_the_archive(self):
        from kasauti.archaeology.loads import by_archive

        rolled = by_archive({"/a/master.R": {"lfe"}, "/a/analysis.R": set()})
        assert rolled["/a"] == {"lfe"}
