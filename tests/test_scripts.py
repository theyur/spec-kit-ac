"""Tests for the payload workflow scripts, each run as an installed script in a temp project."""

import importlib.util
import json
import shutil
import subprocess
import sys

import pytest

from acproject import (AC, CONFIG, EXTENSION, FEATURE_FOLDERS, PAYLOAD, feature_setup, feature_tag,
                       make_project, run_script, write)

S1, S2 = "specs/001-alpha", "specs/002-beta"


@pytest.fixture
def project(tmp_path):
    return make_project(tmp_path / "proj").resolve()


def ok(result):
    assert result.returncode == 0, result.stderr
    return result.stdout


def failed(result, code=1, text=""):
    assert result.returncode == code, f"expected exit {code}, got {result.returncode}\n{result.stdout}{result.stderr}"
    assert text in result.stdout + result.stderr
    return result.stderr


# ---- ac_feature.py / feature resolution ------------------------------------------------------------------------

@pytest.mark.parametrize("arg", [None, "F001", "001", "f001", "001-alpha", "specs/001-alpha", "specs\\001-alpha\\",
                                 "ABSOLUTE"])
def test_feature_forms(project, arg):
    args = [] if arg is None else ["--feature", str(project / S1) if arg == "ABSOLUTE" else arg]
    paths = json.loads(ok(run_script(project, "ac_feature.py", *args)))
    assert paths["featureDir"] == S1 and paths["tag"] == "F001"
    assert paths["featuresDir"] == f"{AC}/Features/F001"
    assert paths["sourcesLock"] == f"{S1}/ac/sources.lock"


def test_feature_other(project):
    paths = json.loads(ok(run_script(project, "ac_feature.py", "--feature", "F002")))
    assert paths["featureDir"] == S2 and paths["stepDefinitionsDir"] == f"{AC}/StepDefinitions/F002"


@pytest.mark.parametrize("case", FEATURE_FOLDERS, ids=[c[0] for c in FEATURE_FOLDERS])
def test_feature_folder_rules(project, case):
    _, folder, setup, valid = case
    feature_setup(project, setup)
    result = run_script(project, "ac_feature.py", "--feature", folder)
    if valid:
        paths = json.loads(ok(result))
        assert paths["featureDir"] == folder and paths["tag"] == feature_tag(folder)
    else:
        failed(result, 1, "FAIL")


@pytest.mark.parametrize("setup, arg, text", [
    (None, "01", "at least 3 digits"),
    (None, "specs/login", "does not start with a feature number"),
    (None, "003", "No feature folder"),
    (None, "specs/003-gamma", "not found"),
    ("no-feature-json", None, "No current feature"),
    ("no-config", "001", "config.json not found"),
])
def test_feature_errors(project, setup, arg, text):
    if setup == "no-feature-json":
        (project / ".specify/feature.json").unlink()
    elif setup == "no-config":
        (project / ".workflow/config.json").unlink()
    failed(run_script(project, "ac_feature.py", *(["--feature", arg] if arg else [])), 1, text)


@pytest.mark.parametrize("config", [
    {k: v for k, v in CONFIG.items() if k != "testFramework"},
    {**CONFIG, "testFramework": "xunit"},
], ids=["missing", "unknown"])
def test_config_test_framework_invalid(project, config):
    write(project / ".workflow/config.json", json.dumps(config))
    failed(run_script(project, "ac_feature.py"), 1, "testFramework")


def test_feature_all(project):
    write(project / "specs/010-gamma/spec.md")
    write(project / "specs/README.md")  # files under specs/ are not features
    listing = json.loads(ok(run_script(project, "ac_feature.py", "--all")))
    assert listing == [{"featureDir": S1, "tag": "F001"}, {"featureDir": S2, "tag": "F002"},
                       {"featureDir": "specs/010-gamma", "tag": "F010"}]


def test_feature_all_empty(tmp_path):
    project = make_project(tmp_path / "empty", features=()).resolve()
    assert json.loads(ok(run_script(project, "ac_feature.py", "--all"))) == []


def test_feature_all_with_feature_is_usage_error(project):
    failed(run_script(project, "ac_feature.py", "--all", "--feature", "F001"), 2, "not allowed with")


@pytest.mark.parametrize("case", [c for c in FEATURE_FOLDERS if not c[3] and c[2]], ids=lambda c: c[0])
def test_feature_all_bad_folder(project, case):
    feature_setup(project, case[2])
    failed(run_script(project, "ac_feature.py", "--all"), 1, "FAIL")


def test_spec_inputs_overlapping_protected_folders_fail(project):
    write(project / ".workflow/config.json", json.dumps({**CONFIG, "specInputs": ["tests"]}))
    failed(run_script(project, "ac_feature.py"), 1, "overlaps tests/App.AcceptanceTests")


@pytest.mark.parametrize("change, message", [
    ({"refsDir": "src/refs"}, "refsDir src/refs overlaps the implementation folder src"),
    ({"refsDir": AC}, f"refsDir {AC} overlaps {AC}"),
    ({"acSurfaceProjects": ["../../other/Secret.csproj"]}, "key acSurfaceProjects must be a project-relative path"),
    ({"solution": "C:/elsewhere/App.slnx"}, "key solution must be a project-relative path"),
    ({"acProject": "src/App.Core/App.Core.csproj"}, "must be a .csproj directly inside acProjectDir"),
    ({"acRefBuildCommand": "dotnet build src/App.Core/App.Core.csproj"}, "acRefBuildCommand must be exactly"),
])
def test_unsafe_config_paths_fail(project, change, message):
    """Copilot on HT PR 16: export_refs.py deletes refsDir; dotnet must never get a path outside the checkout."""
    write(project / ".workflow/config.json", json.dumps({**CONFIG, **change}))
    failed(run_script(project, "ac_feature.py"), 1, message)


@pytest.mark.parametrize("spec_input, folder", [("src/App.Core", "src"), ("lib/Core/notes.md", "lib/Core"),
                                                ("lib", "lib/Core")])
def test_spec_inputs_overlapping_the_code_fail(project, spec_input, folder):
    """Copilot on HT PR 16: a hand-edited config must not hand the AC subagents an implementation folder."""
    write(project / "lib/Core/Core.csproj", "<Project />\n")
    write(project / ".workflow/config.json", json.dumps({**CONFIG, "specInputs": [spec_input]}))
    failed(run_script(project, "ac_feature.py"), 1, f"overlaps the implementation folder {folder}")


@pytest.mark.parametrize("script, args", [
    ("ac_lock.py", ["lock", "sources"]), ("ac_lock.py", ["verify", "sources"]),
    ("ac_lock.py", ["confirm-spec", "sources"]), ("ac_lock.py", ["unlock", "sources"]),
    ("check_features.py", []), ("clear_generated.py", ["steps"]), ("record_skips.py", ["translate-001", "AC-002"]),
    ("new_run.py", ["write"]), ("new_analyze.py", []),
])
def test_scripts_print_the_resolved_feature(project, script, args):
    """S02-R06: every per-feature script names the feature folder and tag it acted on."""
    ok(run_script(project, "ac_lock.py", "lock", "sources"))
    write(project / AC / "Features/F001/Login.feature", GOOD)
    write(project / S1 / "ac/runs/translate-001/translation-report.md", REPORT)
    ok(run_script(project, "new_run.py", "write"))
    if script in ("new_run.py", "new_analyze.py"):
        end_run(project)
    out = ok(run_script(project, script, *args))
    assert f"{S1} (F001)" in out


def test_script_outside_an_install_fails(project):
    # -B: no __pycache__ inside the payload (it would be shipped and installed with it).
    result = subprocess.run([sys.executable, "-I", "-B", str(PAYLOAD / "scripts" / "ac_feature.py")], cwd=project,
                            capture_output=True, text=True)
    failed(result, 1, "is not installed under")


# ---- ac_lock.py --------------------------------------------------------------------------------------------------

def test_sources_lock_verify_and_drift(project):
    write(project / AC / "Samples/F001/in.bin", "sample")
    out = ok(run_script(project, "ac_lock.py", "lock", "sources"))
    assert "Locked 3 sources file(s)" in out  # acceptance.md, .gitkeep, in.bin
    lock = json.loads((project / S1 / "ac/sources.lock").read_text(encoding="utf-8"))
    assert lock["group"] == "sources" and lock["feature"] == S1 and lock["spec"]["path"] == f"{S1}/spec.md"
    assert f"{AC}/Samples/F001/in.bin" in lock["files"] and f"{S1}/acceptance.md" in lock["files"]
    ok(run_script(project, "ac_lock.py", "verify", "sources"))

    write(project / S1 / "spec.md", "changed spec\n")
    failed(run_script(project, "ac_lock.py", "verify", "sources"), 3, "SPEC DRIFT")
    ok(run_script(project, "ac_lock.py", "confirm-spec", "sources"))
    ok(run_script(project, "ac_lock.py", "verify", "sources"))

    write(project / AC / "Samples/F001/in.bin", "other")
    write(project / AC / "Samples/F001/new.bin", "new")
    (project / S1 / "acceptance.md").unlink()
    failed(run_script(project, "ac_lock.py", "verify", "sources"), 1, "not found")
    write(project / S1 / "acceptance.md", "edited\n")
    err = failed(run_script(project, "ac_lock.py", "verify", "sources"), 1)
    assert f"added: {AC}/Samples/F001/new.bin" in err and f"changed: {AC}/Samples/F001/in.bin" in err
    assert f"changed: {S1}/acceptance.md" in err
    failed(run_script(project, "ac_lock.py", "confirm-spec", "sources"), 1, "differ from the lock")

    ok(run_script(project, "ac_lock.py", "unlock", "sources"))
    assert not (project / S1 / "ac/sources.lock").exists()
    failed(run_script(project, "ac_lock.py", "verify", "sources"), 1, "not locked")


def test_spec_drift_ignored_for_other_features(project):
    ok(run_script(project, "ac_lock.py", "lock", "sources"))
    write(project / S2 / "spec.md", "002 changed\n")
    ok(run_script(project, "ac_lock.py", "verify", "sources"))


def test_features_lock(project):
    failed(run_script(project, "ac_lock.py", "lock", "features"), 1, "no .feature file")
    write(project / AC / "Features/F001/A.feature", "@F001\nFeature: A\n")
    ok(run_script(project, "ac_lock.py", "lock", "features"))
    lock = json.loads((project / S1 / "ac/features.lock").read_text(encoding="utf-8"))
    assert "spec" not in lock and f"{AC}/Features/F001/A.feature" in lock["files"]
    ok(run_script(project, "ac_lock.py", "verify", "features"))
    write(project / AC / "Features/F002/B.feature", "@F002\nFeature: B\n")  # another feature: not part of the lock
    ok(run_script(project, "ac_lock.py", "verify", "features"))
    (project / AC / "Features/F001/A.feature").unlink()
    failed(run_script(project, "ac_lock.py", "verify", "features"), 1, "no .feature file")
    failed(run_script(project, "ac_lock.py", "confirm-spec", "features"), 1, "sources only")


def test_lock_usage_error(project):
    assert run_script(project, "ac_lock.py", "lock", "everything").returncode == 2  # argparse


# ---- new_run.py / new_analyze.py -------------------------------------------------------------------------------

def end_run(project):
    """The run is over, as after `changed_files.py check`: a new run script may start (option B, step 8)."""
    ok(run_script(project, "changed_files.py", "clear"))


def marker(project):
    return json.loads((project / ".workflow/active-run.json").read_text(encoding="utf-8"))


def test_runs_and_markers(project):
    failed(run_script(project, "new_analyze.py"), 1, "no run folder")
    assert ok(run_script(project, "new_run.py", "translate")).splitlines()[0] == f"{S1}/ac/runs/translate-001"
    assert marker(project) == {"role": "ac-feature-translator", "feature": S1, "tag": "F001", "run": "translate-001",
                               "analyze": None}
    failed(run_script(project, "new_run.py", "translate"), 1,
           f"An AC run is still active (ac-feature-translator translate-001 of {S1}")  # option B: never replaced
    assert not (project / S1 / "ac/runs/translate-002").exists()  # refused before any folder is created
    end_run(project)
    assert ok(run_script(project, "new_run.py", "translate")).startswith(f"{S1}/ac/runs/translate-002")

    end_run(project)
    assert ok(run_script(project, "new_run.py", "write")).startswith(f"{S1}/ac/runs/run-001")
    assert marker(project)["role"] == "ac-test-writer" and marker(project)["run"] == "run-001"
    end_run(project)
    assert ok(run_script(project, "new_analyze.py")).startswith(f"{S1}/ac/runs/run-001/analyze-1")
    assert marker(project) == {"role": "ac-test-fail-judge", "feature": S1, "tag": "F001", "run": "run-001",
                               "analyze": "analyze-1"}
    end_run(project)
    assert ok(run_script(project, "new_analyze.py")).startswith(f"{S1}/ac/runs/run-001/analyze-2")

    write(project / S1 / "ac/runs/run-001/analyze-2/writer-feedback.md", "fix the table\n")
    end_run(project)
    ok(run_script(project, "new_run.py", "write"))
    assert (project / S1 / "ac/runs/run-002/input-feedback.md").read_text(encoding="utf-8") == "fix the table\n"

    # numbering is per feature
    end_run(project)
    assert ok(run_script(project, "new_run.py", "write", "--feature", "002")).startswith(f"{S2}/ac/runs/run-001")
    assert marker(project)["feature"] == S2 and marker(project)["tag"] == "F002"


@pytest.mark.parametrize("content, needle", [
    (json.dumps({"role": "ac-test-writer", "feature": S1, "tag": "F001", "run": "run-007", "analyze": None}),
     f"(ac-test-writer run-007 of {S1}; .workflow/active-run.json)"),
    (json.dumps({"role": "ac-test-writer", "feature": "specs/999-speckit-ac-smoke", "tag": "F999", "run": "run-001",
                 "analyze": None, "smoke": True}), "`smoke_test.py end <role>`"),
    ("{broken", "(unreadable marker;"),
])
def test_run_scripts_refuse_an_active_run(project, content, needle):
    """Step 8, option B (user): a run script never replaces another run's marker; a background subagent may still be
    working on it. The message says how to end the run once nothing is running."""
    write(project / ".workflow/active-run.json", content)
    for args in (["new_run.py", "translate"], ["new_run.py", "write"], ["new_analyze.py"]):
        result = run_script(project, *args)
        failed(result, 1, "An AC run is still active")
        assert needle in result.stderr
    assert not (project / S1 / "ac/runs").exists()  # nothing created
    assert (project / ".workflow/active-run.json").read_text(encoding="utf-8") == content


def test_write_run_without_feedback(project):
    ok(run_script(project, "new_run.py", "write"))
    end_run(project)
    ok(run_script(project, "new_analyze.py"))
    end_run(project)
    ok(run_script(project, "new_run.py", "write"))
    assert not (project / S1 / "ac/runs/run-002/input-feedback.md").exists()


# ---- changed_files.py ------------------------------------------------------------------------------------------

@pytest.fixture
def git_project(project):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    return project


def test_changed_files_allowlist(git_project):
    p = git_project
    marker = p / ".workflow/active-run.json"
    ok(run_script(p, "new_run.py", "write"))
    failed(run_script(p, "changed_files.py", "check", "ac-test-writer"), 1, "no snapshot")
    assert marker.is_file()  # a usage error keeps the active run
    ok(run_script(p, "changed_files.py", "snapshot"))
    write(p / AC / "StepDefinitions/F002/Fix.cs")
    write(p / AC / "Support/Shared/Ctx.cs")
    write(p / S1 / "ac/runs/run-001/writer-report.md")
    write(p / AC / "bin/Debug/x.dll")
    write(p / AC / "obj-ref/x.cs")
    write(p / ".workflow/guard.log")
    out = ok(run_script(p, "changed_files.py", "check", "ac-test-writer"))
    assert "OUTSIDE" not in out and "bin/Debug" not in out and "guard.log" not in out
    assert not marker.exists()  # the run is over

    ok(run_script(p, "new_run.py", "write"))  # run-002, created before the snapshot
    ok(run_script(p, "changed_files.py", "snapshot"))
    write(p / "src/App.Core/Leak.cs")
    write(p / AC / "Bindings/x.cs")  # not a build folder: must be seen
    write(p / S1 / "ac/runs/run-003/writer-report.md")  # another run's report
    result = run_script(p, "changed_files.py", "check", "ac-test-writer")
    failed(result, 1, "isolation breach, 3 file(s)")
    breaches = {line.split(": ", 1)[1].split()[0] for line in result.stdout.splitlines() if "OUTSIDE ALLOWLIST" in line}
    assert breaches == {"src/App.Core/Leak.cs", f"{AC}/Bindings/x.cs", f"{S1}/ac/runs/run-003/writer-report.md"}
    assert not marker.exists()  # deleted on a breach too

    ok(run_script(p, "new_run.py", "write"))
    failed(run_script(p, "changed_files.py", "check", "ac-test-fail-judge"), 1, "active run is for ac-test-writer")
    assert marker.is_file()


def test_changed_files_clear_ends_a_run_without_a_subagent(project):
    """Copilot on HT PR 16: tests-analyze stopping before the judge (all passed) must not leave its marker behind."""
    marker = project / ".workflow/active-run.json"
    assert "No active run" in ok(run_script(project, "changed_files.py", "clear"))
    ok(run_script(project, "new_run.py", "write"))  # tests-analyze needs a writer run first
    end_run(project)
    ok(run_script(project, "new_analyze.py"))
    assert marker.is_file()
    assert "Active run ended" in ok(run_script(project, "changed_files.py", "clear")) and not marker.exists()
    write(marker, json.dumps({"smoke": True, "role": "ac-test-writer"}))
    failed(run_script(project, "changed_files.py", "clear"), 1, "smoke-test marker")
    assert marker.is_file()  # smoke_test.py end owns it


def test_changed_files_feature_files_and_ignored_folders(git_project):
    p = git_project
    write(p / ".gitignore", "artifacts/\nspecs/*/ac/runs/\n")
    ok(run_script(p, "new_run.py", "write"))
    ok(run_script(p, "changed_files.py", "snapshot"))
    write(p / AC / "StepDefinitions/F001/Extra.feature")
    write(p / S2 / "ac/runs/run-001/writer-report.md")  # git-ignored, another feature
    write(p / "artifacts/refs/api/App.Core.cs")  # git-ignored refs
    result = run_script(p, "changed_files.py", "check", "ac-test-writer")
    failed(result, 1, "isolation breach, 3 file(s)")
    breaches = {line.split(": ", 1)[1].split()[0] for line in result.stdout.splitlines() if "OUTSIDE ALLOWLIST" in line}
    assert breaches == {f"{AC}/StepDefinitions/F001/Extra.feature", f"{S2}/ac/runs/run-001/writer-report.md",
                        "artifacts/refs/api/App.Core.cs"}


def test_changed_files_translator(git_project):
    p = git_project
    ok(run_script(p, "new_run.py", "translate"))
    ok(run_script(p, "changed_files.py", "snapshot"))
    write(p / AC / "Features/F001/A.feature")
    write(p / S1 / "ac/runs/translate-001/translation-report.md")
    ok(run_script(p, "changed_files.py", "check", "ac-feature-translator"))
    ok(run_script(p, "new_run.py", "translate"))
    ok(run_script(p, "changed_files.py", "snapshot"))
    write(p / AC / "Features/F002/B.feature")
    write(p / AC / "Features/F001/Steps.cs")
    result = run_script(p, "changed_files.py", "check", "ac-feature-translator")
    failed(result, 1, "isolation breach, 2 file(s)")
    assert f"{AC}/Features/F002/B.feature   <-- OUTSIDE ALLOWLIST" in result.stdout
    assert f"{AC}/Features/F001/Steps.cs   <-- OUTSIDE ALLOWLIST" in result.stdout


# ---- check_features.py -----------------------------------------------------------------------------------------

GOOD = """@F001
Feature: Login

  Background:
    Given a user "ann"

  @AC-001
  Scenario: Login succeeds
    When "ann" logs in with "pw"
    Then the login succeeds

  @AC-002
  Scenario Outline: Login fails
    When "ann" logs in with "<pw>"
    Then the login fails
    Examples:
      | pw |
      | x  |
"""


def check(project, text, name="Login.feature"):
    write(project / AC / "Features/F001" / name, text)
    return run_script(project, "check_features.py")


def test_check_features_ok(project):
    assert "OK: 2 scenario(s) in 1 feature file(s)" in ok(check(project, GOOD))


def test_check_features_other_f_tags_are_not_feature_tags(project):
    text = GOOD.replace("@F001\n", "@F001 @Fixture\n").replace("  @AC-002", "  @AC-002 @Fast")
    assert "OK: 2 scenario(s)" in ok(check(project, text))


@pytest.mark.parametrize("text, problem", [
    (GOOD.replace("@F001\n", ""), "must carry the feature tag @F001"),
    (GOOD.replace("@F001\n", "@F001 @F002\n"), "must carry the feature tag @F001"),
    (GOOD.replace("  @AC-002", "  @AC-002 @F002"), "carries another feature's tag @F002"),
    (GOOD.replace("@AC-002", "@AC-001"), "@AC-001 is used by 2 scenarios"),
    (GOOD.replace("  @AC-002\n", ""), "needs exactly one @AC- tag"),
    (GOOD.replace('    When "ann" logs in with "pw"\n', ""), "needs a When and a Then"),
    (GOOD.replace("    Then the login succeeds", "    Thn the login succeeds"), "not a Gherkin step"),
    # Copilot on HT PR 16: every tag traces to a reviewed item of the feature's acceptance.md
    (GOOD.replace("@AC-002", "@AC-not-an-id"), "@AC-not-an-id is not an AC id"),
    (GOOD.replace("@AC-002", "@AC-999"), "@AC-999 is not an item of specs/001-alpha/acceptance.md"),
])
def test_check_features_problems(project, text, problem):
    failed(check(project, text), 1, problem)


def test_check_features_needs_files(project):
    write(project / AC / "Features/F002/B.feature", GOOD.replace("@F001", "@F002"))
    failed(run_script(project, "check_features.py"), 1, "no .feature file")
    assert "OK" in ok(run_script(project, "check_features.py", "--feature", "002"))


# ---- clear_generated.py ----------------------------------------------------------------------------------------

def test_clear_features(project):
    write(project / AC / "Features/F001/sub/A.feature")
    write(project / AC / "Features/F002/B.feature")
    assert "Removed 1 file(s)" in ok(run_script(project, "clear_generated.py", "features"))
    assert (project / AC / "Features/F001/.gitkeep").exists() and not (project / AC / "Features/F001/sub").exists()
    assert (project / AC / "Features/F002/B.feature").exists()
    write(project / S1 / "ac/features.lock", "{}")
    failed(run_script(project, "clear_generated.py", "features"), 1, "locked")


def test_clear_steps(project):
    for path in ("StepDefinitions/F001/A.cs", "Support/F001/Ctx.cs", "Support/Shared/Shared.cs",
                 "StepDefinitions/F002/B.cs", "Support/F002/C.cs"):
        write(project / AC / path, "secret code\n")
    result = run_script(project, "clear_generated.py", "steps")
    assert "Removed 2 file(s)" in ok(result) and "secret" not in result.stdout + result.stderr
    assert not (project / AC / "StepDefinitions/F001/A.cs").exists() and not (project / AC / "Support/F001/Ctx.cs").exists()
    for path in ("Support/Shared/Shared.cs", "StepDefinitions/F002/B.cs", "Support/F002/C.cs",
                 "StepDefinitions/F001/.gitkeep"):
        assert (project / AC / path).exists(), path


# ---- record_skips.py / extract_feedback.py ---------------------------------------------------------------------

REPORT = """# Translation report

## Issues

| AC id | Kind | Problem |
|---|---|---|
| AC-002 | ambiguous | which unit? |
| AC-004 | missing value | no literal |

## Notes
| AC-009 | not an issue |
"""


def test_record_skips(project):
    write(project / S1 / "ac/runs/translate-001/translation-report.md", REPORT)
    ok(run_script(project, "record_skips.py", "translate-001", "AC-004", "AC-002"))
    skipped = project / S1 / "ac/runs/translate-001/skipped.json"
    assert json.loads(skipped.read_text(encoding="utf-8")) == ["AC-002", "AC-004"]
    failed(run_script(project, "record_skips.py", "translate-001", "AC-009"), 1, "not in the report's Issues table")
    failed(run_script(project, "record_skips.py", "run-001", "AC-002"), 1, "translate-NNN")
    failed(run_script(project, "record_skips.py", "translate-001/../x", "AC-002"), 1, "translate-NNN")
    failed(run_script(project, "record_skips.py", "translate-001", "AC-002", "--feature", "002"), 1, "not found")


def test_extract_feedback(project, tmp_path):
    report, out = tmp_path / "judge-report.md", tmp_path / "writer-feedback.md"
    write(report, "x\n<!-- WRITER-FEEDBACK:BEGIN -->\n  Use the table.\n<!-- WRITER-FEEDBACK:END -->\ny\n")
    ok(run_script(project, "extract_feedback.py", str(report), str(out)))
    assert out.read_text(encoding="utf-8") == "Use the table.\n"
    write(report, "no markers\n")
    ok(run_script(project, "extract_feedback.py", str(report), str(out)))
    assert out.read_text(encoding="utf-8").startswith("No feedback")


# ---- summarize_trx.py ------------------------------------------------------------------------------------------

TRX = """<?xml version="1.0" encoding="utf-8"?>
<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <Results>
    <UnitTestResult testId="1" testName="Login succeeds" outcome="Passed" duration="00:00:00.01" />
    <UnitTestResult testId="2" testName="Login fails(x)" outcome="Failed" duration="00:00:00.02">
      <Output>
        <ErrorInfo>
          <Message>Expected 1 but was 2</Message>
          <StackTrace>   at Steps.Then() in {ac}/StepDefinitions/F001/LoginSteps.cs:line 12
   at App.Core.Login.Run() in {root}/src/App.Core/Login.cs:line 40
   at App.Core.Login.Inner() in {root}/src/App.Core/Login.cs:line 50</StackTrace>
        </ErrorInfo>
      </Output>
    </UnitTestResult>
    <UnitTestResult testId="3" testName="Shared name" outcome="Failed" duration="00:00:00.03" />
    <UnitTestResult testId="4" testName="Shared name" outcome="Passed" duration="00:00:00.04" />
    <UnitTestResult testId="5" testName="Only in beta" outcome="Failed" duration="00:00:00.05">
      <Output><ErrorInfo><Message>No matching step definition found. MissingStepDefinitionException</Message></ErrorInfo></Output>
    </UnitTestResult>
  </Results>
  <TestDefinitions>
    <UnitTest id="1"><TestMethod className="App.AcceptanceTests.Features.F001.LoginFeature" name="LoginSucceeds" /></UnitTest>
    <UnitTest id="2"><TestMethod className="App.AcceptanceTests.Features.F001.LoginFeature" name="LoginFails" /></UnitTest>
    <UnitTest id="3"><TestMethod className="App.AcceptanceTests.Features.F002.OtherFeature" name="SharedName" /></UnitTest>
    <UnitTest id="4"><TestMethod className="App.AcceptanceTests.OtherFeature" name="SharedName" /></UnitTest>
    <UnitTest id="5"><TestMethod className="App.AcceptanceTests.BetaFeature" name="OnlyInBeta" /></UnitTest>
  </TestDefinitions>
</TestRun>
"""


@pytest.fixture
def trx_project(project):
    write(project / AC / "Features/F001/Login.feature",
          "@F001\nFeature: Login\n\n@AC-001\nScenario: Login succeeds\n\n@AC-002\nScenario Outline: Login fails\n\n"
          "@AC-003\nScenario: Shared name\n")
    write(project / AC / "Features/F002/Other.feature",
          "@F002\nFeature: Other\n\n@AC-001\nScenario: Shared name\n\n@AC-002\nScenario: Only in beta\n")
    trx = project / "ac-results.trx"
    write(trx, TRX.replace("{ac}", str(project / AC)).replace("{root}", str(project)))
    return project


def test_summarize_trx_without_results_fails(trx_project):
    """Copilot on HT PR 16: zero results must never read as "every test passed"."""
    p = trx_project
    write(p / "empty.trx", '<?xml version="1.0"?><TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/'
                           '2010"><Results /></TestRun>')
    failed(run_script(p, "summarize_trx.py", "empty.trx", "ac-results.md"), 1, "no test results")
    failed(run_script(p, "summarize_trx.py", "ac-results.trx", "ac-results.md", "--current", "F003"), 1,
           "no result of the current feature F003")
    assert not (p / "ac-results.md").exists()


def test_summarize_trx(trx_project):
    p = trx_project
    out = ok(run_script(p, "summarize_trx.py", "ac-results.trx", "ac-results.md"))
    assert "5 test(s), passed 2, failed 2, pending 1, skipped 0" in out
    md = (p / "ac-results.md").read_text(encoding="utf-8")
    assert "| F001 | Login succeeds | @F001 @AC-001 | passed |" in md
    assert "| F002 | Shared name | @F002 @AC-001 | failed |" in md  # namespace segment wins
    assert "| ? | Shared name | (ambiguous: F001, F002) | passed |" in md  # no segment, two features
    assert "| F002 | Only in beta | @F002 @AC-002 | pending |" in md  # no segment, one feature
    assert "## F001/AC-002 Login fails(x) — failed" in md
    assert "LoginSteps.cs:line 12" in md and "Login.cs" not in md and md.count("[non-AC frame(s) hidden]") == 1


def test_summarize_trx_nunit_test_names(project):
    """NUnit names tests after the generated method, not the scenario title (found in step 5's real runs): the
    match ignores case, spaces and punctuation, and an outline row takes the longest matching title."""
    write(project / AC / "Features/F001/Calc.feature",
          "@F001\nFeature: Calc\n\n@AC-001\nScenario: Doubling\n\n@AC-002\nScenario Outline: Doubling other numbers\n\n"
          "@AC-003\nScenario: Unbound step\n")
    rows = [("1", "Doubling", "Passed"), ("2", 'DoublingOtherNumbers("3","6","1",null)', "Passed"),
            ("3", "UnboundStep", "Passed")]
    results = "".join(f'<UnitTestResult testId="{i}" testName="{n.replace(chr(34), "&quot;")}" outcome="{o}" />'
                      for i, n, o in rows)
    tests = "".join(f'<UnitTest id="{i}"><TestMethod className="App.AcceptanceTests.Features.F001.CalcFeature" /></UnitTest>'
                    for i, _, _ in rows)
    write(project / "ac-results.trx", '<?xml version="1.0" encoding="utf-8"?>\n<TestRun xmlns="http://microsoft.com/'
          f'schemas/VisualStudio/TeamTest/2010"><Results>{results}</Results><TestDefinitions>{tests}</TestDefinitions>'
          "</TestRun>\n")
    ok(run_script(project, "summarize_trx.py", "ac-results.trx", "ac-results.md"))
    md = (project / "ac-results.md").read_text(encoding="utf-8")
    assert "| F001 | Doubling | @F001 @AC-001 | passed |" in md
    assert '| F001 | DoublingOtherNumbers("3","6","1",null) | @F001 @AC-002 | passed |' in md
    assert "| F001 | UnboundStep | @F001 @AC-003 | passed |" in md


def test_summarize_trx_current(trx_project):
    p = trx_project
    ok(run_script(p, "summarize_trx.py", "ac-results.trx", "ac-results.md", "--current", "F002"))
    md = (p / "ac-results.md").read_text(encoding="utf-8")
    current, regression = md.split("## Regression (other features)")
    assert "## Current feature (F002)" in current and "Only in beta" in current and "Login succeeds" not in current
    assert "Login succeeds" in regression and "### F001/AC-002 Login fails(x) — failed" in regression
    failed(run_script(p, "summarize_trx.py", "ac-results.trx", "x.md", "--current", "beta"), 1, "feature tag")


# ---- export_refs.py (pure functions; the dotnet path runs in step 7) --------------------------------------------

@pytest.fixture(scope="module")
def export_refs():
    # No bytecode: a __pycache__ inside the payload would be shipped and installed with it.
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location("export_refs", PAYLOAD / "scripts" / "export_refs.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


LISTING = """using System;
using App.Core.Internal;

namespace App.Core
{
\tpublic class Api
\t{
\t\tpublic int Run(string input)
\t\t{
\t\t\tthrow null;
\t\t}
\t}
\t[Serializable]
\tinternal class Hidden
\t{
\t\tpublic void X()
\t\t{
\t\t\tthrow null;
\t\t}
\t}
}
namespace App.Core.Internal
{
\tinternal sealed class Only
\t{
\t}
}
"""


def test_public_only(export_refs):
    out = export_refs.public_only(LISTING)
    assert "public class Api" in out and "Hidden" not in out and "[Serializable]" not in out
    assert "namespace App.Core.Internal" not in out and "using App.Core.Internal;" not in out
    assert not [line for line in out.splitlines() if export_refs.NON_PUBLIC.match(line)]


def test_logic_detection(export_refs):
    assert export_refs.LOGIC.search("\t\t\treturn x;")
    assert export_refs.LOGIC.search("if (a)")
    assert not export_refs.LOGIC.search("\t\t\tthrow null;")


def test_internals_visible_to_found_in_folders_named_like_build_output(export_refs, tmp_path, monkeypatch):
    """Copilot on HT PR 16: Bindings/ or objectives/ are source folders; only bin/, obj/, obj-ref/ … are skipped."""
    monkeypatch.setattr(export_refs, "ROOT", tmp_path)
    project = tmp_path / "src/Core/Core.csproj"
    for rel, text in [("src/Core/Core.csproj", "<Project />"), ("src/Core/obj-ref/Gen.cs", "InternalsVisibleTo"),
                      ("src/Core/bin/Debug/Gen.cs", "InternalsVisibleTo")]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    export_refs.check_no_internals_visible_to(project)  # build output only: passes
    for folder in ("Bindings", "objectives"):
        (tmp_path / f"src/Core/{folder}").mkdir()
        (tmp_path / f"src/Core/{folder}/Friends.cs").write_text('[assembly: InternalsVisibleTo("T")]', encoding="utf-8")
        with pytest.raises(SystemExit, match=f"src/Core/{folder}/Friends.cs"):
            export_refs.check_no_internals_visible_to(project)
        (tmp_path / f"src/Core/{folder}/Friends.cs").unlink()
    # Copilot on HT PR 16: Windows file names keep their case (Steps.CS)
    (tmp_path / "src/Core/Friends.CS").write_text('[assembly: InternalsVisibleTo("T")]', encoding="utf-8")
    with pytest.raises(SystemExit, match="src/Core/Friends.CS"):
        export_refs.check_no_internals_visible_to(project)


def test_export_refs_needs_config(project):
    (project / ".workflow/config.json").unlink()
    failed(run_script(project, "export_refs.py"), 1, "config.json not found")


def test_installed_layout_has_every_script(project):
    names = sorted(p.name for p in (project / EXTENSION / "scripts").glob("*.py"))
    assert names == ["ac_feature.py", "ac_lock.py", "aclib.py", "changed_files.py", "check_acceptance.py",
                     "check_features.py", "clear_generated.py", "export_refs.py", "extract_feedback.py",
                     "init_config.py", "init_detect.py", "init_scaffold.py", "init_verify.py", "new_analyze.py",
                     "new_run.py", "record_skips.py", "smoke_test.py", "summarize_trx.py", "task_message.py"]
    templates = sorted(p.relative_to(project / EXTENSION / "templates").as_posix()
                       for p in (project / EXTENSION / "templates").rglob("*") if p.is_file())
    assert templates == ["ac-project/AcceptanceTests.csproj.template", "ac-project/Directory.Build.props.template",
                         "ac-project/reqnroll.json", "acceptance-template.md"]
    assert CONFIG["acProjectDir"] == AC


# ---- task_message.py ---------------------------------------------------------------------------------------------

R1 = f"{S1}/ac/runs"
BUILD_LINE = f"Allowed build command: {CONFIG['acRefBuildCommand']}"
EXPECTED_MESSAGES = {
    "ac-feature-translator": [
        f"Feature: {S1} (tag F001)", "Run: translate-001", f"Spec: {S1}/spec.md",
        "Constitution: .specify/memory/constitution.md", "Other spec inputs: docs/domain",
        f"Acceptance criteria: {S1}/acceptance.md", f"Golden samples: {AC}/Samples/F001/",
        f"Write feature files to: {AC}/Features/F001/", BUILD_LINE,
        f"Write your report to: {R1}/translate-001/translation-report.md"],
    "ac-test-writer": [
        f"Feature: {S1} (tag F001)", "Run: run-001", f"Spec: {S1}/spec.md",
        "Constitution: .specify/memory/constitution.md", "Other spec inputs: docs/domain",
        f"Acceptance criteria (context only): {S1}/acceptance.md", f"AC test project: {AC}/",
        f"Project file: {AC}/App.AcceptanceTests.csproj", "Test framework: xunit3",
        f"Feature files: {AC}/Features/F001/", f"Golden samples: {AC}/Samples/F001/",
        f"Write step definitions to: {AC}/StepDefinitions/F001/", f"Feature support: {AC}/Support/F001/",
        f"Shared support: {AC}/Support/Shared/", "Public API listings: artifacts/refs/api/", BUILD_LINE,
        f"Feedback to address: {R1}/run-001/input-feedback.md",
        f"Write your report to: {R1}/run-001/writer-report.md"],
    "ac-test-fail-judge": [
        f"Current feature: {S1} (tag F001)", "Run: run-001", "Analyze: analyze-1",
        f"Feature folders: {S1} (F001), {S2} (F002)", "Constitution: .specify/memory/constitution.md",
        "Other spec inputs: docs/domain", f"AC test project: {AC}/", "Public API listings: artifacts/refs/api/",
        f"Writer report: {R1}/run-001/writer-report.md", f"Test results: {R1}/run-001/analyze-1/ac-results.md",
        f"Write your report to: {R1}/run-001/analyze-1/judge-report.md"],
}


def start(project, role, feedback=False):
    """The run scripts a command runs before task_message.py."""
    if role == "ac-feature-translator":
        ok(run_script(project, "new_run.py", "translate", "--feature", "F001"))
        return
    ok(run_script(project, "new_run.py", "write", "--feature", "F001"))
    if feedback:
        write(project / R1 / "run-001/input-feedback.md")
    if role == "ac-test-fail-judge":
        end_run(project)  # the writer's run ended at its check
        ok(run_script(project, "new_analyze.py", "--feature", "F001"))


def marker_json(project):
    return json.loads((project / ".workflow/active-run.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("role", list(EXPECTED_MESSAGES))
def test_task_message(project, role):
    start(project, role, feedback=True)
    out = ok(run_script(project, "task_message.py", "--feature", "F001"))
    assert out.rstrip("\n").split("\n") == EXPECTED_MESSAGES[role]
    marker = marker_json(project)
    assert marker["taskMessage"] == "\n".join(EXPECTED_MESSAGES[role])
    assert marker["role"] == role and marker["feature"] == S1  # the rest of the marker is kept


@pytest.mark.parametrize("role", ["ac-feature-translator", "ac-test-writer"])
def test_task_message_drops_optional_lines(tmp_path, role):
    project = make_project(tmp_path / "proj", config={**CONFIG, "specInputs": []}).resolve()
    start(project, role)  # no input-feedback.md
    lines = ok(run_script(project, "task_message.py", "--feature", "F001")).rstrip("\n").split("\n")
    expected = [line for line in EXPECTED_MESSAGES[role]
                if not line.startswith(("Other spec inputs:", "Feedback to address:"))]
    assert lines == expected


def test_task_message_feature_list_is_lazy(project):
    """A stray folder under specs/ fails only the judge's message (the only one with <FEATURE_LIST>)."""
    write(project / "specs/notes/readme.md")
    start(project, "ac-test-writer")
    ok(run_script(project, "task_message.py", "--feature", "F001"))
    end_run(project)
    ok(run_script(project, "new_analyze.py", "--feature", "F001"))
    failed(run_script(project, "task_message.py", "--feature", "F001"), 1, "specs/notes")


def test_task_message_errors(project):
    failed(run_script(project, "task_message.py"), 1, "No active run")
    start(project, "ac-test-writer")
    failed(run_script(project, "task_message.py", "--feature", "F002"), 1, f"the active run is for {S1}")
    agent = project / EXTENSION / "agents/ac-test-writer.md"
    text = agent.read_text(encoding="utf-8")
    agent.write_text(text.replace("Test framework: <TEST_FRAMEWORK>", "Test framework: <TEST_RUNNER>"),
                     encoding="utf-8", newline="\n")
    failed(run_script(project, "task_message.py"), 1, "unknown placeholder <TEST_RUNNER>")
    agent.write_text(text.replace("## Your task message", "## Task"), encoding="utf-8", newline="\n")
    failed(run_script(project, "task_message.py"), 1, "no `## Your task message` section")
    agent.unlink()
    failed(run_script(project, "task_message.py"), 1, "agent file .specify/extensions/ac/agents/ac-test-writer.md")
    assert "taskMessage" not in marker_json(project)


# ---- check_acceptance.py ---------------------------------------------------------------------------------------

SPEC = """# Feature Specification: Alpha

<!-- a template comment with **FR-999**: not a requirement -->

## User Scenarios & Testing

### User Story 1 - Convert (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a, **When** b, **Then** c
2. **Given** a, **When** d, **Then** e
3. **Given** a, **When** f, **Then** g

### Edge Cases

1. not a scenario

## Requirements

- **FR-001**: System MUST convert.
- **FR-002**: System MUST reject.
"""

ACCEPTANCE = """# Acceptance criteria: Alpha

## Coverage

| Requirement / scenario | AC items | Note |
|---|---|---|
| US1-AS3 | — | Not testable through the API: only visible in the CLI |

## Acceptance criteria

### AC-001 (FR-001; US1-AS1) Converts

- Given the amount 10.50 EUR
- When it is converted to USD
- Then the result is 11.34 USD

### AC-002 (FR-002, US1-AS2) Rejects

- **Given** the amount -1 EUR
- **When** it is converted to USD
- **Then** the error is "negative amount"
- Golden sample: `rates.json`
"""


@pytest.fixture
def acceptance(project):
    write(project / S1 / "spec.md", SPEC)
    write(project / S1 / "acceptance.md", ACCEPTANCE)
    write(project / AC / "Samples/F001/rates.json", "{}\n")
    return project


def check_acceptance(project):
    return run_script(project, "check_acceptance.py", "--feature", "F001")


def test_check_acceptance_passes(acceptance):
    out = ok(check_acceptance(acceptance))
    assert "OK: 2 item(s); 2 FR and 2 scenario(s) covered, 1 not testable" in out


@pytest.mark.parametrize("change, finding", [
    (("### AC-002 (FR-002, US1-AS2) Rejects", "### AC2 Rejects"), "line 17: item heading is not"),
    (("### AC-002 (FR-002, US1-AS2)", "### AC-001 (FR-002, US1-AS2)"), "AC-001: duplicate id"),
    (("### AC-002 (FR-002, US1-AS2)", "### AC-002 ()"), "AC-002: no references"),
    (("FR-002, US1-AS2", "FR-002, US1-AS9"), "AC-002: reference US1-AS9 is not in spec.md"),
    (("FR-002, US1-AS2", "FR-002, US1-AS2, FR-999"), "AC-002: reference FR-999 is not in spec.md"),
    (("- When it is converted to USD\n", ""), "AC-001: no `When` line"),
    (("- **Then** the error", "- **And** the error"), "AC-002: no `Then` line"),
    (("FR-002, US1-AS2", "US1-AS2"), "FR-002: not covered by any AC item"),
    (("FR-001; US1-AS1", "FR-001"), "US1-AS1: not covered by any AC item and not listed as not testable"),
    (("Not testable through the API: only visible in the CLI", "Not testable through the API:"),
     "US1-AS3: not covered"),
    (("`rates.json`", "`missing.json`"), "AC-002: golden sample missing.json not found"),
    (("`rates.json`", "`../secret.json`"), "AC-002: golden sample ../secret.json must be a file name"),
    (("## Acceptance criteria", "## Criteria"), "no `## Acceptance criteria` section"),
])
def test_check_acceptance_findings(acceptance, change, finding):
    write(acceptance / S1 / "acceptance.md", ACCEPTANCE.replace(*change))
    result = check_acceptance(acceptance)
    failed(result, 1, "problem(s) in specs/001-alpha/acceptance.md")
    assert finding in result.stdout


def test_check_acceptance_fr_cannot_be_marked_not_testable(acceptance):
    text = ACCEPTANCE.replace("FR-002, US1-AS2", "US1-AS2").replace(
        "| US1-AS3 |", "| FR-002 | — | Not testable through the API: internal |\n| US1-AS3 |")
    write(acceptance / S1 / "acceptance.md", text)
    result = check_acceptance(acceptance)
    failed(result, 1)
    assert "FR-002: not covered by any AC item" in result.stdout


def test_check_acceptance_missing_files(acceptance):
    (acceptance / S1 / "acceptance.md").unlink()
    failed(check_acceptance(acceptance), 1, f"{S1}/acceptance.md not found")


def test_acceptance_template_passes_against_a_matching_spec(acceptance):
    """The shipped template is structurally valid (placeholders aside), so the drafting phase starts from a file
    the check understands."""
    template = (PAYLOAD / "templates/acceptance-template.md").read_text(encoding="utf-8")
    write(acceptance / S1 / "acceptance.md", template)
    out = ok(check_acceptance(acceptance))
    assert "OK: 2 item(s); 2 FR and 2 scenario(s) covered, 1 not testable" in out
    assert "Not testable through the API" in template and "cannot be marked" in template


# ---- summarize_trx.py --only-current ------------------------------------------------------------------------------

def test_summarize_trx_only_current(trx_project):
    p = trx_project
    out = ok(run_script(p, "summarize_trx.py", "ac-results.trx", "ac-results.md", "--current", "F002",
                        "--only-current"))
    assert "current F002: passed 0, failed 1, pending 1, skipped 0; regression: passed 2, failed 1" in out
    md = (p / "ac-results.md").read_text(encoding="utf-8")
    current, regression = md.split("## Regression (other features)")
    assert "Only in beta" in current
    assert "Login fails" not in regression and "Expected 1 but was 2" not in regression
    assert "Not part of this analysis (--current): 3 result(s) of other features" in regression
    assert "not passed: F001/AC-002." in regression
    failed(run_script(p, "summarize_trx.py", "ac-results.trx", "x.md", "--only-current"), 1, "needs --current")
