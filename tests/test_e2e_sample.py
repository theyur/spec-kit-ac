"""The step 7 sample discriminates, before any model is involved (S07-R08). Opt-in.

make_sample.py builds the sample in tmp_path (real specify init, `uv run speckit-ac install` from this checkout),
init's scripts set it up as /speckit-ac-init would, and hand-written reference acceptance tests
(tests/e2e/reference/, never copied into the live sample) run against each implementation fixture:
001-buggy fails only at 100.00, 001-fixed passes, 002 fails feature 001 between 100.00 and 149.99. check_stage.py
then gives the expected verdicts on fabricated judge reports. Needs Windows, dotnet, specify, uv, git and NuGet;
takes a few minutes. Run with SPECKIT_AC_DOTNET_E2E=1.
"""
import os
import platform
import shlex
import shutil
import sys
from pathlib import Path

import pytest

E2E = Path(__file__).resolve().parent / "e2e"
sys.path.insert(0, str(E2E))
import check_stage  # noqa: E402
import e2elib  # noqa: E402
import stage  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("SPECKIT_AC_DOTNET_E2E") != "1" or platform.system() != "Windows"
    or any(shutil.which(tool) is None for tool in ("dotnet", "specify", "uv", "git")),
    reason="opt-in: SPECKIT_AC_DOTNET_E2E=1 on Windows with dotnet, specify, uv and git")

REFERENCE = E2E / "reference"


def ok(args, cwd, what):
    code, out = e2elib.run(args, cwd)
    assert code == 0, f"{what} failed (exit {code}):\n{out[-4000:]}"
    return out


def script(project, name, *args):
    return ok([sys.executable, "-I", str(project / e2elib.EXTENSION / "scripts" / name), *args], project, name)


def copy_reference(project, number, cfg):
    tag, folder = f"F{number}", project / "specs" / e2elib.SPECS[number]
    shutil.copyfile(REFERENCE / number / "acceptance.md", folder / "acceptance.md")
    for kind in ("Features", "StepDefinitions"):
        shutil.copytree(REFERENCE / number / kind / tag, project / cfg["acProjectDir"] / kind / tag, dirs_exist_ok=True)
    e2elib.commit(project, f"e2e test: reference {number}")


def implement_and_run(project, cfg, fixture, number, analyze):
    """Implement a fixture, check the solution and unit tests, run every AC test; return {key: outcome}."""
    stage.apply(project, "implement", fixture)
    ok(["dotnet", "build", cfg["solution"], "-nologo", "-v", "q"], project, f"solution build ({fixture})")
    for unit in cfg["unitTestProjects"]:
        ok(shlex.split(cfg["unitTestCommand"].replace("{project}", unit)), project, f"unit tests ({fixture})")
    analyze_dir = f"specs/{e2elib.SPECS[number]}/ac/runs/run-001/{analyze}"
    (project / analyze_dir).mkdir(parents=True)
    ok(["dotnet", "build", cfg["acProject"], "-nologo", "-v", "q"], project, "AC build")  # acTestCommand: --no-build
    command = cfg["acTestCommand"].replace("{acProject}", cfg["acProject"]).replace("{analyzeDir}", analyze_dir)
    e2elib.run(shlex.split(command), project)  # failing tests exit non-zero
    assert (project / analyze_dir / "ac-results.trx").is_file()
    script(project, "summarize_trx.py", f"{analyze_dir}/ac-results.trx", f"{analyze_dir}/ac-results.md",
           "--current", f"F{number}")
    rows = check_stage.results_rows((project / analyze_dir / "ac-results.md").read_text(encoding="utf-8"))
    return project / analyze_dir, {r["key"]: r["outcome"] for r in rows}


def judge(analyze, rows):
    lines = ["# Judge report", "## Summary", "| Feature/AC | Scope | Verdict | Confidence | Reason |", "|---|---|---|---|---|"]
    lines += [f"| {key} | {scope} | {verdict} | high | fabricated |" for key, scope, verdict in rows]
    (analyze / "judge-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def check(project, *argv):
    return check_stage.main(["--project", str(project), "--cli", "checkout", *argv])


def test_sample_discriminates(tmp_path):
    project = tmp_path / "speckit-ac-e2e"
    ok([sys.executable, str(E2E / "make_sample.py"), "--dest", str(project), "--cli", "checkout"], e2elib.REPO,
       "make_sample.py")
    assert e2elib.dirty(project) == []

    # /speckit-ac-init, as its scripts run it (A2, A3)
    import json
    detected = json.loads(script(project, "init_detect.py"))
    proposal = detected["proposal"]
    assert proposal["acSurfaceProjects"] == ["src/Shop.Pricing/Shop.Pricing.csproj"]
    assert proposal["unitTestProjects"] == ["tests/Shop.Pricing.Tests/Shop.Pricing.Tests.csproj"]
    assert proposal["testFramework"] == "xunit3" and detected["runner"] == "vstest" and detected["blockers"] == []
    script(project, "init_config.py", "--solution", detected["solution"], "--surface", proposal["acSurfaceProjects"][0],
           "--unit-tests", proposal["unitTestProjects"][0], "--ac-project-dir", proposal["acProjectDir"],
           "--framework", "xunit3", "--runner", "vstest")
    script(project, "init_scaffold.py", "--target-framework", proposal["targetFramework"])
    verify = script(project, "init_verify.py")
    assert "FAIL" not in verify, verify
    stage.apply(project, "commit", "init")
    assert check(project, "init") == 0
    cfg = e2elib.load_config(project)

    # Feature 001: the planted bug fails only the 100.00 item.
    stage.apply(project, "spec", "001")
    copy_reference(project, "001", cfg)
    analyze, outcomes = implement_and_run(project, cfg, "001-buggy", "001", "analyze-1")
    assert {k for k, o in outcomes.items() if o != "passed"} == {"F001/AC-001"}, outcomes
    assert len(outcomes) == 5
    judge(analyze, [("F001/AC-001", "current", "IMPLEMENTATION_FAULT")])
    assert check(project, "analyze", "fault-001", "001") == 0
    judge(analyze, [("F001/AC-001", "current", "TEST_FAULT")])
    assert check(project, "analyze", "fault-001", "001") == 1
    stage.apply(project, "commit", "analyze 001 buggy")

    # The fix: everything passes.
    analyze, outcomes = implement_and_run(project, cfg, "001-fixed", "001", "analyze-2")
    assert set(outcomes.values()) == {"passed"} and len(outcomes) == 5, outcomes
    assert check(project, "analyze", "pass", "001") == 0
    stage.apply(project, "commit", "analyze 001 fixed")

    # Feature 002 raises the threshold: feature 001's items in [100.00, 150.00) fail, feature 002 passes.
    stage.apply(project, "spec", "002")
    copy_reference(project, "002", cfg)
    analyze, outcomes = implement_and_run(project, cfg, "002", "002", "analyze-1")
    assert {k for k, o in outcomes.items() if o != "passed"} == {"F001/AC-001", "F001/AC-005"}, outcomes
    assert {k for k in outcomes if k.startswith("F002/")} == {"F002/AC-001", "F002/AC-002", "F002/AC-003"}
    judge(analyze, [("F001/AC-001", "regression", "SUPERSEDED"), ("F001/AC-005", "regression", "SUPERSEDED")])
    assert check(project, "analyze", "superseded-002", "002") == 0
    judge(analyze, [("F001/AC-001", "regression", "SUPERSEDED"), ("F001/AC-005", "regression", "TEST_FAULT")])
    assert check(project, "analyze", "superseded-002", "002") == 1
