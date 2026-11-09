"""Tests for the three AC subagent definitions (payload/agents/*.md), step 3.

The agents are prompts, so these tests check what can be checked without running a model: the frontmatter, the
absence of CT specifics and hard-coded paths, the task-message template, and — the main point — that every input
the template names is readable, and every output writable, for that role under the real guard and a real
active-run marker written by the run scripts. Templates are filled mechanically from `ac_feature.py` and the
config by task_message.py (the script the commands use), so renaming a key on either side fails here.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from acproject import AC, PAYLOAD, make_project, run_guard, run_script, write

AGENTS = PAYLOAD / "agents"
T, W, J = "ac-feature-translator", "ac-test-writer", "ac-test-fail-judge"
ALLOW, DENY = 0, 2

FRONTMATTER = {
    T: {"command": "/speckit-ac-translate", "tools": ["Read", "Write", "Edit", "Grep", "Glob", "Bash"],
        "disallowed": ["Skill", "Agent", "mcp__*"]},
    W: {"command": "/speckit-ac-tests-write", "tools": ["Read", "Write", "Edit", "Grep", "Glob", "Bash"],
        "disallowed": ["Skill", "Agent", "mcp__*"]},
    J: {"command": "/speckit-ac-tests-analyze", "tools": ["Read", "Write", "Grep", "Glob"],
        "disallowed": ["Skill", "Agent", "Bash", "mcp__*"]},
}

# How the guard-consistency test exercises each template line. A new label must be added here on purpose.
KINDS = {
    T: {"Feature": "value", "Run": "value", "Spec": "file", "Constitution": "file",
        "Other spec inputs": "spec-inputs", "Acceptance criteria": "file", "Golden samples": "dir",
        "Write feature files to": "write-feature", "Allowed build command": "command",
        "Write your report to": "write-file"},
    W: {"Feature": "value", "Run": "value", "Spec": "file", "Constitution": "file",
        "Other spec inputs": "spec-inputs", "Acceptance criteria (context only)": "file",
        "AC test project": "project", "Project file": "file", "Test framework": "value", "Feature files": "dir",
        "Golden samples": "dir", "Write step definitions to": "write-dir", "Feature support": "write-dir",
        "Shared support": "write-dir", "Public API listings": "dir", "Allowed build command": "command",
        "Feedback to address": "file", "Write your report to": "write-file"},
    J: {"Current feature": "value", "Run": "value", "Analyze": "value", "Feature folders": "feature-list",
        "Constitution": "file", "Other spec inputs": "spec-inputs", "AC test project": "project",
        "Public API listings": "dir", "Writer report": "file", "Test results": "file",
        "Write your report to": "write-file"},
}

CT_STRINGS = ["SPEC.md", "acSources", ".workflow/runs", "/ac-translate", "/ac-tests-write", "/ac-tests-analyze",
              "experiment", "knowledge-base", "CT."]
PATH_FRAGMENTS = ["specs/", ".workflow/", "Features/", "StepDefinitions/", "Support/", "Samples/"]
VERDICTS = ["TRANSLATION_FAULT", "TEST_FAULT", "IMPLEMENTATION_FAULT", "SPEC_AMBIGUITY", "UNEXPRESSIBLE",
            "SUPERSEDED", "INCONCLUSIVE"]
SECTION = "## Your task message"


def text(role):
    return (AGENTS / f"{role}.md").read_text(encoding="utf-8")


def frontmatter(role):
    lines = text(role).split("\n")
    assert lines[0] == "---"
    end = lines.index("---", 1)
    return dict(line.split(": ", 1) for line in lines[1:end])


def section(role):
    """The `## Your task message` section: template, placeholder table, optional-line note."""
    body = text(role)
    start = body.index(SECTION)
    end = body.find("\n## ", start + len(SECTION))
    return body[start:end if end != -1 else len(body)]


def body_outside_section(role):
    body = text(role)
    return body[body.index("\n---", 3) + 4:].replace(section(role), "")


def template(role):
    """[(label, value)] of the fenced template."""
    match = re.search(r"```text\n(.*?)\n```", section(role), re.DOTALL)
    assert match, f"{role}: no ```text template in {SECTION}"
    return [tuple(line.split(": ", 1)) for line in match[1].split("\n")]


def placeholders(value):
    return re.findall(r"<([A-Z_]+)>", value)


# ---- frontmatter and text ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("role", [T, W, J])
def test_frontmatter(role):
    meta = frontmatter(role)
    expected = FRONTMATTER[role]
    assert meta["name"] == role
    assert [t.strip() for t in meta["tools"].split(",")] == expected["tools"]
    assert [t.strip() for t in meta["disallowedTools"].split(",")] == expected["disallowed"]
    assert meta["omitClaudeMd"] == "true"
    assert "hooks" not in meta  # frontmatter hooks fail open in an untrusted folder
    assert expected["command"] in meta["description"]
    assert "never invoke it any other way" in meta["description"]


def test_agent_names_match_the_guard_and_scripts():
    guard = (PAYLOAD / "hooks/guard.py").read_text(encoding="utf-8")
    aclib = (PAYLOAD / "scripts/aclib.py").read_text(encoding="utf-8")
    for role in (T, W, J):
        assert f'"{role}"' in guard and f'"{role}"' in aclib
    assert sorted(p.stem for p in AGENTS.glob("*.md")) == sorted([T, W, J])


def test_no_ct_strings():
    for path in PAYLOAD.rglob("*"):
        if path.is_file() and path.suffix in (".md", ".py", ".yml"):
            content = path.read_text(encoding="utf-8")
            found = [s for s in CT_STRINGS if s in content]
            assert not found, f"{path.relative_to(PAYLOAD)}: {found}"


@pytest.mark.parametrize("role", [T, W, J])
def test_no_hard_coded_paths(role):
    """Agents name inputs by their task-message labels; paths live only in the task-message section."""
    body = body_outside_section(role)
    assert not [f for f in PATH_FRAGMENTS if f in body]


@pytest.mark.parametrize("role", [T, W, J])
def test_placeholders_defined(role):
    used = {name for _, raw in template(role) for name in placeholders(raw)}
    table = set(re.findall(r"^\| `<([A-Z_]+)>` \|", section(role), re.MULTILINE))
    assert used == table


@pytest.mark.parametrize("role", [T, W, J])
def test_template_labels_known(role):
    labels = [label for label, _ in template(role)]
    assert len(labels) == len(set(labels))
    assert set(labels) == set(KINDS[role])


@pytest.mark.parametrize("role, optional", [(T, ["Other spec inputs"]), (W, ["Other spec inputs", "Feedback to address"]),
                                            (J, ["Other spec inputs"])])
def test_optional_lines_are_explained(role, optional):
    note = section(role).split("```", 2)[2]
    for label in optional:
        assert f"*{label}*" in note


# ---- guard consistency ----------------------------------------------------------------------------------------

def start_run(project, role):
    """Run the scripts a command runs before the subagent; return the run/analyze ids. They write the marker."""
    if role == T:
        out = run_script(project, "new_run.py", "translate", "--feature", "F001")
    else:
        out = run_script(project, "new_run.py", "write", "--feature", "F001")
        assert out.returncode == 0, out.stderr
        if role == J:
            (project / ".workflow/active-run.json").unlink()  # the writer's run ended at its check
            out = run_script(project, "new_analyze.py", "--feature", "F001")
    assert out.returncode == 0, out.stderr
    folder = out.stdout.splitlines()[0]
    if role == J:
        return {"RUN_ID": folder.split("/")[-2], "ANALYZE_ID": folder.split("/")[-1]}
    return {"RUN_ID": folder.split("/")[-1]}


def script_json(project, *args):
    out = run_script(project, "ac_feature.py", *args)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


class Guard:
    def __init__(self, project, role):
        self.project, self.role = project, role

    def __call__(self, tool, **tool_input):
        for key in ("file_path", "path"):
            if key in tool_input:
                tool_input[key] = str(self.project / tool_input[key])
        payload = {"tool_name": tool, "tool_input": tool_input, "hook_event_name": "PreToolUse",
                   "cwd": str(self.project), "agent_type": self.role}
        code, reason = run_guard(self.project, payload)
        return code, f"{tool} {tool_input}: {reason}"

    def allows(self, tool, **tool_input):
        code, why = self(tool, **tool_input)
        assert code == ALLOW, why

    def denies(self, tool, **tool_input):
        code, why = self(tool, **tool_input)
        assert code == DENY, why

    def read_dir(self, folder):
        folder = folder.rstrip("/")
        write(self.project / folder / "probe.txt")
        self.allows("Glob", path=folder, pattern="**/*")
        self.allows("Read", file_path=f"{folder}/probe.txt")


@pytest.mark.parametrize("role", [T, W, J])
def test_guard_consistency(tmp_path, role):
    """Every input the filled template names is readable and every output writable for the role, under the guard
    and the marker the run scripts wrote. The *AC test project* line also proves the agent text's warning: the
    project files are readable by name, a search rooted at the project folder is not."""
    project = make_project(tmp_path / "proj").resolve()
    ids = start_run(project, role)
    feature = script_json(project, "--feature", "F001")
    run_dir = f"{feature['runsDir']}/{ids['RUN_ID']}"
    # Files the command or an earlier step leaves for the subagent.
    write(project / run_dir / "input-feedback.md")
    write(project / run_dir / "writer-report.md")
    if role == J:
        write(project / run_dir / ids["ANALYZE_ID"] / "ac-results.md")
    # The message exactly as the command sends it (task_message.py, step 4), with every optional line present.
    out = run_script(project, "task_message.py", "--feature", "F001")
    assert out.returncode == 0, out.stderr
    message = [tuple(line.split(": ", 1)) for line in out.stdout.rstrip("\n").split("\n")]
    assert [label for label, _ in message] == [label for label, _ in template(role)]
    guard = Guard(project, role)

    for label, value in message:
        kind = KINDS[role][label]
        if kind == "value":
            continue
        if kind == "file":
            guard.allows("Read", file_path=value)
        elif kind == "dir":
            guard.read_dir(value)
        elif kind == "spec-inputs":
            for entry in value.split(", "):
                if (project / entry).is_dir():
                    guard.read_dir(entry)
                else:
                    guard.allows("Read", file_path=entry)
        elif kind == "feature-list":
            for item in value.split(", "):
                folder = item.split(" (")[0]
                guard.allows("Read", file_path=f"{folder}/spec.md")
                guard.allows("Read", file_path=f"{folder}/acceptance.md")
        elif kind == "project":
            folder = value.rstrip("/")
            write(project / folder / "Directory.Build.props")
            guard.allows("Read", file_path=f"{folder}/Directory.Build.props")
            guard.denies("Glob", path=folder, pattern="**/*")
            for sub in ("Features", "Samples", "StepDefinitions", "Support", "Support/Shared",
                        "StepDefinitions/F002", "Support/F002"):
                guard.allows("Glob", path=f"{folder}/{sub}", pattern="**/*")
        elif kind == "write-feature":
            name = feature["featureDir"].split("/")[-1].split("-", 1)[1]
            guard.allows("Write", file_path=f"{value.rstrip('/')}/{name}.feature", content="Feature: x\n")
        elif kind == "write-dir":
            guard.allows("Write", file_path=f"{value.rstrip('/')}/Probe.cs", content="class Probe {}\n")
        elif kind == "write-file":
            guard.allows("Write", file_path=value, content="# report\n")
        elif kind == "command":
            guard.allows("Bash", command=value)
        else:
            raise AssertionError(f"unknown kind {kind}")


# ---- role rules ---------------------------------------------------------------------------------------------

def test_translator_rules():
    body = text(T)
    assert "`@<TAG>`" in body
    assert "Exactly **one** `.feature` file" in body
    assert "without the leading number and dash" in body
    assert "@AC-001 @FR-003 @US1-AS2" in body
    assert "build blocked outside this feature" in body
    assert "# Translation report — <TAG> / <RUN_ID>" in body
    assert "earlier translation reports" not in body


def test_writer_rules():
    body = text(W)
    for phrase in ('[Scope(Tag = "<TAG>")]', "Never change the `[Scope]`", "`[BeforeTestRun]`",
                   "## Cross-feature changes", 'PendingStepException("API-CHANGED:',
                   'PendingStepException("UNEXPRESSIBLE:', "*Shared support* holds only plain helpers",
                   "never a `[Binding]` class", "# Writer report — <TAG> / <RUN_ID>", "## Missing packages"):
        assert phrase in body, phrase
    for framework in ("`xunit2`", "`xunit3`", "`nunit`", "`mstest`"):
        assert framework in body


def test_judge_rules():
    body = text(J)
    for verdict in VERDICTS:
        assert f"`{verdict}`" in body, verdict
    assert "| Feature/AC | Scope (current / regression) | Verdict | Confidence | One-line reason |" in body
    assert "# Judge report — <TAG> / <RUN_ID> / <ANALYZE_ID>" in body
    assert "**regression scenarios only**" in body
    assert "`API-CHANGED:`" in body
    assert '"Cross-feature changes"' in body
    feedback = (PAYLOAD / "scripts/extract_feedback.py").read_text(encoding="utf-8")
    for name in ("BEGIN", "END"):
        marker = re.search(rf'^{name} = "(.*)"$', feedback, re.MULTILINE)[1]
        assert body.count(marker) == 1, marker


def test_pending_prefixes_are_counted_as_pending():
    summarize = (PAYLOAD / "scripts/summarize_trx.py").read_text(encoding="utf-8")
    assert re.search(r'^PENDING = \(.*"PendingStepException"', summarize, re.MULTILINE)
    writer = text(W)
    for prefix in ("API-CHANGED:", "UNEXPRESSIBLE:"):
        assert f'throw new PendingStepException("{prefix}' in writer


@pytest.mark.parametrize("role", [T, W, J])
def test_final_message_rule_passes_the_handback_screen(role):
    """The final-message instruction itself must not need what the guard's hand-back screen blocks."""
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # no __pycache__ in the payload
    try:
        spec = importlib.util.spec_from_file_location("guard_code", PAYLOAD / "hooks/guard.py")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
    finally:
        sys.dont_write_bytecode = previous
    code = guard.CODE
    final = [p.replace("\n", " ") for p in text(role).split("\n\n") if p.startswith("Your final message back:")]
    assert len(final) == 1 and not code.search(final[0])
    assert role == J or "No " in final[0]
