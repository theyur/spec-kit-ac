"""The step 7 end-to-end tooling (tests/e2e: stage.py, check_stage.py, make_sample.py), on fabricated trees (S07-R09).

External commands (dotnet, the sample's scripts, speckit-ac doctor) go through a stub runner; git is real.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

E2E = Path(__file__).resolve().parent / "e2e"
sys.path.insert(0, str(E2E))
import check_stage  # noqa: E402
import e2elib  # noqa: E402
import make_sample  # noqa: E402
import stage  # noqa: E402

AC = "tests/Shop.AcceptanceTests"
CONFIG = {
    "schemaVersion": 1, "python": "uv run --no-project python -I", "solution": "Shop.slnx", "specInputs": [],
    "acSurfaceProjects": ["src/Shop.Pricing/Shop.Pricing.csproj"],
    "unitTestProjects": ["tests/Shop.Pricing.Tests/Shop.Pricing.Tests.csproj"],
    "acProjectDir": AC, "acProject": f"{AC}/Shop.AcceptanceTests.csproj", "refsDir": "artifacts/refs",
    "acRefBuildCommand": f"dotnet build {AC}/Shop.AcceptanceTests.csproj -p:AcRefMode=true -nologo -v q",
    "unitTestCommand": "dotnet test {project}",
    "acTestCommand": 'dotnet test {acProject} --no-build --results-directory {analyzeDir} '
                     '--logger "trx;LogFileName=ac-results.trx"',
    "testFramework": "xunit3",
}
F001 = "specs/001-order-discount"
F002 = "specs/002-raise-discount-threshold"


def write(path: Path, text: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def git(project, *args):
    return subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "sample"
    write(root / ".specify/memory/constitution.md", "# C\n")
    write(root / ".workflow/config.json", json.dumps(CONFIG, indent=2) + "\n")
    write(root / ".gitignore", ".workflow/guard.log\n.workflow/active-run.json\n")
    write(root / "src/Shop.Pricing/DiscountCalculator.cs", "// base\n")
    git(root, "init", "-q")
    e2elib.commit(root, "init")
    return root


class Runner:
    """Stub for e2elib.run: records calls; returns the exit code of the first matching (substring, code) rule."""

    def __init__(self, rules=()):
        self.rules, self.calls = list(rules), []

    def __call__(self, args, cwd, timeout=1800):
        line = " ".join(map(str, args))
        self.calls.append(line)
        for text, code in self.rules:
            if text in line:
                return code, f"stub output for {text}"
        return 0, "ok"


def check(project, *argv, runner=None):
    runner = runner or Runner()
    code = check_stage.main(["--project", str(project), "--cli", "checkout", *argv], runner=runner)
    return code


# ------------------------------------------------------------------------------------------------------------ stage


def test_stage_spec_writes_spec_and_feature_json_and_commits(project):
    written = stage.apply(project, "spec", "001")
    assert written == [f"{F001}/spec.md", ".specify/feature.json"]
    assert (project / F001 / "spec.md").read_bytes() == (E2E / "specs/001-order-discount/spec.md").read_bytes()
    assert json.loads((project / ".specify/feature.json").read_text(encoding="utf-8")) == {
        "feature_directory": F001}
    assert e2elib.dirty(project) == []
    assert "e2e: spec 001" in git(project, "log", "-1", "--format=%s")


@pytest.mark.parametrize("fixture,operator,threshold", [("001-buggy", ">", "100m"), ("001-fixed", ">=", "100m"),
                                                         ("002", ">=", "150m")])
def test_stage_implement_copies_fixture(project, fixture, operator, threshold):
    written = stage.apply(project, "implement", fixture)
    assert written == ["src/Shop.Pricing/DiscountCalculator.cs", "tests/Shop.Pricing.Tests/DiscountCalculatorTests.cs"]
    code = (project / "src/Shop.Pricing/DiscountCalculator.cs").read_text(encoding="utf-8")
    assert f"subtotal {operator} Threshold" in code and f"Threshold = {threshold}" in code
    assert f"e2e: implement {fixture}" in git(project, "log", "-1", "--format=%s")


def test_stage_fix_is_the_fixed_fixture(project):
    stage.apply(project, "implement", "001-buggy")
    stage.apply(project, "fix", "001")
    assert "subtotal >= Threshold" in (project / "src/Shop.Pricing/DiscountCalculator.cs").read_text(encoding="utf-8")
    assert "e2e: fix 001 (fallback)" in git(project, "log", "-1", "--format=%s")


def test_stage_refuses_a_dirty_tree(project):
    write(project / "notes.md")
    with pytest.raises(e2elib.E2EError, match="uncommitted changes"):
        stage.apply(project, "spec", "001")
    assert not (project / F001).exists()


def test_stage_commit_commits_leftovers_and_tolerates_a_clean_tree(project, capsys):
    write(project / F001 / "acceptance.md")
    stage.apply(project, "commit", "translate 001")
    assert e2elib.dirty(project) == [] and "e2e: after translate 001" in git(project, "log", "-1", "--format=%s")
    stage.apply(project, "commit", "again")
    assert "Nothing to commit." in capsys.readouterr().out


def test_stage_refuses_a_folder_that_is_not_a_sample(tmp_path):
    with pytest.raises(e2elib.E2EError, match="not an e2e sample"):
        stage.apply(tmp_path, "spec", "001")


@pytest.mark.parametrize("argv", [["implement", "003"], ["spec", "003"], ["fix", "002"], ["bogus", "x"]])
def test_stage_usage_errors(project, argv):
    with pytest.raises(SystemExit) as exit_info:
        stage.main(["--project", str(project), *argv])
    assert exit_info.value.code == 2


def test_fixtures_and_specs_exist_for_every_name():
    for name in e2elib.FIXTURE_NAMES:
        assert (e2elib.FIXTURES / name / "src/Shop.Pricing/DiscountCalculator.cs").is_file()
        tests = (e2elib.FIXTURES / name / "tests/Shop.Pricing.Tests/DiscountCalculatorTests.cs").read_text("utf-8")
        assert "50.00m" in tests and "200.00m" in tests and "Negative" not in tests  # R01: 50.00 and 200.00 only
    for name in e2elib.SPECS.values():
        assert (e2elib.SPEC_SOURCES / name / "spec.md").is_file()


# ------------------------------------------------------------------------------------------------------ make_sample


def test_destination_rules(tmp_path):
    assert make_sample.check_destination(tmp_path / "new", False) == "create"
    (tmp_path / "empty").mkdir()
    assert make_sample.check_destination(tmp_path / "empty", False) == "empty"
    write(tmp_path / "full/readme.txt")
    with pytest.raises(e2elib.E2EError, match="not empty"):
        make_sample.check_destination(tmp_path / "full", False)
    with pytest.raises(e2elib.E2EError, match="not a previous sample"):
        make_sample.check_destination(tmp_path / "full", True)
    write(tmp_path / "old/.specify/init-options.json")
    assert make_sample.check_destination(tmp_path / "old", True) == "replace"
    with pytest.raises(e2elib.E2EError, match="inside the spec-kit-ac checkout"):
        make_sample.check_destination(e2elib.REPO / "sample-here", False)
    with pytest.raises(e2elib.E2EError, match="contains the spec-kit-ac checkout"):
        make_sample.check_destination(e2elib.REPO.parent, True)
    with pytest.raises(e2elib.E2EError, match="drive root"):
        make_sample.check_destination(Path(tmp_path.anchor), True)


def test_remove_tree_handles_read_only_files(tmp_path):
    victim = write(tmp_path / "old/.git/objects/pack/p.pack")
    victim.chmod(0o444)
    make_sample.remove_tree(tmp_path / "old")
    assert not (tmp_path / "old").exists()


def test_payload_comparison_skips_extensionignore_and_its_patterns(tmp_path):
    payload, installed = tmp_path / "payload", tmp_path / "installed"
    write(payload / ".extensionignore", "# compiled\n__pycache__/\n*.pyc\n")
    write(payload / "scripts/a.py", "print(1)\n")
    write(payload / "scripts/__pycache__/a.cpython-314.pyc", "bytecode")
    write(payload / "scripts/b.pyc", "bytecode")
    write(installed / "scripts/a.py", "print(1)\r\n")  # CRLF folded
    assert make_sample.payload_mismatch(payload, installed) is None
    write(installed / "scripts/a.py", "print(2)\n")
    assert "scripts/a.py differs" in make_sample.payload_mismatch(payload, installed)
    (installed / "scripts/a.py").unlink()
    assert "scripts/a.py is missing" in make_sample.payload_mismatch(payload, installed)


def test_the_real_payload_matches_a_copy_without_ignored_files(tmp_path):
    import shutil
    shutil.copytree(e2elib.PAYLOAD, tmp_path / "ac", ignore=shutil.ignore_patterns("__pycache__", "*.pyc",
                                                                                   ".extensionignore"))
    assert make_sample.payload_mismatch(e2elib.PAYLOAD, tmp_path / "ac") is None


def test_sample_never_contains_reference_files():
    sample = {p.relative_to(e2elib.SAMPLE).as_posix() for p in e2elib.SAMPLE.rglob("*") if p.is_file()}
    assert not any("StepDefinitions" in p or p.endswith(".feature") or p.endswith("acceptance.md") for p in sample)
    assert ".claude/settings.local.json" in (e2elib.SAMPLE / ".gitignore").read_text(encoding="utf-8")


# ----------------------------------------------------------------------------------------------------- check: init


def test_init_passes(project):
    runner = Runner()
    assert check(project, "init", runner=runner) == 0
    assert any(c.startswith(f"dotnet build {AC}/Shop.AcceptanceTests.csproj") for c in runner.calls)
    assert any(c.endswith("speckit-ac doctor") for c in runner.calls)


@pytest.mark.parametrize("rule", [("dotnet build", 1), ("doctor", 1)])
def test_init_fails_on_build_or_doctor(project, rule):
    assert check(project, "init", runner=Runner([rule])) == 1


def test_init_fails_on_mtp_config(project):
    cfg = dict(CONFIG, acTestCommand="dotnet test --project {acProject} --no-build --report-trx")
    write(project / ".workflow/config.json", json.dumps(cfg))
    assert check(project, "init") == 1


def test_init_without_config_is_an_error(project):
    (project / ".workflow/config.json").unlink()
    with pytest.raises(e2elib.E2EError, match="config.json"):
        check(project, "init")


# ---------------------------------------------------------------------------------------------------- check: smoke

SMOKE_LOG = "".join(f"{role}\tRead\tdeny\n{role}\tSubagentHandback\tallow\n" for role in check_stage.ROLES)


def test_smoke_passes_and_warns_without_explore(project, capsys):
    write(project / ".workflow/guard.log", SMOKE_LOG)
    assert check(project, "smoke") == 0
    assert "WARN no `Explore Read deny` line" in capsys.readouterr().out
    write(project / ".workflow/guard.log", SMOKE_LOG + "Explore\tRead\tdeny\n")
    assert check(project, "smoke") == 0
    assert "PASS an Explore subagent's Read was denied" in capsys.readouterr().out


@pytest.mark.parametrize("role", check_stage.ROLES)
def test_smoke_fails_without_a_handback(project, role):
    write(project / ".workflow/guard.log", SMOKE_LOG.replace(f"{role}\tSubagentHandback\tallow\n",
                                                             f"{role}\tSubagentHandback\tdeny\n"))
    assert check(project, "smoke") == 1


@pytest.mark.parametrize("leftover", [".workflow/active-run.json", "specs/999-speckit-ac-smoke/spec.md",
                                      f"{AC}/StepDefinitions/smoke-test.txt"])
def test_smoke_fails_on_leftovers(project, leftover):
    write(project / ".workflow/guard.log", SMOKE_LOG)
    write(project / leftover)
    assert check(project, "smoke") == 1


def test_smoke_fails_without_a_log(project):
    assert check(project, "smoke") == 1


# ----------------------------------------------------------------------------------------- check: ac and features

BOUNDARY_ITEMS = """# Acceptance criteria

## Acceptance criteria

### AC-001 (FR-001; US1-AS1) Exactly 100.00

- Given an order with the subtotal 100.00
- When the total is calculated
- Then the total is 90.00

### AC-002 (FR-002; US1-AS2) Below

- Given an order with the subtotal 99.99
- Then the total is 99.99
"""


def test_ac_runs_both_scripts_and_finds_the_boundary_item(project, capsys):
    write(project / F001 / "acceptance.md", BOUNDARY_ITEMS)
    runner = Runner()
    assert check(project, "ac", "001", runner=runner) == 0
    assert any("check_acceptance.py --feature 001" in c for c in runner.calls)
    assert any("ac_lock.py verify sources --feature 001" in c for c in runner.calls)
    assert "PASS an item checks the boundary 100.00 -> 90.00: AC-001" in capsys.readouterr().out


def test_ac_warns_without_the_boundary_item(project, capsys):
    write(project / F001 / "acceptance.md", BOUNDARY_ITEMS.replace("100.00", "100.50"))
    assert check(project, "ac", "001") == 0
    assert "WARN no item checks the boundary" in capsys.readouterr().out


@pytest.mark.parametrize("rule", [("check_acceptance.py", 1), ("ac_lock.py verify sources", 1)])
def test_ac_fails_when_a_script_fails(project, rule):
    write(project / F001 / "acceptance.md", BOUNDARY_ITEMS)
    assert check(project, "ac", "001", runner=Runner([rule])) == 1


def test_ac_needs_the_feature_folder(project):
    with pytest.raises(e2elib.E2EError, match="stage.py spec 001"):
        check(project, "ac", "001")


def test_features_checks_tags(project):
    write(project / F002 / "spec.md")
    write(project / AC / "Features/F002/A.feature", "@F002\nFeature: A\n")
    assert check(project, "features", "002") == 0
    write(project / AC / "Features/F002/B.feature", "@F001\nFeature: B\n")
    assert check(project, "features", "002") == 1


def test_features_fails_without_files_or_on_a_script(project):
    write(project / F002 / "spec.md")
    assert check(project, "features", "002") == 1
    write(project / AC / "Features/F002/A.feature", "@F002\nFeature: A\n")
    assert check(project, "features", "002", runner=Runner([("ac_lock.py verify features", 1)])) == 1


# -------------------------------------------------------------------------------------------------- check: written

STEPS = '[Binding, Scope(Tag = "F001")]\npublic class S {}\n'


def written_project(project, steps=STEPS):
    write(project / F001 / "spec.md")
    e2elib.commit(project, "translate")
    write(project / F001 / "ac/runs/run-001/writer-report.md")
    write(project / F001 / "ac/runs/run-001/input-feedback.md")
    if steps is not None:
        write(project / AC / "StepDefinitions/F001/Steps.cs", steps)
    write(project / AC / "Support/Shared/Money.cs", "// helper\n")
    return project


def test_written_passes(project):
    assert check(written_project(project), "written", "001") == 0


@pytest.mark.parametrize("steps", [None, "[Binding]\npublic class S {}\n", '[Binding, Scope(Tag = "F002")]\n'])
def test_written_fails_on_missing_or_unscoped_steps(project, steps):
    assert check(written_project(project, steps), "written", "001") == 1


@pytest.mark.parametrize("outside", ["src/Shop.Pricing/DiscountCalculator.cs", f"{AC}/StepDefinitions/F001/X.feature",
                                     f"{F001}/acceptance.md", f"{F001}/ac/runs/run-001/notes.md"])
def test_written_fails_on_files_outside_the_allowlist(project, outside):
    written_project(project)
    write(project / outside, "changed\n")
    assert check(project, "written", "001") == 1


def test_written_scope_accepts_at_sign_and_spacing():
    assert check_stage.SCOPE.findall('[Scope( Tag="@F001" )]') == ["F001"]


# -------------------------------------------------------------------------------------------------- check: analyze

def results_md(rows, only_current=False):
    """rows: (feature, scenario, ac, outcome); a trace with a Gherkin table that must not be read as a result."""
    head = "| Feature | Scenario | Tags | Outcome | Duration |\n|---|---|---|---|---|\n"
    body = "".join(f"| {f} | {s} | @{f} {'@' + a if a else ''} | {o} | 00:00:00.01 |\n" for f, s, a, o in rows)
    trace = "\n### F001/AC-001 x — failed\n\nStep trace:\n```\n| F001 | fake | @AC-009 | failed | x |\n```\n"
    text = "# AC results\n\n## Current feature (F001)\n\nTotal: 1\n\n" + head + body + trace
    text += "\n## Regression (other features)\n\n"
    text += "Not part of this analysis (--current): 0 result(s)\n" if only_current else head
    return text


def judge_md(rows):
    lines = ["# Judge report", "## Summary", "| Feature/AC | Scope (current / regression) | Verdict | Confidence | Reason |",
             "|---|---|---|---|---|"]
    lines += [f"| {key} | {scope} | {verdict} | high | because |" for key, scope, verdict in rows]
    lines += ["## Details (for the user)", "| F001/AC-005 | x | TEST_FAULT | low | not in the summary |"]
    return "\n".join(lines) + "\n"


def analyze_project(project, number, results, judge=None, items=BOUNDARY_ITEMS):
    folder = project / (F001 if number == "001" else F002)
    write(folder / "spec.md")
    write(folder / "acceptance.md", items)
    write(folder / "ac/runs/run-001/analyze-1/ac-results.md", "stale\n")
    analyze = folder / "ac/runs/run-001/analyze-2"
    write(analyze / "ac-results.md", results)
    if judge is not None:
        write(analyze / "judge-report.md", judge)
    return project


FAULT_RESULTS = [("F001", "Exactly 100.00", "AC-001", "failed"), ("F001", "Below", "AC-002", "passed")]


def test_analyze_fault_passes(project, capsys):
    analyze_project(project, "001", results_md(FAULT_RESULTS), judge_md([("F001/AC-001", "current",
                                                                          "IMPLEMENTATION_FAULT")]))
    assert check(project, "analyze", "fault-001", "001") == 0
    out = capsys.readouterr().out
    assert "F001/AC-001" in out and "IMPLEMENTATION_FAULT" in out and "analyze-2" in out


@pytest.mark.parametrize("cell", ["F001 / AC-001", "`F001/AC-001` boundary", "F001 @AC-001"])
def test_analyze_reads_judge_keys_tolerantly(project, cell):
    analyze_project(project, "001", results_md(FAULT_RESULTS), judge_md([(cell, "current", "**IMPLEMENTATION_FAULT**")]))
    assert check(project, "analyze", "fault-001", "001") == 0


@pytest.mark.parametrize("judge", [
    judge_md([("F001/AC-001", "current", "TEST_FAULT")]),                      # wrong verdict
    judge_md([("AC-001 only", "current", "IMPLEMENTATION_FAULT")]),           # no feature id
    judge_md([]),                                                              # no verdict for the failure
    None,                                                                      # no judge report
])
def test_analyze_fault_fails(project, judge):
    analyze_project(project, "001", results_md(FAULT_RESULTS), judge)
    assert check(project, "analyze", "fault-001", "001") == 1


def test_analyze_fault_fails_for_a_non_boundary_failure(project):
    rows = [("F001", "Exactly 100.00", "AC-001", "passed"), ("F001", "Below", "AC-002", "failed")]
    analyze_project(project, "001", results_md(rows), judge_md([("F001/AC-002", "current", "IMPLEMENTATION_FAULT")]))
    assert check(project, "analyze", "fault-001", "001") == 1


def test_analyze_fault_fails_when_nothing_failed(project):
    rows = [("F001", "Exactly 100.00", "AC-001", "passed")]
    analyze_project(project, "001", results_md(rows), judge_md([]))
    assert check(project, "analyze", "fault-001", "001") == 1


def test_analyze_pass(project):
    rows = [("F001", "Exactly 100.00", "AC-001", "passed"), ("F001", "Below", "AC-002", "passed")]
    analyze_project(project, "001", results_md(rows))
    assert check(project, "analyze", "pass", "001") == 0


@pytest.mark.parametrize("outcome", ["failed", "pending", "skipped"])
def test_analyze_pass_fails_on_anything_but_passed(project, outcome):
    rows = [("F001", "Exactly 100.00", "AC-001", "passed"), ("F001", "Below", "AC-002", outcome)]
    analyze_project(project, "001", results_md(rows))
    assert check(project, "analyze", "pass", "001") == 1


def test_analyze_fails_on_a_result_without_an_ac_id(project):
    rows = [("F001", "Exactly 100.00", "AC-001", "failed"), ("F001", "Untagged", "", "failed")]
    analyze_project(project, "001", results_md(rows), judge_md([("F001/AC-001", "current", "IMPLEMENTATION_FAULT")]))
    assert check(project, "analyze", "fault-001", "001") == 1


SUPERSEDED_RESULTS = [("F002", "At 150.00", "AC-001", "passed"), ("F001", "Exactly 100.00", "AC-001", "failed"),
                      ("F001", "Rounding", "AC-005", "failed"), ("F001", "Below", "AC-002", "passed")]


def test_analyze_superseded_passes(project):
    judge = judge_md([("F001/AC-001", "regression", "SUPERSEDED"), ("F001/AC-005", "regression", "SUPERSEDED")])
    analyze_project(project, "002", results_md(SUPERSEDED_RESULTS), judge)
    assert check(project, "analyze", "superseded-002", "002") == 0


def test_analyze_superseded_fails(project):
    judge = judge_md([("F001/AC-001", "regression", "SUPERSEDED"), ("F001/AC-005", "regression", "IMPLEMENTATION_FAULT")])
    analyze_project(project, "002", results_md(SUPERSEDED_RESULTS), judge)
    assert check(project, "analyze", "superseded-002", "002") == 1


def test_analyze_superseded_fails_on_an_f002_failure(project):
    rows = SUPERSEDED_RESULTS + [("F002", "Below 150", "AC-002", "failed")]
    judge = judge_md([("F001/AC-001", "regression", "SUPERSEDED"), ("F001/AC-005", "regression", "SUPERSEDED"),
                      ("F002/AC-002", "current", "IMPLEMENTATION_FAULT")])
    analyze_project(project, "002", results_md(rows), judge)
    assert check(project, "analyze", "superseded-002", "002") == 1


def test_analyze_superseded_fails_with_only_current(project, capsys):
    analyze_project(project, "002", results_md([("F002", "At 150.00", "AC-001", "passed")], only_current=True),
                    judge_md([]))
    assert check(project, "analyze", "superseded-002", "002") == 1
    assert "without --current" in capsys.readouterr().out


def test_analyze_fails_without_an_analyze_folder(project):
    write(project / F001 / "ac/runs/run-001/writer-report.md")
    assert check(project, "analyze", "pass", "001") == 1


@pytest.mark.parametrize("argv", [["analyze", "fault-001", "002"], ["analyze", "bogus", "001"], ["ac", "003"],
                                  ["analyze", "pass"], ["init", "001"]])
def test_check_usage_errors(project, argv):
    with pytest.raises(SystemExit) as exit_info:
        check_stage.main(["--project", str(project), *argv], runner=Runner())
    assert exit_info.value.code == 2


# ----------------------------------------------------------------------------------------------------- parsers

def test_results_parser_ignores_headers_separators_and_fenced_tables():
    rows = check_stage.results_rows(results_md(FAULT_RESULTS))
    assert [(r["key"], r["outcome"]) for r in rows] == [("F001/AC-001", "failed"), ("F001/AC-002", "passed")]


def test_judge_parser_reads_only_the_summary():
    rows = check_stage.judge_rows(judge_md([("F001/AC-001", "current", "SUPERSEDED")]))
    assert [(r["key"], r["verdict"]) for r in rows] == [("F001/AC-001", "SUPERSEDED")]


def test_ac_items_split_on_headings():
    items = check_stage.ac_items(BOUNDARY_ITEMS)
    assert set(items) == {"AC-001", "AC-002"} and "90.00" in items["AC-001"] and "90.00" not in items["AC-002"]


def test_reference_acceptance_has_the_boundary_item():
    items = check_stage.ac_items((E2E / "reference/001/acceptance.md").read_text(encoding="utf-8"))
    assert "100.00" in items["AC-001"] and "90.00" in items["AC-001"]


def test_tool_cli_is_the_uv_tool_not_the_checkout_venv(monkeypatch, tmp_path):
    """Under `uv run` the checkout's .venv/Scripts/speckit-ac is first on PATH; tool mode must not pick it up."""
    bin_dir = tmp_path / "uv-bin"
    write(bin_dir / "speckit-ac.exe", "")
    venv = write(tmp_path / ".venv/Scripts/speckit-ac.exe", "")
    monkeypatch.setattr(e2elib.shutil, "which", lambda name: str(venv))
    monkeypatch.setattr(e2elib, "run", lambda args, cwd, timeout=1800: (0, f"{bin_dir}\n"))
    assert e2elib.cli_command("tool") == [str(bin_dir / "speckit-ac.exe")]
    (bin_dir / "speckit-ac.exe").unlink()
    with pytest.raises(e2elib.E2EError, match="not installed as a uv tool"):
        e2elib.cli_command("tool")


def test_analyze_can_check_an_earlier_analyze_folder(project):
    analyze_project(project, "001", results_md(FAULT_RESULTS), judge_md([("F001/AC-001", "current",
                                                                          "IMPLEMENTATION_FAULT")]))
    passing = [("F001", "Exactly 100.00", "AC-001", "passed"), ("F001", "Below", "AC-002", "passed")]
    write(project / F001 / "ac/runs/run-001/analyze-3/ac-results.md", results_md(passing))
    assert check(project, "analyze", "fault-001", "001") == 1  # latest (analyze-3) passed everything
    assert check(project, "--analyze", "analyze-2", "analyze", "fault-001", "001") == 0
    assert check(project, "--analyze", "analyze-9", "analyze", "fault-001", "001") == 1


def test_judge_key_with_trailing_row_text():
    rows = check_stage.judge_rows(judge_md([("F001/AC-001 (row subtotal 100.00 / total 90.00)", "current",
                                             "IMPLEMENTATION_FAULT")]))
    assert [(r["key"], r["verdict"]) for r in rows] == [("F001/AC-001", "IMPLEMENTATION_FAULT")]


def test_analyze_fails_on_mixed_verdicts_for_one_item(project):
    """Outlines give one judge row per failing example; one wrong verdict among them must not be hidden."""
    rows = [("F002", "At 150.00", "AC-001", "passed"), ("F001", "Rounding 100.01", "AC-003", "failed"),
            ("F001", "Rounding 100.05", "AC-003", "failed")]
    judge = judge_md([("F001/AC-003 (100.01)", "regression", "TEST_FAULT"),
                      ("F001/AC-003 (100.05)", "regression", "SUPERSEDED")])
    analyze_project(project, "002", results_md(rows), judge)
    assert check(project, "analyze", "superseded-002", "002") == 1
