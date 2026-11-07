"""Temp projects laid out as `speckit-ac install` + `/speckit-ac-init` would leave them, for guard and script tests."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAYLOAD = REPO / "src" / "speckit_ac" / "payload"
EXTENSION = Path(".specify/extensions/ac")
AC = "tests/App.AcceptanceTests"
BUILD = f"dotnet build {AC}/App.AcceptanceTests.csproj -p:AcRefMode=true -nologo -v q"
CONFIG = {
    "schemaVersion": 1,
    "python": "uv run --no-project python -I",
    "solution": "App.slnx",
    "specInputs": ["docs/domain"],
    "acSurfaceProjects": ["src/App.Core/App.Core.csproj"],
    "unitTestProjects": ["tests/App.Tests/App.Tests.csproj"],
    "acProjectDir": AC,
    "acProject": f"{AC}/App.AcceptanceTests.csproj",
    "refsDir": "artifacts/refs",
    "acRefBuildCommand": BUILD,
    "unitTestCommand": "dotnet test --project {project}",
    "acTestCommand": "dotnet test --project {acProject} --no-build --results-directory {analyzeDir}",
}
FEATURES = ("001-alpha", "002-beta")


# Feature folders for R05, shared by the script tests (ac_feature.py --feature) and the guard tests (marker), so the
# two implementations cannot drift: (id, folder, extra setup, valid?)
FEATURE_FOLDERS = [
    ("sequential", "specs/001-alpha", None, True),
    ("four digits", "specs/0001-delta", "specs/0001-delta", True),
    ("two digits", "specs/01-x", "specs/01-x", False),
    ("timestamp folder", "specs/20260319-143022-login", "specs/20260319-143022-login", False),
    ("nested", "specs/scope/001-x", "specs/scope/001-x", False),
    ("duplicate number", "specs/001-alpha", "specs/001-other", False),
    ("dot-dot", "specs/001-alpha/../002-beta", None, False),
    ("timestamp numbering", "specs/001-alpha", "timestamp-numbering", False),
]


def feature_setup(project: Path, setup):
    """Apply a FEATURE_FOLDERS setup: create a feature folder, or switch spec-kit to timestamp numbering."""
    if setup == "timestamp-numbering":
        write(project / ".specify/init-options.json", json.dumps({"feature_numbering": "timestamp"}) + "\n")
    elif setup:
        write(project / setup / "spec.md")


def feature_tag(folder: str) -> str:
    name = folder.rstrip("/").split("/")[-1]
    return "F" + name.split("-")[0]


def write(path: Path, text: str = "x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_project(base: Path, config=CONFIG, features=FEATURES, current="specs/001-alpha") -> Path:
    """A project with the payload installed. `config`: dict, raw str (written as is) or None (no config file)."""
    base.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PAYLOAD, base / EXTENSION, ignore=shutil.ignore_patterns("__pycache__"))
    write(base / ".specify/memory/constitution.md", "# Constitution\n")
    if current is not None:
        write(base / ".specify/feature.json", json.dumps({"feature_directory": current}) + "\n")
    for name in features:
        for doc in ("spec.md", "acceptance.md", "plan.md", "tasks.md"):
            write(base / "specs" / name / doc, f"# {name} {doc}\n")
    if isinstance(config, dict):
        write(base / ".workflow/config.json", json.dumps(config, indent=2) + "\n")
    elif isinstance(config, str):
        write(base / ".workflow/config.json", config)
    write(base / "docs/domain/overview.md")
    write(base / f"{AC}/App.AcceptanceTests.csproj", "<Project />\n")
    for folder in ("Features", "Samples", "StepDefinitions", "Support"):
        for tag in ("F001", "F002"):
            write(base / AC / folder / tag / ".gitkeep", "")
    write(base / AC / "Support/Shared/.gitkeep", "")
    return base


def run_script(project: Path, name: str, *args: str) -> subprocess.CompletedProcess:
    """Run an installed script the way the commands do: `<python> -I .specify/extensions/ac/scripts/<name>`."""
    script = project / EXTENSION / "scripts" / name
    return subprocess.run([sys.executable, "-I", str(script), *args], cwd=project, capture_output=True, text=True,
                          encoding="utf-8")


def run_guard(project: Path, payload, project_dir="project", guard: Path | None = None) -> tuple[int, str]:
    """Run the installed guard with a hook payload (dict, or raw text) the way Claude Code does.

    `project_dir`: CLAUDE_PROJECT_DIR (default: the project; None: unset). `guard`: another guard file to run.
    """
    text = payload if isinstance(payload, str) else json.dumps(payload)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project if project_dir == "project" else project_dir)
    guard = guard or project / EXTENSION / "hooks" / "guard.py"
    result = subprocess.run([sys.executable, "-I", str(guard)], input=text,
                            capture_output=True, text=True, encoding="utf-8", env=env)
    return result.returncode, result.stderr.strip()
