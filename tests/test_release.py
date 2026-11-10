"""Release files (step 9): the release helper, the three workflows, the changelog and the README pin.

Stdlib only: the workflows are checked as text (full-line comments stripped first), not parsed as YAML.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"


def load_helper():
    spec = importlib.util.spec_from_file_location("release_check", REPO / "tools" / "release_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rc = load_helper()


def code(path: Path) -> str:
    """The file without full-line comments, so a comment can't satisfy a check."""
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def block(text: str, key: str) -> list[str]:
    """The indented lines under a top-level `key:` line."""
    lines = text.splitlines()
    start = lines.index(f"{key}:")
    out = []
    for line in lines[start + 1:]:
        if line and not line.startswith(" "):
            break
        if line.strip():
            out.append(line.strip())
    return out


def permissions(text: str) -> dict[str, str]:
    return dict(line.split(": ", 1) for line in block(text, "permissions"))


def package_version() -> str:
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def is_final(version: str) -> bool:
    return bool(rc.FINAL.fullmatch(version))


# --- the helper, on a temporary project ---------------------------------------------------------------

CHANGELOG = """# Changelog

## [Unreleased]

- next thing

## [0.2.0] - 2026-12-01

### Added

- second release

## [0.1.0] - 2026-11-10

- first release

## [0.0.9]

[0.2.0]: https://example.invalid/v0.2.0
[0.1.0]: https://example.invalid/v0.1.0
"""


def project(tmp_path: Path, version: str = "0.2.0", manifest: str | None = None, changelog: str = CHANGELOG) -> Path:
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8")
    payload = tmp_path / "src" / "speckit_ac" / "payload"
    payload.mkdir(parents=True)
    (payload / "extension.yml").write_text(
        f'schema_version: "1.0"\nextension:\n  id: ac\n  version: "{manifest or version}"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tmp_path


def test_check_accepts_a_matching_tag(tmp_path):
    assert rc.check("v0.2.0", project(tmp_path)) == "0.2.0"


@pytest.mark.parametrize("tag", ["v0.2.1", "0.2.0", "v0.2.0-rc1", "refs/tags/v0.2.0"])
def test_check_refuses_another_tag(tmp_path, tag):
    with pytest.raises(rc.ReleaseError, match="does not match"):
        rc.check(tag, project(tmp_path))


def test_check_refuses_a_manifest_mismatch(tmp_path):
    with pytest.raises(rc.ReleaseError, match="extension.yml says 0.1.9"):
        rc.check("v0.2.0", project(tmp_path, manifest="0.1.9"))


@pytest.mark.parametrize("version", [
    "0.2.0.dev0", "0.2.0rc1", "0.2.0b2", "0.2.0a1",           # canonical pre-release and dev spellings
    "0.2.0RC1", "0.2.0-rc1", "0.2.0c1", "0.2.0.pre1", "0.2.0alpha1", "0.2.0-beta.2", "0.2.0preview3",  # PEP 440 aliases
    "0.2.0.dev0+local", "0.2.0+local", "0.2.0.post1",       # local and post versions
    "0.2", "0.2.0.0", "v0.2.0", " 0.2.0",                   # not X.Y.Z
])
def test_check_refuses_anything_but_a_final_version(tmp_path, version):
    with pytest.raises(rc.ReleaseError, match="not a final X.Y.Z version"):
        rc.check(f"v{version}", project(tmp_path, version=version))


def test_check_refuses_a_manifest_without_a_version(tmp_path):
    root = project(tmp_path)
    (root / "src" / "speckit_ac" / "payload" / "extension.yml").write_text("extension:\n  id: ac\n", encoding="utf-8")
    with pytest.raises(rc.ReleaseError, match="no extension version"):
        rc.check("v0.2.0", root)


def test_notes_returns_the_section_without_link_definitions(tmp_path):
    root = project(tmp_path)
    assert rc.notes("0.2.0", root) == "### Added\n\n- second release\n"
    assert rc.notes("0.1.0", root) == "- first release\n"


@pytest.mark.parametrize("version, message", [("0.3.0", "no section"), ("Unreleased", "no release date"),
                                              ("0.0.9", "no release date")])
def test_notes_refuses_a_missing_or_undated_section(tmp_path, version, message):
    with pytest.raises(rc.ReleaseError, match=message):
        rc.notes(version, project(tmp_path))


def test_notes_refuses_an_empty_section(tmp_path):
    root = project(tmp_path, changelog="# Changelog\n\n## [0.2.0] - 2026-12-01\n\n## [0.1.0] - 2026-11-10\n\n- x\n")
    with pytest.raises(rc.ReleaseError, match="empty"):
        rc.notes("0.2.0", root)


def test_latest_is_the_newest_dated_section(tmp_path):
    assert rc.latest(project(tmp_path)) == "0.2.0"
    with pytest.raises(rc.ReleaseError, match="no released"):
        other = tmp_path / "other"
        other.mkdir()
        rc.latest(project(other, changelog="# Changelog\n\n## [Unreleased]\n\n- x\n"))


def test_main_exit_codes_and_outputs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rc, "ROOT", project(tmp_path))
    assert rc.main(["check", "v0.2.0"]) == 0
    assert rc.main(["check", "v9.9.9"]) == 1
    assert "does not match" in capsys.readouterr().err
    out = tmp_path / "notes.md"
    assert rc.main(["notes", "0.1.0", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == "- first release\n"
    assert rc.main(["latest"]) == 0
    assert capsys.readouterr().out.strip() == "0.2.0"
    assert rc.main([]) == 1
    assert rc.main(["notes", "0.3.0", str(out)]) == 1


# --- the real changelog and README ------------------------------------------------------------------


def test_changelog_has_the_newest_release_and_its_notes():
    latest = rc.latest()
    assert rc.notes(latest).strip()
    version = package_version()
    if is_final(version):
        assert latest == version
        assert rc.check(f"v{version}") == version


def test_readme_pins_the_newest_release():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert f"uv tool install speckit-ac --from git+https://github.com/theyur/spec-kit-ac@v{rc.latest()}" in readme
    assert "<owner>" not in readme


# --- workflows -------------------------------------------------------------------------------------------


def test_every_action_is_pinned_and_permissions_are_top_level():
    files = sorted(WORKFLOWS.glob("*.yml"))
    assert [f.name for f in files] == ["ci.yml", "release.yml", "sonar.yml"]
    for path in files:
        text = code(path)
        uses = re.findall(r"^\s*(?:-\s+)?uses:\s*(\S+)\s*$", text, re.MULTILINE)
        assert uses, path.name
        for ref in uses:
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@v\d+(\.\d+\.\d+)?", ref), f"{path.name}: {ref}"
        assert text.count("permissions:") == 1, f"{path.name}: permissions must be declared once, at the top"
        assert "\npermissions:\n" in text, path.name
        assert "write-all" not in text and "read-all" not in text


def test_ci_workflow():
    text = code(WORKFLOWS / "ci.yml")
    assert block(text, "on") == ["push:", "branches: [master]", "pull_request:", "workflow_dispatch:"]
    assert permissions(text) == {"contents": "read"}
    assert block(text, "concurrency") == ["group: ci-${{ github.ref }}", "cancel-in-progress: true"]
    assert "name: test (${{ matrix.python }})" in text
    assert "runs-on: windows-latest" in text
    assert 'python: ["3.11", "3.14"]' in text
    assert "fail-fast: false" in text
    assert "python-version: ${{ matrix.python }}" in text
    assert "run: uv sync --locked" in text
    assert "run: uv run pytest -q --tb=short" in text


def test_sonar_workflow_and_properties():
    text = code(WORKFLOWS / "sonar.yml")
    assert block(text, "on") == ["push:", "branches: [master]", "pull_request:",
                                 "types: [opened, synchronize, reopened]", "workflow_dispatch:"]
    assert permissions(text) == {"contents": "read", "pull-requests": "read"}
    assert "write" not in text
    assert 'if [ -z "$SONAR_TOKEN" ]; then' in text
    assert "SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}" in text
    assert "fetch-depth: 0" in text
    assert "uv run --with coverage coverage run -m pytest -q --tb=short" in text
    assert "uv run --with coverage coverage xml -o coverage.xml" in text
    assert "uses: SonarSource/sonarqube-scan-action@v8" in text
    # Overrides are passed only when the repository variable is set; the defaults stay in the properties file.
    assert "vars.SONAR_ORGANIZATION && format('-Dsonar.organization={0}', vars.SONAR_ORGANIZATION) || ''" in text
    assert "vars.SONAR_PROJECT_KEY && format('-Dsonar.projectKey={0}', vars.SONAR_PROJECT_KEY) || ''" in text

    props = dict(line.split("=", 1) for line in code(REPO / "sonar-project.properties").splitlines() if "=" in line)
    assert props == {
        "sonar.organization": "theyur", "sonar.projectKey": "theyur_spec-kit-ac",
        "sonar.host.url": "https://sonarcloud.io", "sonar.sources": "src,tools", "sonar.tests": "tests",
        "sonar.python.version": "3.11", "sonar.python.coverage.reportPaths": "coverage.xml",
        "sonar.qualitygate.wait": "true",
    }
    coverage = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["coverage"]["run"]
    assert coverage == {"source": ["src", "tools"], "relative_files": True}


def test_release_workflow_publishes_last():
    text = code(WORKFLOWS / "release.yml")
    assert block(text, "on") == ["push:", 'tags: ["v*"]']
    assert permissions(text) == {"contents": "write"}
    assert "continue-on-error" not in text
    assert not re.search(r"^\s*if:", text, re.MULTILINE)
    assert 'python-version: "3.14"' in text and "enable-cache: false" in text
    order = ["fetch-depth: 0", 'git merge-base --is-ancestor "$GITHUB_SHA" origin/master',
             "run: uv sync --locked", 'release_check.py check "$GITHUB_REF_NAME"', "run: uv run pytest -q --tb=short",
             "run: uv build", 'release_check.py notes "${GITHUB_REF_NAME#v}" release-notes.md',
             'gh release create "$GITHUB_REF_NAME" dist/*.whl dist/*.tar.gz']
    positions = [text.find(step) for step in order]
    assert -1 not in positions, dict(zip(order, positions))
    assert positions == sorted(positions)
    tail = text[positions[-1]:]
    assert "- name:" not in tail and "- uses:" not in tail, "publishing must be the last step"
    assert "--notes-file release-notes.md --verify-tag" in tail
    assert "GH_TOKEN: ${{ github.token }}" in text


def on_master_script() -> str:
    """The `run:` body of the release workflow's "Check the tag is on master" step."""
    text = code(WORKFLOWS / "release.yml")
    step = text[text.index("- name: Check the tag is on master"):]
    body = step[step.index("run: |") + len("run: |"):].splitlines()[1:]
    lines = []
    for line in body:
        if line.strip().startswith("- name:") or line.strip().startswith("- uses:"):
            break
        lines.append(line[10:] if line.startswith(" " * 10) else line.strip())
    return "\n".join(lines).strip() + "\n"


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None, reason="needs bash and git")
def test_release_refuses_a_tag_that_is_not_on_master(tmp_path):
    """The on-master step, run as the workflow runs it: a commit of master passes, a side-branch commit fails."""
    origin, clone = tmp_path / "origin", tmp_path / "clone"
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]

    def git(cwd, *args):
        return subprocess.run(["git", *identity, *args], cwd=cwd, check=True, capture_output=True,
                              text=True).stdout.strip()

    origin.mkdir()
    git(origin, "init", "-q", "-b", "master")
    git(origin, "commit", "-q", "--allow-empty", "-m", "on master")
    on_master = git(origin, "rev-parse", "HEAD")
    git(origin, "switch", "-q", "-c", "side")
    git(origin, "commit", "-q", "--allow-empty", "-m", "not reviewed")
    side = git(origin, "rev-parse", "HEAD")
    git(origin, "switch", "-q", "master")
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    script = tmp_path / "step.sh"
    script.write_text(on_master_script(), encoding="utf-8", newline="\n")

    def step(sha):
        env = {**os.environ, "GITHUB_SHA": sha, "GITHUB_REF_NAME": "v0.1.0"}
        # The full path: on Windows a bare "bash" resolves to the WSL launcher in System32 before PATH.
        return subprocess.run([shutil.which("bash"), str(script)], cwd=clone, env=env, capture_output=True, text=True)

    assert step(on_master).returncode == 0
    refused = step(side)
    assert refused.returncode == 1
    assert "is not on master" in refused.stdout
