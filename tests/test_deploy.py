"""speckit-ac install / uninstall / upgrade / doctor against a fake spec-kit (S06-R01–R16, R18; A04–A07)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fakespecify import EMPTY_YML, FakeHost, copy_payload, make_project, snapshot, write
from speckit_ac import __version__, cli, deploy
from speckit_ac.deploy import DeployError

ROLES = ("ac-feature-translator", "ac-test-writer", "ac-test-fail-judge")
AGENTS = [f".claude/agents/{r}.md" for r in ROLES]
SKILL = ".claude/skills/speckit-ac-init/SKILL.md"


@pytest.fixture
def payload(tmp_path):
    return copy_payload(tmp_path / "payload")


@pytest.fixture
def project(tmp_path):
    return make_project(tmp_path)


@pytest.fixture
def host(project):
    return FakeHost(project)


def install(project, host, payload):
    return deploy.install(project, host, payload)


def settings(project):
    return json.loads((project / ".claude/settings.json").read_text(encoding="utf-8"))


def ours(project):
    return [g for g in settings(project).get("hooks", {}).get("PreToolUse", []) if deploy.is_ours(g)]


def manifest(project):
    return json.loads((project / deploy.MANIFEST).read_text(encoding="utf-8"))


# ---- install ---------------------------------------------------------------------------------------------------

def test_install_deploys_everything(project, host, payload, capsys):
    assert install(project, host, payload) == 0
    out = capsys.readouterr().out
    assert "Next steps" in out and "/speckit-ac-init smoke" in out and "NEW Claude Code session" in out
    for rel in AGENTS:
        assert (project / rel).read_bytes() == (payload / "agents" / Path(rel).name).read_bytes()
    skills = sorted((project / ".claude/skills").glob("speckit-ac-*/SKILL.md"))
    assert len(skills) == 5
    for skill in skills:
        assert not skill.is_symlink()
        assert deploy.has_skill_flag(skill.read_text(encoding="utf-8"))
    assert ours(project) == [deploy.guard_group()]
    claude = (project / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.startswith("# Project\n\nHouse rules.\n\n" + deploy.MD_BEGIN)
    m = manifest(project)
    assert m["version"] == __version__ and m["command"] == deploy.GUARD_COMMAND
    kinds = {f["kind"] for f in m["files"]}
    assert kinds == {"agent", "skill", "extension"}
    paths = {f["path"] for f in m["files"]}
    assert set(AGENTS) <= paths and SKILL in paths and deploy.GUARD_REL in paths
    assert m["preexisting"][".claude/settings.json"] is False and m["preexisting"][".specify/extensions"] is False
    assert m["settingsCreatedKeys"] == ["hooks", "hooks.PreToolUse"]


def test_guard_command_is_the_spec_string():
    assert deploy.guard_group() == {"matcher": "*", "hooks": [{
        "type": "command",
        "command": 'uv run --no-project python -I "$CLAUDE_PROJECT_DIR/.specify/extensions/ac/hooks/guard.py"',
        "timeout": 30, "onFailure": "block"}]}


def test_install_order_by_state(project, host, payload):
    """A04: specify add first; the self-test runs while the guard is not registered; registration then manifest."""
    install(project, host, payload)
    commands = [" ".join(c) for c, _ in host.calls]
    add = next(i for i, c in enumerate(commands) if c.startswith("specify extension add"))
    tests = [i for i, c in enumerate(commands) if "guard.py" in c]
    assert len(tests) == 2 and add < tests[0]
    assert all(not registered for c, registered in host.calls if "guard.py" in " ".join(c))


@pytest.mark.parametrize("problem,setup", [
    ("OS is Linux", lambda p, h: setattr(h, "os", "Linux")),
    ("pwsh is not on PATH", lambda p, h: h.missing.add("pwsh")),
    ("uv is not on PATH", lambda p, h: h.missing.add("uv")),
    ("specify is not on PATH", lambda p, h: h.missing.add("specify")),
    ("too old", lambda p, h: setattr(h, "specify_version", "specify 1.0.1")),
    ("could not read the spec-kit version", lambda p, h: setattr(h, "specify_version", "boom")),
    ("needs >= 3.11", lambda p, h: setattr(h, "python_version", "3.10")),
    ('"script": "sh"', lambda p, h: write(p / ".specify/init-options.json", '{"script": "sh", "integration": "claude"}')),
    ('"integration": "copilot"', lambda p, h: write(p / ".specify/init-options.json",
                                                    '{"script": "ps", "integration": "copilot"}')),
    ("init-options.json is missing", lambda p, h: (p / ".specify/init-options.json").unlink()),
    ("CLAUDE.md is missing", lambda p, h: (p / "CLAUDE.md").unlink()),
    ("no .sln or .slnx", lambda p, h: (p / "App.slnx").unlink()),
    ("not a git repository", lambda p, h: setattr(h, "git", "false")),
])
def test_prerequisites_stop_install_before_any_change(project, host, payload, problem, setup):
    setup(project, host)
    before = snapshot(project)
    with pytest.raises(DeployError, match="before any change") as error:
        install(project, host, payload)
    assert problem in str(error.value)
    assert snapshot(project) == before
    assert not host.commands("specify extension")


@pytest.mark.parametrize("output, problem", [
    ("warning: a uv notice\n3.14", None),       # warnings before the version line
    ("Python 3.12", None),                      # a word before the version
    ("3.14  ", None),                           # trailing spaces
    ("3.10", "needs >= 3.11"),
    ("", "does not start Python"),
    ("3.14\nTraceback: boom", "does not start Python"),  # the version must be on the last line
    ("3.14.1", "does not start Python"),       # major.minor only
    ("1" * 20000 + ".", "does not start Python"),  # long digit run without a match: fails fast (S8786)
])
def test_python_version_output_shapes(project, host, payload, output, problem):
    host.python_version = output
    if problem is None:
        install(project, host, payload)
        return
    with pytest.raises(DeployError, match="before any change") as error:
        install(project, host, payload)
    assert problem in str(error.value)


def test_timeout_is_a_reported_problem(project, host, payload):
    host.fail["uv run"] = (None, "uv run --no-project timed out after 300 s")
    with pytest.raises(DeployError, match="timed out"):
        install(project, host, payload)


@pytest.mark.parametrize("problem,setup", [
    ("already deployed", lambda p: write(p / ".workflow/deploy.json", "{}")),
    ("already installed", lambda p: write(p / ".specify/extensions/.registry", '{"extensions": {"ac": {}}}')),
    ("exists with other content", lambda p: write(p / ".claude/agents/ac-test-writer.md", "mine\n")),
    ("not valid JSON", lambda p: write(p / ".claude/settings.json", "{oops")),
    ("not a JSON object", lambda p: write(p / ".claude/settings.json", "[]")),
    ('"hooks" in .claude/settings.json is not an object', lambda p: write(p / ".claude/settings.json",
                                                                          '{"hooks": []}')),
    ("not a list of objects", lambda p: write(p / ".claude/settings.json", '{"hooks": {"PreToolUse": ["x"]}}')),
    ("is invalid", lambda p: write(p / ".workflow/config.json", '{"schemaVersion": 1}')),
])
def test_refusals_before_any_change(project, host, payload, problem, setup):
    setup(project)
    before = snapshot(project)
    with pytest.raises(DeployError, match="before any change") as error:
        install(project, host, payload)
    assert problem in str(error.value)
    assert snapshot(project) == before
    assert not host.commands("specify extension")


def test_identical_preexisting_agent_is_accepted_and_kept(project, host, payload):
    rel = AGENTS[1]
    write(project / rel, (payload / "agents/ac-test-writer.md").read_text(encoding="utf-8").replace("\n", "\r\n"))
    before = snapshot(project)
    install(project, host, payload)
    assert (project / rel).read_bytes() == before[rel]  # not rewritten (CRLF kept)
    deploy.uninstall(project, host)
    assert snapshot(project) == before


@pytest.mark.parametrize("failing", ["skills", "self-test", "registration"])
def test_failed_install_is_undone(project, host, payload, monkeypatch, failing):
    before = snapshot(project)
    if failing == "skills":
        monkeypatch.setattr(deploy, "patch_skills", lambda root: (_ for _ in ()).throw(DeployError("boom")))
    elif failing == "self-test":
        host.fail[f"uv run --no-project python -I {project / deploy.GUARD_REL}"] = (2, "blocked")
    else:
        monkeypatch.setattr(deploy, "write_manifest", lambda root, m: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(DeployError) as error:
        install(project, host, payload)
    assert "was undone" in str(error.value)
    assert snapshot(project) == before
    if failing == "self-test":
        assert not any(registered for _, registered in host.calls)


def test_failed_undo_prints_manual_steps(project, host, payload, monkeypatch):
    monkeypatch.setattr(deploy, "write_manifest", lambda root, m: (_ for _ in ()).throw(OSError("disk full")))
    host.fail["specify extension remove"] = (1, "locked")
    with pytest.raises(DeployError) as error:
        install(project, host, payload)
    assert "Undoing it failed too" in str(error.value) and "Undo by hand" in str(error.value)
    assert not ours(project) if (project / ".claude/settings.json").exists() else True


def test_no_bytecode_reaches_the_install(project, host, payload):
    """A07: a payload with __pycache__ / *.pyc (a compiled wheel) installs without them."""
    write(payload / "scripts/__pycache__/aclib.cpython-311.pyc", "bytes")
    write(payload / "scripts/stray.pyc", "bytes")
    install(project, host, payload)
    ext = project / deploy.EXT
    assert not [p for p in ext.rglob("*") if p.name == "__pycache__" or p.suffix == ".pyc"]
    assert not (ext / ".extensionignore").exists()
    assert not [f for f in manifest(project)["files"] if "__pycache__" in f["path"] or f["path"].endswith(".pyc")]


def test_payload_module_writes_no_bytecode(tmp_path):
    """R03: the CLI's import of payload modules leaves no __pycache__ and shares one aclib (one AcError class)."""
    copy = copy_payload(tmp_path / "payload")
    code = ("import sys; from pathlib import Path; from speckit_ac.paths import payload_module; "
            f"m = payload_module('init_config', Path(r'{copy}')); "
            "assert sys.modules['aclib'].AcError is m.aclib.AcError; print(m.PYTHON)")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == deploy.PYTHON
    assert not list(copy.rglob("__pycache__"))


def test_payload_ships_extensionignore():
    text = (deploy.payload_dir() / ".extensionignore").read_text(encoding="utf-8").split()
    assert text == ["__pycache__/", "*.pyc"]


# ---- skills ----------------------------------------------------------------------------------------------------

SKILL_TEXT = ("---\nname: speckit-ac-init\ndescription: 'x'\ncompatibility: c\nmetadata:\n  author: a\n"
              "  source: ac:commands/speckit.ac.init.md\n---\n\n# body\n")


def test_patch_adds_the_flag_before_metadata_and_changes_nothing_else():
    patched = deploy.patch_skill_text(SKILL_TEXT)
    assert patched == SKILL_TEXT.replace("metadata:\n", "disable-model-invocation: true\nmetadata:\n")


def test_patch_keeps_crlf():
    text = SKILL_TEXT.replace("\n", "\r\n")
    assert deploy.patch_skill_text(text) == text.replace("metadata:\r\n", "disable-model-invocation: true\r\nmetadata:\r\n")


def test_patch_sets_an_existing_key():
    text = SKILL_TEXT.replace("compatibility: c\n", "disable-model-invocation: false\n")
    assert deploy.patch_skill_text(text) == SKILL_TEXT.replace("compatibility: c\n", "disable-model-invocation: true\n")


def test_patch_without_metadata_inserts_before_the_closing_line():
    text = "---\nname: x\n---\nbody\n"
    assert deploy.patch_skill_text(text) == "---\nname: x\ndisable-model-invocation: true\n---\nbody\n"


@pytest.mark.parametrize("text", ["no frontmatter\n", "---\nname: x\n"])
def test_patch_refuses_broken_frontmatter(text):
    with pytest.raises(DeployError):
        deploy.patch_skill_text(text)


@pytest.mark.parametrize("symlinks", [True, False])
def test_patch_skills_makes_real_files(project, host, payload, symlinks):
    host.symlinks = symlinks
    deploy.specify_add(project, host, payload)
    if symlinks:
        assert (project / SKILL).is_symlink()
    target = (project / SKILL).read_text(encoding="utf-8")
    deploy.patch_skills(project)
    assert not (project / SKILL).is_symlink()
    assert (project / SKILL).read_text(encoding="utf-8") == deploy.patch_skill_text(target)
    assert "source: ac:commands/speckit.ac.init.md" in (project / SKILL).read_text(encoding="utf-8")


def test_patch_skills_refuses_a_skill_folder_that_leads_outside(project, host, payload, tmp_path):
    """A speckit-ac skill folder that is a directory link must not make the patch write outside the project."""
    host.symlinks = False
    deploy.specify_add(project, host, payload)
    folder = (project / SKILL).parent
    outside = tmp_path / "outside" / folder.name
    shutil.copytree(folder, outside)
    shutil.rmtree(folder)
    os.symlink(outside, folder, target_is_directory=True)
    before = (outside / "SKILL.md").read_bytes()
    with pytest.raises(DeployError, match="leads outside"):
        deploy.patch_skills(project)
    assert (outside / "SKILL.md").read_bytes() == before


# ---- settings.json -----------------------------------------------------------------------------------------------

OTHER_GROUP = {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo other"}]}


def test_register_keeps_other_keys_and_hooks_and_appends_last(project):
    original = {"env": {"A": "b"}, "hooks": {"PreToolUse": [OTHER_GROUP], "PostToolUse": []}, "z": 1}
    write(project / ".claude/settings.json", json.dumps(original, indent=2) + "\n")
    result = deploy.register_guard(project)
    assert result == {"createdFile": False, "createdKeys": [], "reformatted": False}
    data = settings(project)
    assert list(data) == ["env", "hooks", "z"]
    assert data["hooks"]["PreToolUse"] == [OTHER_GROUP, deploy.guard_group()]
    deploy.register_guard(project)
    assert settings(project)["hooks"]["PreToolUse"] == [OTHER_GROUP, deploy.guard_group()]  # replaced, not doubled


def test_register_replaces_an_old_group_of_ours(project):
    old = {"matcher": "*", "hooks": [{"type": "command", "command": f"python {deploy.GUARD_REL}"}]}
    write(project / ".claude/settings.json", json.dumps({"hooks": {"PreToolUse": [old, OTHER_GROUP]}}, indent=2))
    deploy.register_guard(project)
    assert settings(project)["hooks"]["PreToolUse"] == [OTHER_GROUP, deploy.guard_group()]


def test_register_reports_reformatting_and_keeps_crlf(project):
    write(project / ".claude/settings.json", '{"a":1}\r\n')
    assert deploy.register_guard(project)["reformatted"] is True
    text = (project / ".claude/settings.json").read_bytes()
    assert b"\r\n" in text and b"\n" not in text.replace(b"\r\n", b"")


def test_unregister_drops_only_created_keys(project):
    write(project / ".claude/settings.json", '{\n  "hooks": {}\n}\n')
    result = deploy.register_guard(project)
    assert result["createdKeys"] == ["hooks.PreToolUse"]
    deploy.unregister_guard(project, False, result["createdKeys"])
    assert (project / ".claude/settings.json").read_text(encoding="utf-8") == '{\n  "hooks": {}\n}\n'


def test_unregister_leaves_unrecognised_groups(project):
    data = {"hooks": {"PreToolUse": [{"matcher": "*"}, {"hooks": "x"}, {"hooks": [{"command": 3}]}]}}
    write(project / ".claude/settings.json", json.dumps(data, indent=2) + "\n")
    before = (project / ".claude/settings.json").read_bytes()
    assert deploy.unregister_guard(project) is False
    assert (project / ".claude/settings.json").read_bytes() == before


def test_unregister_deletes_a_created_empty_file(project):
    result = deploy.register_guard(project)
    assert result["createdFile"] is True
    deploy.unregister_guard(project, True, result["createdKeys"])
    assert not (project / ".claude/settings.json").exists()


# ---- CLAUDE.md block ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_claude_block_round_trip(project, newline):
    original = f"# Project{newline}{newline}Rules.{newline}"
    write(project / "CLAUDE.md", original)
    deploy.write_claude_block(project)
    text = (project / "CLAUDE.md").read_bytes().decode("utf-8")
    assert text.startswith(original + newline + deploy.MD_BEGIN + newline)
    assert text.endswith(deploy.MD_END + newline)
    assert "StepDefinitions/" in text and "acProjectDir" in text
    deploy.write_claude_block(project)
    assert (project / "CLAUDE.md").read_bytes().decode("utf-8") == text  # replaced in place
    deploy.remove_claude_block(project)
    assert (project / "CLAUDE.md").read_bytes().decode("utf-8") == original


def test_claude_block_is_ascii():
    assert all(line.isascii() for line in deploy.CLAUDE_BLOCK)


# ---- uninstall ---------------------------------------------------------------------------------------------------

def test_round_trip_is_byte_identical(project, host, payload):
    before = snapshot(project)
    install(project, host, payload)
    deploy.uninstall(project, host)
    assert snapshot(project) == before


def test_round_trip_with_existing_settings_and_agents(project, host, payload):
    write(project / ".claude/settings.json", json.dumps({"hooks": {"PreToolUse": [OTHER_GROUP]}}, indent=2) + "\n")
    write(project / ".claude/agents/reviewer.md", "---\nname: reviewer\n---\n")
    before = snapshot(project)
    install(project, host, payload)
    deploy.uninstall(project, host)
    assert snapshot(project) == before


def test_round_trip_with_empty_hooks(project, host, payload):
    write(project / ".claude/settings.json", '{\n  "hooks": {}\n}\n')
    before = snapshot(project)
    install(project, host, payload)
    deploy.uninstall(project, host)
    assert snapshot(project) == before


def test_round_trip_keeps_preexisting_spec_kit_files(project, host, payload):
    write(project / ".specify/extensions.yml", "installed: []\nsettings:\n  auto_execute_hooks: true\nhooks: {}\n")
    write(project / ".specify/extensions/.registry", '{"schema_version": "1.0", "extensions": {}}')
    install(project, host, payload)
    deploy.uninstall(project, host)
    assert (project / ".specify/extensions.yml").read_bytes() == EMPTY_YML.encode()  # spec-kit's, kept
    assert (project / ".specify/extensions/.registry").is_file()


def test_uninstall_takes_the_guard_off_before_spec_kit_removes_it(project, host, payload):
    install(project, host, payload)
    deploy.uninstall(project, host)
    removes = host.commands("specify extension remove")
    assert removes and all(not registered for _, registered in removes)


def test_uninstall_keeps_changed_agent_and_warns(project, host, payload, capsys):
    install(project, host, payload)
    write(project / AGENTS[0], "my own translator\n")
    deploy.uninstall(project, host)
    assert (project / AGENTS[0]).read_text(encoding="utf-8") == "my own translator\n"
    assert not (project / AGENTS[1]).exists()
    assert f"warn: {AGENTS[0]} was changed after install, so it is kept" in capsys.readouterr().out


def test_uninstall_warns_about_changed_skill(project, host, payload, capsys):
    install(project, host, payload)
    write(project / SKILL, "changed\n")
    deploy.uninstall(project, host)
    assert f"warn: {SKILL} was changed after install" in capsys.readouterr().out


def test_uninstall_removes_init_blocks_and_lists_user_data(project, host, payload, capsys):
    install(project, host, payload)
    import aclib
    aclib.write_block(project / ".gitignore", ["/artifacts/refs/"])
    write(project / ".gitattributes", "*.png binary\n")
    aclib.write_block(project / ".gitattributes", ["x text eol=lf"])
    write(project / ".workflow/config.json", "{}")
    write(project / "specs/001-a/acceptance.md")
    write(project / "specs/001-a/ac/sources.lock")
    deploy.uninstall(project, host)
    out = capsys.readouterr().out
    assert not (project / ".gitignore").exists()  # created by init, empty afterwards
    assert (project / ".gitattributes").read_text(encoding="utf-8") == "*.png binary\n"
    assert ".workflow/config.json" in out and "specs/001-a/acceptance.md" in out and "specs/001-a/ac/" in out
    assert (project / ".workflow/config.json").is_file() and (project / "specs/001-a/ac/sources.lock").is_file()


def test_uninstall_without_manifest_prints_manual_steps(project, host):
    with pytest.raises(DeployError, match="Undo by hand"):
        deploy.uninstall(project, host)
    assert not host.calls


def test_uninstall_can_be_rerun_after_a_failure(project, host, payload, capsys):
    before = snapshot(project)
    install(project, host, payload)
    write(project / ".gitignore", "# >>> speckit-ac (managed; do not edit)\n/x/\n")  # no end marker
    with pytest.raises(DeployError, match="without"):
        deploy.uninstall(project, host)
    assert not ours(project) if (project / ".claude/settings.json").exists() else True
    (project / ".gitignore").unlink()
    deploy.uninstall(project, host)
    assert snapshot(project) == before


# ---- upgrade -----------------------------------------------------------------------------------------------------

def test_upgrade_repatches_skills_and_keeps_changed_agent(project, host, payload, capsys):
    install(project, host, payload)
    write(project / AGENTS[2], "my judge\n")
    capsys.readouterr()
    assert deploy.upgrade(project, host, payload) == 0
    out = capsys.readouterr().out
    assert f"warn: {AGENTS[2]} was changed after install" in out
    assert (project / AGENTS[2]).read_text(encoding="utf-8") == "my judge\n"
    assert deploy.has_skill_flag((project / SKILL).read_text(encoding="utf-8"))
    assert not (project / SKILL).is_symlink()
    assert ours(project) == [deploy.guard_group()]
    entry = next(f for f in manifest(project)["files"] if f["path"] == AGENTS[2])
    assert entry["sha256"] == deploy.content_hash(project / deploy.EXT / "agents/ac-test-fail-judge.md")
    deploy.uninstall(project, host)
    assert (project / AGENTS[2]).read_text(encoding="utf-8") == "my judge\n"
    assert f"warn: {AGENTS[2]} was changed after install" in capsys.readouterr().out


def test_upgrade_carries_created_keys_forward(project, host, payload):
    install(project, host, payload)
    data = settings(project)
    data["hooks"]["PreToolUse"].insert(0, OTHER_GROUP)
    write(project / ".claude/settings.json", json.dumps(data, indent=2) + "\n")
    deploy.upgrade(project, host, payload)
    assert manifest(project)["settingsCreatedKeys"] == ["hooks", "hooks.PreToolUse"]
    data = settings(project)
    data["hooks"]["PreToolUse"].remove(OTHER_GROUP)
    write(project / ".claude/settings.json", json.dumps(data, indent=2) + "\n")
    deploy.uninstall(project, host)
    assert not (project / ".claude/settings.json").exists()


def test_upgrade_reregisters_after_a_failed_add(project, host, payload, capsys):
    install(project, host, payload)
    host.fail["specify extension add"] = (1, "network down")
    with pytest.raises(DeployError, match="registered again"):
        deploy.upgrade(project, host, payload)
    assert ours(project) == [deploy.guard_group()]


def test_upgrade_without_install_is_refused(project, host, payload):
    with pytest.raises(DeployError, match="not deployed"):
        deploy.upgrade(project, host, payload)


def test_upgrade_then_uninstall_round_trips(project, host, payload):
    before = snapshot(project)
    install(project, host, payload)
    deploy.upgrade(project, host, payload)
    deploy.uninstall(project, host)
    assert snapshot(project) == before


# ---- doctor ------------------------------------------------------------------------------------------------------

def doctor(project, host, capsys):
    code = deploy.doctor(project, host)
    return code, capsys.readouterr().out


def test_doctor_passes_after_install_and_writes_nothing(project, host, payload, capsys):
    install(project, host, payload)
    capsys.readouterr()
    before = snapshot(project)
    code, out = doctor(project, host, capsys)
    assert code == 0, out
    assert "[FAIL]" not in out and "[warn] no .workflow/config.json yet" in out
    assert "/speckit-ac-init" in out.splitlines()[-1]
    assert snapshot(project) == before


def test_doctor_folds_crlf(project, host, payload, capsys):
    """D1: an autocrlf=true clone checks the files out with CRLF."""
    install(project, host, payload)
    for entry in manifest(project)["files"]:
        path = project / entry["path"]
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    capsys.readouterr()
    code, out = doctor(project, host, capsys)
    assert code == 0, out


def valid_config(project):
    sys.path.insert(0, str(Path(__file__).parent))
    from acproject import CONFIG
    return dict(CONFIG)


@pytest.mark.parametrize("breakage,expected", [
    ("skill flag", "lacks `disable-model-invocation: true`"),
    ("skill symlink", "is a symlink"),
    ("guard changed", "changed since deploy: .specify/extensions/ac/hooks/guard.py"),
    ("not registered", "the guard is not registered"),
    ("registered twice", "registered 2 times"),
    ("config python", 'config "python" is `py -3`'),
    ("no block", "CLAUDE.md has no speckit-ac block"),
    ("registry", "is not installed"),
    ("missing file", "missing: .specify/extensions/ac/scripts/aclib.py"),
    ("broken settings", "guard registration"),
    ("broken manifest", "deploy manifest"),
    ("invalid config", "config"),
])
def test_doctor_fails(project, host, payload, capsys, breakage, expected):
    install(project, host, payload)
    skill = project / SKILL
    if breakage == "skill flag":
        skill.write_text(skill.read_text(encoding="utf-8").replace("disable-model-invocation: true\n", ""),
                         encoding="utf-8")
    elif breakage == "skill symlink":
        skill.unlink()
        os.symlink(os.path.relpath(project / deploy.EXT / ".specify-dev/agent-commands/claude/speckit-ac-init/SKILL.md",
                                   skill.parent), skill)
    elif breakage == "guard changed":
        with open(project / deploy.GUARD_REL, "a", encoding="utf-8") as f:
            f.write("\n# edited\n")
    elif breakage == "not registered":
        deploy.unregister_guard(project)
    elif breakage == "registered twice":
        data = settings(project)
        data["hooks"]["PreToolUse"].append(deploy.guard_group())
        write(project / ".claude/settings.json", json.dumps(data, indent=2))
    elif breakage == "config python":
        cfg = valid_config(project)
        cfg["python"] = "py -3"
        write(project / ".workflow/config.json", json.dumps(cfg))
    elif breakage == "no block":
        deploy.remove_claude_block(project)
    elif breakage == "registry":
        write(project / ".specify/extensions/.registry", '{"extensions": {}}')
    elif breakage == "missing file":
        (project / deploy.EXT / "scripts/aclib.py").unlink()
    elif breakage == "broken settings":
        write(project / ".claude/settings.json", "{oops")
    elif breakage == "broken manifest":
        write(project / deploy.MANIFEST, "{}")
    elif breakage == "invalid config":
        write(project / ".workflow/config.json", '{"schemaVersion": 1}')
    capsys.readouterr()
    code, out = doctor(project, host, capsys)
    assert code == 1
    fails = [line for line in out.splitlines() if line.startswith("[FAIL]")]
    assert any(expected in line for line in fails), out
    assert out.splitlines()[-2].endswith("FAIL")  # the total line still comes


def test_doctor_config_ok_and_blocks(project, host, payload, capsys):
    install(project, host, payload)
    import aclib
    write(project / ".workflow/config.json", json.dumps(valid_config(project)))
    aclib.write_block(project / ".gitignore", ["x"])
    capsys.readouterr()
    code, out = doctor(project, host, capsys)
    assert "[FAIL] .gitattributes has no speckit-ac block" in out and code == 1
    aclib.write_block(project / ".gitattributes", ["x"])
    code, out = doctor(project, host, capsys)
    assert code == 0, out
    assert 'valid; "python" matches the guard command' in out


def test_doctor_warns_on_changed_agent_and_extra_file(project, host, payload, capsys):
    install(project, host, payload)
    write(project / AGENTS[0], "mine\n")
    write(project / deploy.EXT / "notes.txt", "x")
    capsys.readouterr()
    code, out = doctor(project, host, capsys)
    assert code == 0, out
    assert f"[warn] changed since deploy: {AGENTS[0]}" in out
    assert "[warn] not in the manifest: .specify/extensions/ac/notes.txt" in out


def test_doctor_warns_on_version_mismatch(project, host, payload, capsys):
    install(project, host, payload)
    m = manifest(project)
    m["version"] = "0.0.1"
    write(project / deploy.MANIFEST, json.dumps(m))
    capsys.readouterr()
    code, out = doctor(project, host, capsys)
    assert "[warn] deployed 0.0.1" in out


def test_doctor_without_install(project, host, capsys):
    code, out = doctor(project, host, capsys)
    assert code == 1 and "[FAIL] deploy manifest" in out and "skipped (no valid manifest)" in out


# ---- CLI ---------------------------------------------------------------------------------------------------------

def test_cli_help_lists_the_commands(capsys):
    assert cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    for name in ("install", "uninstall", "upgrade", "doctor"):
        assert name in out


@pytest.mark.parametrize("command", ["install", "uninstall", "upgrade", "doctor"])
def test_cli_needs_the_project_root(tmp_path, monkeypatch, capsys, command):
    project = make_project(tmp_path)
    (project / "src").mkdir()
    monkeypatch.chdir(project / "src")  # a sub-folder: no search upwards
    assert cli.main([command]) == 1
    err = capsys.readouterr().err
    assert err.startswith("FAIL: ") and "has no .specify/ folder" in err


def test_cli_unknown_command_is_a_usage_error(capsys):
    assert cli.main(["frobnicate"]) == 2


def test_cli_output_is_ascii(tmp_path, monkeypatch, capsys):
    project = make_project(tmp_path)
    host = FakeHost(project)
    host.fail["specify extension add"] = (1, "Fehler: äöü ✗ failed")
    monkeypatch.setattr(deploy, "Host", lambda: host)
    monkeypatch.setattr(deploy, "payload_dir", lambda: copy_payload(tmp_path / "payload"))
    monkeypatch.chdir(project)
    assert cli.main(["install"]) == 1
    err = capsys.readouterr().err
    assert err.isascii() and "\\xe4" in err


@pytest.mark.parametrize("text", [
    '{\n  "env": {\n    "NAME": "Zoë"\n  },\n  "hooks": {}\n}\n',
    '{\r\n  "hooks": {\r\n    "PreToolUse": []\r\n  }\r\n}\r\n',
])
def test_round_trip_survives_spec_kit_rewriting_settings(project, host, payload, text):
    """spec-kit rewrites an existing settings.json on add / remove (CRLF, non-ASCII escaped); uninstall restores the
    file's own line ending and characters."""
    write(project / ".claude/settings.json", text)
    before = snapshot(project)
    install(project, host, payload)
    assert manifest(project)["settingsNewline"] == ("CRLF" if "\r\n" in text else "LF")
    deploy.uninstall(project, host)
    assert snapshot(project) == before
