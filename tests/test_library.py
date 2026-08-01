"""Building an archived version once, and remembering what would not build."""

from pathlib import Path

import pytest

from kasauti.archaeology import library
from kasauti.archaeology.library import BUILT, FAILED, Build, Ledger


@pytest.fixture
def ledger(tmp_path):
    return Ledger.load(tmp_path / "builds.csv")


def populated(root: Path, package: str, version: str) -> Path:
    """Create a library directory that looks like a successful install."""
    lib = root / f"{package}_{version}"
    (lib / package).mkdir(parents=True)
    return lib


class TestLedger:
    def test_a_recorded_build_survives_a_round_trip(self, tmp_path):
        path = tmp_path / "builds.csv"
        first = Ledger.load(path)
        first.record(
            Build("sandwich", "2.2-1", FAILED, "4.6.0", "macOS", "no NAMESPACE")
        )

        again = Ledger.load(path)
        found = again.get("sandwich", "2.2-1")
        assert found is not None
        assert found.outcome == FAILED
        assert found.detail == "no NAMESPACE"

    def test_it_is_written_on_every_record_not_at_the_end(self, tmp_path):
        # A sweep is a long unattended run. A ledger that only lands when the run
        # finishes is exactly the one lost when it does not.
        path = tmp_path / "builds.csv"
        Ledger.load(path).record(Build("plm", "1.5-12", BUILT))
        assert path.exists()

    def test_an_unrecorded_version_is_unknown_not_failed(self, ledger):
        assert ledger.get("plm", "9.9-9") is None


class TestEnsure:
    def test_an_installed_version_is_returned_without_building(
        self, tmp_path, ledger, monkeypatch
    ):
        monkeypatch.setattr(
            library, "install", lambda *a, **k: pytest.fail("should not build")
        )
        monkeypatch.setattr(library, "r_version", lambda: "4.6.0")
        lib = populated(tmp_path, "sandwich", "2.4-0")

        found, _ = library.ensure("sandwich", "2.4-0", ledger, root=tmp_path)
        assert found == lib
        assert (ledger.get("sandwich", "2.4-0") or Build("", "", "")).outcome == BUILT

    def test_a_recorded_failure_is_not_attempted_again(
        self, tmp_path, ledger, monkeypatch
    ):
        # The measurement that matters most and costs most. `fixest` before
        # mid-2021 spends its whole timeout failing to compile; paying that once
        # per bisect, per screen, and per sweep is what made the old install
        # unaffordable at this scale.
        monkeypatch.setattr(
            library, "install", lambda *a, **k: pytest.fail("should not retry")
        )
        ledger.record(
            Build("fixest", "0.8.0", FAILED, detail="parallel_funs.o Error 1")
        )

        found, detail = library.ensure("fixest", "0.8.0", ledger, root=tmp_path)
        assert found is None
        assert detail == "parallel_funs.o Error 1"

    def test_the_recorded_reason_survives_rather_than_being_reinvented(
        self, tmp_path, ledger, monkeypatch
    ):
        monkeypatch.setattr(library, "install", lambda *a, **k: pytest.fail("no"))
        ledger.record(
            Build("fixest", "0.8.0", FAILED, detail="a NAMESPACE is required")
        )
        assert (
            "NAMESPACE" in library.ensure("fixest", "0.8.0", ledger, root=tmp_path)[1]
        )

    def test_retry_overrides_a_recorded_failure(self, tmp_path, ledger, monkeypatch):
        # The only thing that can change the answer is a changed toolchain, so
        # the override exists but is never the default.
        calls = []
        monkeypatch.setattr(library, "r_version", lambda: "4.7.0")

        def build(package, version, root=None, timeout=900):
            calls.append(version)
            return populated(root or tmp_path, package, version), ""

        monkeypatch.setattr(library, "install", build)
        ledger.record(Build("fixest", "0.8.0", FAILED, "4.6.0"))

        found, _ = library.ensure("fixest", "0.8.0", ledger, root=tmp_path, retry=True)
        assert calls == ["0.8.0"]
        assert found is not None
        assert (ledger.get("fixest", "0.8.0") or Build("", "", "")).outcome == BUILT

    def test_a_fresh_failure_is_recorded_so_it_is_paid_for_once(
        self, tmp_path, ledger, monkeypatch
    ):
        monkeypatch.setattr(library, "r_version", lambda: "4.6.0")
        monkeypatch.setattr(library, "install", lambda *a, **k: (None, "build failed"))

        library.ensure("sandwich", "1.0-0", ledger, root=tmp_path)
        recorded = Ledger.load(tmp_path / "builds.csv").get("sandwich", "1.0-0")
        assert recorded is not None
        assert recorded.outcome == FAILED
        assert recorded.r_version == "4.6.0"


class TestFailureDetail:
    def test_the_compiler_line_is_kept_over_the_wrapper_message(self):
        # Every failed install ends with "had non-zero exit status", which is
        # true of all of them and explains none. `unknown type name 'Sint'` is
        # what puts every survival before 3.4-0 out of reach; keeping the tail
        # of the log loses exactly that.
        log = (
            "* installing *source* package\n"
            "./survproto.h:35:30: error: unknown type name 'Sint'\n"
            "make: *** [agexact.o] Error 1\n"
            "ERROR: compilation failed for package 'survival'\n"
            "In install.packages(...) : had non-zero exit status\n"
        )
        assert library._tidy(log) == (
            "./survproto.h:35:30: error: unknown type name 'Sint'"
        )

    def test_a_log_with_no_error_line_falls_back_to_its_tail(self):
        assert library._tidy("something went wrong quietly") != ""


class TestMissingDependencies:
    def test_one_named_dependency(self):
        # R quotes package names with U+2018/U+2019, written as escapes here so
        # the test says which characters it means.
        log = (
            "ERROR: dependency \u2018mnormt\u2019 is not available "
            "for package \u2018psych\u2019"
        )
        assert library.missing_dependencies(log) == ["mnormt"]

    def test_several_named_dependencies(self):
        # The package's own name follows "for package" and must not be mistaken
        # for one of its dependencies, or the retry would try to fetch a current
        # version of the very package under test.
        log = (
            "ERROR: dependencies \u2018classInt\u2019, \u2018s2\u2019, "
            "\u2018units\u2019 are not available for package \u2018sf\u2019"
        )
        assert library.missing_dependencies(log) == ["classInt", "s2", "units"]

    def test_a_toolchain_failure_names_nothing(self):
        # The distinction the retry rests on: a missing import is an accident of
        # this machine, an undeclared C function is a wall.
        log = "classTree.c:302:36: error: call to undeclared function 'Calloc'"
        assert library.missing_dependencies(log) == []


class TestAdopt:
    def test_versions_already_on_disk_are_recorded(self, tmp_path, ledger, monkeypatch):
        monkeypatch.setattr(library, "r_version", lambda: "4.6.0")
        populated(tmp_path, "sandwich", "2.4-0")
        populated(tmp_path, "plm", "1.5-12")

        assert library.adopt(ledger, root=tmp_path) == 2
        assert (ledger.get("plm", "1.5-12") or Build("", "", "")).outcome == BUILT

    def test_an_empty_directory_is_not_a_failure(self, tmp_path, ledger, monkeypatch):
        # `install` creates the directory before building, so an empty one means
        # a build was attempted -- not that the version is unbuildable. Recording
        # it as FAILED would fabricate a measurement nobody made.
        monkeypatch.setattr(library, "r_version", lambda: "4.6.0")
        (tmp_path / "sandwich_2.2-1").mkdir()

        assert library.adopt(ledger, root=tmp_path) == 0
        assert ledger.get("sandwich", "2.2-1") is None


class TestReach:
    def test_the_floor_is_the_oldest_version_known_to_build(self, ledger):
        for version, outcome in [
            ("1.0-0", FAILED),
            ("1.1-0", FAILED),
            ("1.2-0", BUILT),
            ("1.3-0", BUILT),
        ]:
            ledger.record(Build("p", version, outcome))
        versions = ["1.0-0", "1.1-0", "1.2-0", "1.3-0"]
        assert library.floor("p", versions, ledger) == "1.2-0"

    def test_the_floor_follows_release_order_not_string_order(self, ledger):
        # `1.5-13` sorts before `1.5-9` as a string. The release history knows
        # better, so it is the release history that is asked.
        ledger.record(Build("plm", "1.5-9", BUILT))
        ledger.record(Build("plm", "1.5-13", BUILT))
        assert library.floor("plm", ["1.5-9", "1.5-13"], ledger) == "1.5-9"

    def test_untried_versions_are_counted_apart_from_failures(self, ledger):
        ledger.record(Build("p", "1.0-0", FAILED))
        ledger.record(Build("p", "1.1-0", BUILT))
        assert library.reach("p", ["1.0-0", "1.1-0", "1.2-0"], ledger) == {
            "tried": 2,
            "built": 1,
            "failed": 1,
            "untried": 1,
        }


class TestSubstitute:
    def test_the_library_slot_is_replaced(self, monkeypatch):
        monkeypatch.setenv(library.ROOT_VARIABLE, "/var/rlibs")
        cmd = ["Rscript", "--vanilla", "run_r.R", "${KASAUTI_RLIBS}/sandwich_2.4-0"]
        assert library.substitute(cmd, Path("/var/rlibs/sandwich_2.2-1")) == [
            "Rscript",
            "--vanilla",
            "run_r.R",
            "/var/rlibs/sandwich_2.2-1",
        ]

    def test_a_command_with_no_library_slot_is_refused(self):
        # Returning it unchanged would run the reproducer against whatever
        # version happens to be installed and report the answer as if it had
        # come from the one that was asked for.
        with pytest.raises(ValueError, match="no argument names the version library"):
            library.substitute(["Rscript", "run_r.R"], Path("/var/rlibs/plm_1.5-12"))

    def test_a_resolved_path_under_the_root_also_counts(self, monkeypatch):
        monkeypatch.setenv(library.ROOT_VARIABLE, "/var/rlibs")
        cmd = ["Rscript", "run_r.R", "/var/rlibs/plm_1.5-12"]
        assert library.substitute(cmd, Path("/var/rlibs/plm_1.4-0"))[-1] == (
            "/var/rlibs/plm_1.4-0"
        )
