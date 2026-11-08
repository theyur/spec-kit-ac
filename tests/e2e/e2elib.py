"""Shared helpers for the step 7 end-to-end tooling (make_sample.py, stage.py, check_stage.py).

Run the tools from the spec-kit-ac checkout: `uv run python tests/e2e/<tool>.py ...`. Standard library only.
Output is ASCII (the Windows console code page cannot print everything).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

E2E = Path(__file__).resolve().parent
REPO = E2E.parents[1]
PAYLOAD = REPO / "src" / "speckit_ac" / "payload"
SAMPLE = E2E / "sample"
SPEC_SOURCES = E2E / "specs"
FIXTURES = E2E / "fixtures"
SPECS = {"001": "001-order-discount", "002": "002-raise-discount-threshold"}
FIXTURE_NAMES = ("001-buggy", "001-fixed", "002")
EXTENSION = ".specify/extensions/ac"
CONFIG = ".workflow/config.json"
# A fixed identity and no signing, so commits in the sample never depend on the user's git config.
GIT_IDENTITY = ["-c", "user.name=speckit-ac e2e", "-c", "user.email=e2e@localhost", "-c", "commit.gpgsign=false"]


class E2EError(Exception):
    """A refusal or a failed step; main() prints it and exits 1."""


def say(text: str = "") -> None:
    print(str(text).encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def run(args, cwd, timeout=1800):
    """Run a command; return (exit code, stdout + stderr). A missing program gives (None, message)."""
    args = [str(a) for a in args]
    exe = shutil.which(args[0]) or args[0]
    env = dict(os.environ, PYTHONUTF8="1")
    try:
        result = subprocess.run([exe, *args[1:]], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"{args[0]}: {error}"
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def checked(args, cwd, what=None, timeout=1800) -> str:
    code, out = run(args, cwd, timeout)
    if code != 0:
        raise E2EError(f"{what or ' '.join(map(str, args))} failed (exit {code}):\n{out[-3000:]}")
    return out


def git(project: Path, *args) -> str:
    return checked(["git", *args], project, what=f"git {' '.join(args)}")


def dirty(project: Path) -> list[str]:
    """`git status --porcelain` lines (untracked files included, ignored files not)."""
    return [line for line in git(project, "status", "--porcelain", "--untracked-files=all").splitlines() if line]


def changed_paths(project: Path) -> list[str]:
    """Paths changed since HEAD, untracked included (posix, project-relative)."""
    out = checked(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], project, what="git status")
    paths, entries, i = [], out.split("\0"), 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) > 3:
            paths.append(entry[3:])
            if entry[0] in "RC":  # a rename / copy is followed by its source path
                i += 1
        i += 1
    return paths


def commit(project: Path, message: str) -> bool:
    """Stage everything and commit; False when there was nothing to commit."""
    git(project, "add", "-A")
    if not dirty(project):
        return False
    git(project, *GIT_IDENTITY, "commit", "-q", "-m", message)
    return True


def require_project(project: Path) -> Path:
    project = project.resolve()
    if not (project / ".specify").is_dir() or not (project / ".git").exists():
        raise E2EError(f"{project} is not an e2e sample (needs .specify/ and .git). Run make_sample.py first.")
    return project


def load_config(project: Path) -> dict:
    path = project / CONFIG
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise E2EError(f"{CONFIG} is missing or not valid JSON ({error}). Run /speckit-ac-init first.") from None


def python_cmd(cfg: dict) -> list[str]:
    """The config's `python` command, split (e.g. `uv run --no-project python -I`)."""
    return str(cfg.get("python") or "").split()


def feature_dir(project: Path, number: str) -> Path:
    path = project / "specs" / SPECS[number]
    if not path.is_dir():
        raise E2EError(f"specs/{SPECS[number]} does not exist. Run stage.py spec {number} first.")
    return path


def cli_command(mode: str) -> list[str]:
    """How to start the speckit-ac CLI: the installed uv tool, or `uv run` from this checkout."""
    if mode == "checkout":
        return ["uv", "run", "--project", str(REPO), "speckit-ac"]
    # The uv tool's own executable, never a PATH lookup: under `uv run` the checkout's .venv/Scripts comes first on
    # PATH and holds the editable dev entry point (found in the first live stage 1, 2026-11-08).
    code, out = run(["uv", "tool", "dir", "--bin"], REPO)
    exe = tool_executable(Path(out.strip().splitlines()[-1])) if code == 0 and out.strip() else None
    if exe is None:
        raise E2EError("speckit-ac is not installed as a uv tool (run make_sample.py, or pass --cli checkout).")
    return [str(exe)]


def tool_executable(bin_dir: Path):
    for name in ("speckit-ac.exe", "speckit-ac"):
        if (bin_dir / name).is_file():
            return bin_dir / name
    return None


def main_wrapper(main) -> None:
    try:
        main()
    except E2EError as error:
        say(f"ERROR: {error}")
        sys.exit(1)
