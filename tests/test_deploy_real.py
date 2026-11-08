"""speckit-ac install / upgrade / uninstall / doctor with the real spec-kit, uv and git (S06-R18 (a)–(e); A02, A03, A07).

Skipped without `specify` (spec-kit) or off Windows. Each test builds a fresh `specify init --integration claude
--script ps` project, so the set takes a minute or two.
"""
import json
import platform
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from fakespecify import copy_payload, snapshot, write
from speckit_ac import __version__, deploy

REPO = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("specify") is None or platform.system() != "Windows"
                                or shutil.which("uv") is None, reason="needs specify, uv and Windows")
OTHER_GROUP = {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo other"}]}


def run(*cmd, cwd):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=300, env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    assert result.returncode == 0, f"{cmd}: {result.stdout[-1500:]}{result.stderr[-1500:]}"
    return result.stdout


def git(*args, cwd):
    return run("git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", "-c", "core.autocrlf=false", *args,
               cwd=cwd)


@pytest.fixture
def payload(tmp_path):
    """A payload copy with bytecode planted, as a compiled wheel would carry (A07)."""
    copy = copy_payload(tmp_path / "payload")
    write(copy / "scripts/__pycache__/aclib.cpython-311.pyc", "bytes")
    write(copy / "scripts/stray.pyc", "bytes")
    return copy


@pytest.fixture
def project(tmp_path):
    run("specify", "init", "proj", "--integration", "claude", "--script", "ps", "--non-interactive", cwd=tmp_path)
    root = tmp_path / "proj"
    write(root / "CLAUDE.md", "# Project\n\nHouse rules.\n")
    write(root / "App.slnx", "<Solution />\n")
    git("init", "-q", cwd=root)
    git("add", "-A", cwd=root)
    git("commit", "-qm", "init", cwd=root)
    return root


def installed_skills(root):
    return sorted((root / ".claude/skills").glob("speckit-ac-*/SKILL.md"))


def test_round_trip_fresh_project(project, payload, capsys):
    """(a) + A07: a fresh project comes back byte for byte; no bytecode reaches the install."""
    before = snapshot(project)
    assert deploy.install(project, payload=payload) == 0
    ext = project / deploy.EXT
    assert not [p for p in ext.rglob("*") if p.name == "__pycache__" or p.suffix == ".pyc"]
    assert not (ext / ".extensionignore").exists()
    assert len(installed_skills(project)) == 5
    assert deploy.uninstall(project) == 0
    assert snapshot(project) == before


def test_round_trip_with_existing_settings_and_agent(project, payload):
    """(b): an indent-2 settings.json with another hook and another agent come back byte for byte."""
    write(project / ".claude/settings.json", json.dumps({"hooks": {"PreToolUse": [OTHER_GROUP]}}, indent=2) + "\n")
    write(project / ".claude/agents/reviewer.md", "---\nname: reviewer\n---\n\nReview.\n")
    before = snapshot(project)
    deploy.install(project, payload=payload)
    deploy.uninstall(project)
    assert snapshot(project) == before


def test_clone_upgrade_uninstall(project, payload, tmp_path, capsys):
    """(c) clone with core.symlinks=false gets real patched skills and a passing doctor; (d) upgrade re-patches;
    (e) uninstall leaves no speckit-ac skill, and the project round-trips after the upgrade."""
    before = snapshot(project)
    deploy.install(project, payload=payload)
    git("add", "-A", cwd=project)
    git("commit", "-qm", "install speckit-ac", cwd=project)
    modes = run("git", "ls-files", "-s", "--", ".claude/skills", cwd=project)
    ac_lines = [line for line in modes.splitlines() if "speckit-ac-" in line]
    assert len(ac_lines) == 5 and all(line.startswith("100644 ") for line in ac_lines), modes

    clone = tmp_path / "clone"
    run("git", "-c", "core.symlinks=false", "-c", "core.autocrlf=true", "clone", "-q", str(project), str(clone),
        cwd=tmp_path)
    for skill in installed_skills(clone):
        assert not skill.is_symlink()
        assert deploy.has_skill_flag(skill.read_bytes().decode("utf-8").replace("\r\n", "\n"))
    capsys.readouterr()
    code = deploy.doctor(clone)
    out = capsys.readouterr().out
    assert code == 0, out
    assert "[FAIL]" not in out and out.count("[warn]") == 1 and "no .workflow/config.json yet" in out

    assert deploy.upgrade(project, payload=payload) == 0
    for skill in installed_skills(project):
        assert not skill.is_symlink() and deploy.has_skill_flag(skill.read_text(encoding="utf-8"))
    capsys.readouterr()
    assert deploy.doctor(project) == 0, capsys.readouterr().out

    deploy.uninstall(project)
    assert not installed_skills(project)
    assert snapshot(project) == before


def test_wheel_ships_extensionignore(tmp_path):
    """R03: uv_build puts the payload's dotfile into the wheel."""
    run("uv", "build", "--wheel", "-o", str(tmp_path / "dist"), str(REPO), cwd=tmp_path)
    wheel = next((tmp_path / "dist").glob(f"speckit_ac-{__version__}-*.whl"))
    names = zipfile.ZipFile(wheel).namelist()
    assert "speckit_ac/payload/.extensionignore" in names
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
