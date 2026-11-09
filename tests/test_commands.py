"""Tests for the extension manifest and the five commands (payload/extension.yml, payload/commands/*.md), step 4.

The commands are instructions for a model, so these tests check what can be checked without one: the manifest, the
command texts (every script and subcommand they name exists, the subagent start sequence and the step order, no path
that spec-kit's rendering would rewrite), a **walk** per subagent command that runs its script steps in a temp
project in the documented order and starts the subagent through the real guard, and — when `specify` is installed
— a real `specify extension add --dev` of the payload.
"""

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from acproject import AC, PAYLOAD, REPO, make_project, run_guard, run_script, write

COMMANDS = PAYLOAD / "commands"
MANIFEST = PAYLOAD / "extension.yml"
T, W, J = "ac-feature-translator", "ac-test-writer", "ac-test-fail-judge"
ALLOW, DENY = 0, 2
S1 = "specs/001-alpha"
NAMES = ["init", "translate", "tests-write", "tests-analyze", "critic"]
ROLE = {"translate": T, "tests-write": W, "tests-analyze": J}
RUN_SCRIPT = {"translate": ("new_run.py", "translate"), "tests-write": ("new_run.py", "write"),
              "tests-analyze": ("new_analyze.py", None)}
# Subcommands each script accepts (its argparse choices / usage); a command may use only these.
SUBCOMMANDS = {"ac_lock.py": {"lock", "verify", "unlock", "confirm-spec"}, "new_run.py": {"translate", "write"},
               "changed_files.py": {"snapshot", "check", "clear"}, "clear_generated.py": {"features", "steps"},
               "smoke_test.py": {"start", "end", "isolation-file"}}
# Step order inside "## Steps" (a subsequence: other mentions may sit in between).
STEP_ORDER = {
    "translate": [("ac_feature.py", None), ("ac_lock.py", "verify"), ("check_acceptance.py", None),
                  ("ac_lock.py", "lock"), ("export_refs.py", None), ("clear_generated.py", "features"),
                  ("check_features.py", None), ("record_skips.py", None), ("ac_lock.py", "lock")],
    "tests-write": [("ac_feature.py", None), ("ac_lock.py", "verify"), ("ac_lock.py", "verify"),
                    ("export_refs.py", None), ("clear_generated.py", "steps")],
    "tests-analyze": [("ac_feature.py", None), ("ac_lock.py", "verify"), ("new_analyze.py", None),
                      ("summarize_trx.py", None), ("extract_feedback.py", None)],
}
# spec-kit 1.0.2 rewrites these when it renders a command into a skill (agents.py:195-270).
REWRITTEN = [re.compile(r"(^|[\s`\"'(])(?:\./)?(agents|hooks|scripts|templates)/", re.MULTILINE),
             re.compile(r"(^|[\s`\"'(])(?:\.?/)?(scripts|templates|memory)/", re.MULTILINE)]
INVOCATION = re.compile(r"`([a-z_]+\.py)([^`]*)`|the `Agent` tool")


def text(name):
    return (COMMANDS / f"speckit.ac.{name}.md").read_text(encoding="utf-8")


def frontmatter_and_body(content):
    lines = content.split("\n")
    assert lines[0] == "---"
    end = lines.index("---", 1)
    meta = dict(line.split(": ", 1) for line in lines[1:end])
    return meta, "\n".join(lines[end + 1:])


def invocations(content):
    """[(script, first argument or None)] in text order; the subagent launch is ("Agent", None)."""
    found = []
    for match in INVOCATION.finditer(content):
        if match[1] is None:
            found.append(("Agent", None))
            continue
        args = match[2].split()
        first = args[0] if args and re.fullmatch(r"[a-z][a-z-]*", args[0]) else None
        found.append((match[1], first))
    return found


def is_subsequence(wanted, items):
    it = iter(items)
    return all(any(w == x for x in it) for w in wanted)


def manifest_commands():
    return re.findall(r"^    - name: (speckit\.ac\.[a-z-]+)\n      file: (commands/\S+)$",
                      MANIFEST.read_text(encoding="utf-8"), re.MULTILINE)


# ---- manifest -----------------------------------------------------------------------------------------------------

def test_manifest_header():
    manifest = MANIFEST.read_text(encoding="utf-8")
    version = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert manifest.startswith('schema_version: "1.0"\n')
    assert re.search(r"^extension:\n  id: ac\n", manifest, re.MULTILINE)
    assert re.search(rf'^  version: "{re.escape(version)}"$', manifest, re.MULTILINE)
    assert re.search(r"^  license: MIT$", manifest, re.MULTILINE)
    assert re.search(r'^requires:\n  speckit_version: ">=1\.0\.2"$', manifest, re.MULTILINE)


def test_manifest_commands_match_the_files():
    commands = manifest_commands()
    assert [name for name, _ in commands] == [f"speckit.ac.{n}" for n in NAMES]
    for name, file in commands:
        assert file == f"commands/{name}.md" and (PAYLOAD / file).is_file()
    assert sorted(p.name for p in COMMANDS.glob("*.md")) == sorted(f"speckit.ac.{n}.md" for n in NAMES)


def test_manifest_hooks():
    hooks = MANIFEST.read_text(encoding="utf-8").split("\nhooks:\n", 1)[1]
    events = re.findall(r"^  (\w+):$", hooks, re.MULTILINE)
    assert events == ["after_clarify", "after_plan", "after_tasks", "after_implement"]
    entries = re.findall(r"^    - command: (\S+)$", hooks, re.MULTILINE)
    assert entries == ["speckit.ac.critic", "speckit.ac.translate", "speckit.ac.critic", "speckit.ac.critic",
                       "speckit.ac.tests-write"]
    assert hooks.count("      optional: true\n") == len(entries)  # offered, never auto-run
    prompts = re.findall(r'^      prompt: "(.*)"$', hooks, re.MULTILINE)
    assert len(prompts) == len(entries) and all(p.startswith("Type /speckit-ac-") for p in prompts)
    clarify = hooks.split("  after_plan:")[0]
    assert re.findall(r"priority: (\d+)", clarify) == ["10", "20"]  # critic offered before translate


# ---- command texts ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", NAMES)
def test_frontmatter(name):
    meta, _ = frontmatter_and_body(text(name))
    assert set(meta) == {"description", "argument-hint"}
    assert "Started only by the user" in meta["description"]


@pytest.mark.parametrize("name", NAMES)
def test_body_survives_spec_kit_rendering(name):
    _, body = frontmatter_and_body(text(name))
    for pattern in REWRITTEN:
        assert not pattern.search(body), f"{name}: spec-kit would rewrite {pattern.search(body)[0]!r}"
    for token in ("{SCRIPT}", "{ARGS}", "__AGENT__"):
        assert token not in body
    assert "$ARGUMENTS" in body


@pytest.mark.parametrize("name", NAMES)
def test_scripts_and_subcommands_exist(name):
    content = text(name)
    scripts = PAYLOAD / "scripts"
    shared = (scripts / "aclib.py").read_text(encoding="utf-8")
    for script, first in invocations(content):
        if script == "Agent":
            continue
        assert (scripts / script).is_file(), f"{name}: no script {script}"
        if script in SUBCOMMANDS and first is not None:
            assert first in SUBCOMMANDS[script], f"{name}: {script} {first}"
    for script, args in re.findall(r"`([a-z_]+\.py)([^`]*)`", content):
        source = (scripts / script).read_text(encoding="utf-8")
        for flag in re.findall(r"--[a-z-]+", args):
            assert f'"{flag}"' in source + shared, f"{name}: {script} has no flag {flag}"
    for path in re.findall(r"\.specify/extensions/ac/(\S+?)[`\s)]", content):
        if not path.startswith("scripts/<"):
            assert (PAYLOAD / path).exists(), f"{name}: {path} is not in the payload"


@pytest.mark.parametrize("name", NAMES)
def test_named_commands_exist(name):
    provided = {n.split(".")[-1] for n, _ in manifest_commands()}
    for command in re.findall(r"/speckit-ac-([a-z-]+)", text(name) + MANIFEST.read_text(encoding="utf-8")):
        assert command in provided, f"/speckit-ac-{command}"


@pytest.mark.parametrize("name", ["translate", "tests-write", "tests-analyze"])
def test_subagent_start_sequence(name):
    content = text(name)
    script, kind = RUN_SCRIPT[name]
    start = [(script, kind), ("task_message.py", None), ("changed_files.py", "snapshot"), ("Agent", None),
             ("changed_files.py", "check")]
    assert is_subsequence(start, invocations(content)), invocations(content)
    assert f"`subagent_type: {ROLE[name]}`, `run_in_background: false`" in content
    assert "the exact output of `task_message.py`" in content and "Add nothing" in content
    assert f"`changed_files.py check {ROLE[name]}`" in content and "isolation breach" in content


@pytest.mark.parametrize("name", ["translate", "tests-write", "tests-analyze"])
def test_step_order(name):
    steps = text(name).split("\n## Steps\n", 1)[1]
    assert is_subsequence(STEP_ORDER[name], invocations(steps)), invocations(steps)


def flat(content):
    """Text with every run of whitespace as one space, so checks don't depend on line wrapping."""
    return " ".join(content.split())


WAIT = "Wait for the subagent's hand-back (its result) before anything else."
BACKGROUND = "If the tool says it runs in the background, make no other tool call until its result arrives"
NEXT_STEP = {"translate": "`changed_files.py check`", "tests-write": "`changed_files.py check`",
             "tests-analyze": "`changed_files.py check`", "init": "`smoke_test.py end`",
             "critic": "read the report (step 2)"}


@pytest.mark.parametrize("name", NAMES)
def test_waits_for_the_hand_back(name):
    """Step 7: the model ran every subagent in the background; the command must wait before the next step."""
    content = flat(text(name))
    launch = content.index("`run_in_background: false`")
    wait = content.index(WAIT, launch)
    background = content.index(BACKGROUND, wait)
    assert content[background + len(BACKGROUND):].startswith(f"; only then {'' if name == 'critic' else 'run '}"
                                                              f"{NEXT_STEP[name]}")


@pytest.mark.parametrize("name", ["translate", "tests-write", "tests-analyze"])
def test_shared_rules(name):
    content = flat(text(name))
    assert "`<python> .specify/extensions/ac/scripts/<name>.py …`" in content
    assert "Never use `$CLAUDE_PROJECT_DIR` in a script path" in content
    assert "run `/speckit-ac-init` first" in content
    for code in ("**0**", "**1**", "**3**"):
        assert code in content
    assert "`ac_lock.py confirm-spec sources <feature-arg>`" in content
    assert "Never start it, or any other command, yourself." in content or "Never start another command" in content
    # Step 8, option B: a run script refuses another active run; only the user ends it
    assert ('It refuses while another AC run is active ("An AC run is still active"): stop and report its message. '
            "Never end that run yourself; the user does, once no AC subagent is running;") in content


def test_translate_rules():
    content = flat(text("translate"))
    assert "**phase 1**" in content and "**phase 2**" in content
    for forbidden in ("`plan.md`", "`research.md`", "`data-model.md`", "`contracts/`", "`tasks.md`", "`CLAUDE.md`"):
        assert forbidden in content
    assert "Only after an explicit approval: `ac_lock.py lock features <feature-arg>`" in content
    assert "`check_acceptance.py <feature-arg>` passes" in content


def test_tests_write_rules():
    content = flat(text("tests-write"))
    assert "`fresh`" in content and "Do not read the files first" in content
    assert "Never run the tests of the whole solution" in content
    assert "cross-feature changes, missing packages" in content


def test_tests_analyze_rules():
    content = flat(text("tests-analyze"))
    assert "`--only-current`" in content and "`ac_feature.py --all`" in content
    assert "**that exists**" in content  # only existing locks of other features are verified
    assert "only the number of errors and their codes" in content
    # Copilot on HT PR 16: every stop between new_analyze.py and the judge ends the run (build, no TRX, all passed)
    steps = content.split(" 9. Start the judge", 1)[0].split(" 5. Run `new_analyze.py", 1)[1]
    assert steps.count("`changed_files.py clear`") == 5  # the rule + the four stops
    for verdict in ("TRANSLATION_FAULT", "IMPLEMENTATION_FAULT", "TEST_FAULT", "SPEC_AMBIGUITY", "UNEXPRESSIBLE",
                    "SUPERSEDED", "INCONCLUSIVE"):
        assert f"`{verdict}`" in content


def test_init_rules():
    raw = text("init")
    content = flat(raw)
    for mode in ("**smoke** mode", "**setup** mode", "**verify** mode"):
        assert mode in content
    assert "`<python>` is `uv run --no-project python -I`" in content  # no config yet
    assert "Never use `$CLAUDE_PROJECT_DIR` in a script path" in content
    assert "The **only** file you edit yourself is the `<NoWarn>` property of the AC project file" in content
    setup = raw.split("\n## Setup\n", 1)[1].split("\n## Verify\n", 1)[0]
    assert is_subsequence([("init_detect.py", None), ("init_config.py", None), ("init_scaffold.py", None),
                           ("init_verify.py", None)], invocations(setup)), invocations(setup)
    flat_setup = flat(setup)
    assert flat_setup.index("Wait for an explicit confirmation") < flat_setup.index("`init_config.py --solution")
    assert flat_setup.index("`supported.supported` is false") < flat_setup.index("Show **one summary**")
    assert "`implementationFolders`" in flat_setup and "Extra spec inputs**: always ask" in flat_setup
    assert "`init_scaffold.py --target-framework <the confirmed target framework>`" in flat_setup
    assert "delete `.workflow/config.json`" in flat_setup  # scaffold failure: back to setup
    assert "`<NoWarn>$(NoWarn);CS1234</NoWarn>`" in flat_setup and "run `init_verify.py` once more" in flat_setup
    smoke = raw.split("\n## Smoke\n", 1)[1].split("\n## Report\n", 1)[0]
    assert is_subsequence([("smoke_test.py", "start"), ("Agent", None), ("smoke_test.py", "end"),
                           ("smoke_test.py", "isolation-file"), ("smoke_test.py", "isolation-file")],
                          invocations(smoke)), invocations(smoke)
    flat_smoke = flat(smoke)
    assert "`run_in_background: false`" in flat_smoke and "the exact output of `smoke_test.py start`" in flat_smoke
    assert "the guard denies the launch" in flat_smoke and "reports that its read was blocked" in flat_smoke
    assert "`.specify/extensions/ac/hooks/guard.py`" in flat_smoke and "`onFailure: block`" in flat_smoke
    report = flat(raw.split("\n## Report\n", 1)[1])
    assert "`/speckit-constitution`" in report and "never edit the constitution yourself" in report
    assert "run `/speckit-ac-init smoke`" in report
    assert "Never start another command" in content


def test_critic_rules():
    raw = text("critic")
    content = flat(raw)
    source = Path.home() / ".claude/skills/speckit-critic/SKILL.md"
    assert "`spec`, `plan` (default), `tasks`, `ac` or `features`" in content
    assert '`model: "fable"`' in content and '`effort: "high"`' in content
    assert content.count("Do NOT read source code, unit tests, plan.md") == 2  # stages ac and features
    assert "## Stage features (report-only)" in content and "Do not revise anything" in content
    assert "if `sourcesLock` exists, stop" in content
    hard_rules = raw.split("HARD RULES\n", 1)[1].split("\n\nWORKING DIRECTORY", 1)[0]
    assert hard_rules.count("\n- ") == 4
    if source.is_file():  # the hard rules are kept word for word
        assert hard_rules in source.read_text(encoding="utf-8")


# ---- walks: each subagent command's script steps in order, the launch through the real guard ------------------

@pytest.fixture
def project(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    root = make_project(tmp_path / "proj").resolve()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def run(project, *args):
    result = run_script(project, *args)
    assert result.returncode == 0, f"{args}: {result.stdout}{result.stderr}"
    return result.stdout


def launch(project, role, prompt):
    payload = {"tool_name": "Agent", "hook_event_name": "PreToolUse", "cwd": str(project),
               "tool_input": {"description": "AC", "prompt": prompt, "subagent_type": role,
                              "run_in_background": False}}
    return run_guard(project, payload)[0]


def subagent_write(project, role, path, content):
    """A subagent's Write: allowed by the guard, then done."""
    payload = {"tool_name": "Write", "hook_event_name": "PreToolUse", "cwd": str(project), "agent_type": role,
               "tool_input": {"file_path": str(project / path), "content": content}}
    assert run_guard(project, payload) == (ALLOW, ""), path
    write(project / path, content)


def start_subagent(project, role, run_args, writes):
    """Rules steps 1-5 of a command: run script, task message, snapshot, launch, stub subagent, check."""
    run(project, *run_args)
    message = run(project, "task_message.py", "--feature", "F001")
    run(project, "changed_files.py", "snapshot")
    assert launch(project, role, message) == ALLOW
    for path, content in writes:
        subagent_write(project, role, path, content)
    out = run(project, "changed_files.py", "check", role)
    assert "OUTSIDE ALLOWLIST" not in out
    assert not (project / ".workflow/active-run.json").exists()
    assert launch(project, role, message) == DENY  # the run is over
    return message


FEATURE = """@F001
Feature: Alpha

  @AC-001 @FR-001
  Scenario: Converts
    Given the amount 10.50 EUR
    When it is converted to USD
    Then the result is 11.34 USD
"""
REPORT = "# Translation report — F001 / translate-001\n\n## Issues\n\n| AC id | Kind |\n|---|---|\n| AC-002 | gap |\n"
TRX = """<?xml version="1.0" encoding="utf-8"?>
<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <Results>
    <UnitTestResult testId="1" testName="Converts" outcome="Failed" duration="00:00:00.01">
      <Output><ErrorInfo><Message>Expected 11.34 but was 11.35</Message></ErrorInfo></Output>
    </UnitTestResult>
  </Results>
  <TestDefinitions>
    <UnitTest id="1"><TestMethod className="App.AcceptanceTests.Features.F001.AlphaFeature" name="Converts" /></UnitTest>
  </TestDefinitions>
</TestRun>
"""
JUDGE = ("# Judge report\n\n<!-- WRITER-FEEDBACK:BEGIN -->\n## Feedback for the test writer\n"
         "AC-001: the expected value must be the literal 11.34 USD.\n<!-- WRITER-FEEDBACK:END -->\n")


def translate(project):
    """/speckit-ac-translate phase 2 (sources locked in phase 1). Skipped: export_refs.py (needs dotnet)."""
    run(project, "ac_lock.py", "lock", "sources", "--feature", "F001")  # end of phase 1
    run(project, "ac_feature.py", "--feature", "F001")
    run(project, "ac_lock.py", "verify", "sources", "--feature", "F001")
    run(project, "clear_generated.py", "features", "--feature", "F001")
    message = start_subagent(project, T, ("new_run.py", "translate", "--feature", "F001"), [
        (f"{AC}/Features/F001/alpha.feature", FEATURE),
        (f"{S1}/ac/runs/translate-001/translation-report.md", REPORT)])
    assert f"Write feature files to: {AC}/Features/F001/" in message
    run(project, "check_features.py", "--feature", "F001")
    run(project, "record_skips.py", "translate-001", "AC-002", "--feature", "F001")
    run(project, "ac_lock.py", "lock", "features", "--feature", "F001")


def write_tests(project):
    """/speckit-ac-tests-write fresh. Skipped: solution build, unit tests, export_refs.py (need dotnet)."""
    run(project, "ac_feature.py", "--feature", "F001")
    run(project, "ac_lock.py", "verify", "sources", "--feature", "F001")
    run(project, "ac_lock.py", "verify", "features", "--feature", "F001")
    run(project, "clear_generated.py", "steps", "--feature", "F001")
    return start_subagent(project, W, ("new_run.py", "write", "--feature", "F001"), [
        (f"{AC}/StepDefinitions/F001/AlphaSteps.cs", "[Binding, Scope(Tag = \"F001\")] public class AlphaSteps {}\n"),
        (f"{AC}/Support/Shared/Money.cs", "public record Money(decimal Amount, string Currency);\n"),
        (f"{S1}/ac/runs/run-001/writer-report.md", "# Writer report — F001 / run-001\n")])


def test_walk_translate(project):
    translate(project)
    assert json.loads((project / S1 / "ac/runs/translate-001/skipped.json").read_text(encoding="utf-8")) == ["AC-002"]
    assert (project / S1 / "ac/features.lock").is_file()


def test_walk_tests_write(project):
    translate(project)
    message = write_tests(project)
    assert f"Write step definitions to: {AC}/StepDefinitions/F001/" in message  # allowed despite the text rule
    assert "Feedback to address" not in message  # no judge feedback yet


def test_walk_tests_analyze(project):
    """/speckit-ac-tests-analyze. Skipped: AC project build and test run (dotnet); the TRX is a fixture."""
    translate(project)
    write_tests(project)
    run(project, "ac_feature.py", "--all")
    run(project, "ac_feature.py", "--feature", "F001")
    run(project, "ac_lock.py", "verify", "sources", "--feature", "F001")
    run(project, "ac_lock.py", "verify", "features", "--feature", "F001")
    assert (project / S1 / "ac/runs/run-001/writer-report.md").is_file()
    analyze = run(project, "new_analyze.py", "--feature", "F001").splitlines()[0]
    write(project / analyze / "ac-results.trx", TRX)
    out = run(project, "summarize_trx.py", f"{analyze}/ac-results.trx", f"{analyze}/ac-results.md",
              "--current", "F001")
    assert "failed 1" in out
    # Rules step 1 (new_analyze.py) already ran: the judge starts at task_message.py.
    run(project, "task_message.py", "--feature", "F001")
    run(project, "changed_files.py", "snapshot")
    message = json.loads((project / ".workflow/active-run.json").read_text(encoding="utf-8"))["taskMessage"]
    assert launch(project, J, message) == ALLOW
    subagent_write(project, J, f"{analyze}/judge-report.md", JUDGE)
    run(project, "changed_files.py", "check", J)
    run(project, "extract_feedback.py", f"{analyze}/judge-report.md", f"{analyze}/writer-feedback.md")
    assert "literal 11.34 USD" in (project / analyze / "writer-feedback.md").read_text(encoding="utf-8")
    # The next tests-write run gets the feedback line.
    run(project, "new_run.py", "write", "--feature", "F001")
    assert f"Feedback to address: {S1}/ac/runs/run-002/input-feedback.md" in run(
        project, "task_message.py", "--feature", "F001")


# ---- real spec-kit --------------------------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("specify") is None, reason="specify (spec-kit) not installed")
def test_real_spec_kit_install(tmp_path):
    """specify init --script ps + extension add --dev: the manifest is valid, the five skills are rendered with
    their command bodies unchanged, and the five optional hooks are registered."""
    def specify(*args, cwd):
        result = subprocess.run(["specify", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=180)
        assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]

    extension = tmp_path / "ext"
    shutil.copytree(PAYLOAD, extension, ignore=shutil.ignore_patterns("__pycache__"))
    specify("init", "proj", "--integration", "claude", "--script", "ps", "--non-interactive", cwd=tmp_path)
    project = tmp_path / "proj"
    specify("extension", "add", "--dev", str(extension), cwd=project)
    for name in NAMES:
        skill = (project / f".claude/skills/speckit-ac-{name}/SKILL.md").read_text(encoding="utf-8")
        lines = skill.split("\n")  # spec-kit's frontmatter is nested YAML (metadata:), so split it off by line
        end = lines.index("---", 1)
        assert f"name: speckit-ac-{name}" in lines[1:end]
        body = "\n".join(lines[end + 1:])
        assert body.strip() == frontmatter_and_body(text(name))[1].strip(), name
    registered = (project / ".specify/extensions.yml").read_text(encoding="utf-8")
    assert registered.count("extension: ac") == 5
    for name in ("critic", "translate", "tests-write"):
        assert f"command: speckit.ac.{name}" in registered
    assert (project / ".specify/extensions/ac/agents/ac-test-writer.md").is_file()
    assert (project / ".specify/extensions/ac/templates/acceptance-template.md").is_file()
