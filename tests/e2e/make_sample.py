"""Build the step 7 end-to-end sample: a spec-kit .NET project with speckit-ac installed (spec S07-R04).

Usage (from the spec-kit-ac checkout):
    uv run python tests/e2e/make_sample.py --dest <e2e-sample> [--force] [--cli tool|checkout]

1. Checks the destination: never inside this checkout, never a drive root; an existing non-empty folder only with
   --force, and only if it is a previous sample (has .specify/ or .workflow/); --force deletes only that folder.
2. specify init <dest> --integration claude --script ps --non-interactive, then copies tests/e2e/sample/ over it.
3. git init, commit.
4. --cli tool (default): uv tool install --reinstall --from <this checkout> speckit-ac (in the user's uv tool
   directory; undo with `uv tool uninstall speckit-ac`). --cli checkout: `uv run --project <checkout> speckit-ac`.
5. speckit-ac install, then compares the checkout's payload with the installed extension (stale tool check), commit.
"""
import argparse
import fnmatch
import hashlib
import os
import shutil
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2elib  # noqa: E402
from e2elib import E2EError, say  # noqa: E402


def check_destination(dest: Path, force: bool) -> str:
    """'create' (absent), 'empty' (an empty folder to remove first) or 'replace' (a previous sample, --force)."""
    dest = dest.resolve()
    if dest.parent == dest:
        raise E2EError(f"{dest} is a drive root.")
    repo = e2elib.REPO.resolve()
    if dest == repo or repo in dest.parents:
        raise E2EError(f"{dest} is inside the spec-kit-ac checkout; its CLAUDE.md and .claude/ would reach the "
                       "sample's sessions. Choose a folder outside it.")
    if dest in repo.parents:
        raise E2EError(f"{dest} contains the spec-kit-ac checkout.")
    if not dest.exists():
        return "create"
    if not dest.is_dir():
        raise E2EError(f"{dest} exists and is not a folder.")
    if not any(dest.iterdir()):
        return "empty"
    if not force:
        raise E2EError(f"{dest} is not empty. Pass --force to replace a previous sample.")
    if not ((dest / ".specify").is_dir() or (dest / ".workflow").is_dir()):
        raise E2EError(f"{dest} has no .specify/ or .workflow/, so it is not a previous sample; not deleting it.")
    return "replace"


def _make_writable(func, path, *_):
    os.chmod(path, stat.S_IWRITE)  # read-only files under .git (pack files) on Windows
    func(path)


def remove_tree(path: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable)
    else:
        shutil.rmtree(path, onerror=_make_writable)


def ignore_patterns(payload: Path) -> list[str]:
    file = payload / ".extensionignore"
    if not file.is_file():
        return []
    return [line.strip() for line in file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def ignored(rel: str, patterns: list[str]) -> bool:
    parts = rel.split("/")
    for pattern in patterns:
        if pattern.endswith("/"):
            if pattern.rstrip("/") in parts[:-1]:
                return True
        elif fnmatch.fnmatch(parts[-1], pattern) or fnmatch.fnmatch(rel, pattern):
            return True
    return False


def content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def payload_mismatch(payload: Path, installed: Path):
    """The first payload file whose installed copy is missing or different (CRLF folded), or None.
    spec-kit copies neither .extensionignore nor what it ignores."""
    patterns = ignore_patterns(payload)
    for file in sorted(p for p in payload.rglob("*") if p.is_file()):
        rel = file.relative_to(payload).as_posix()
        if rel == ".extensionignore" or ignored(rel, patterns):
            continue
        copy = installed / rel
        if not copy.is_file():
            return f"{rel} is missing from {installed}"
        if content_hash(copy) != content_hash(file):
            return f"{rel} differs from the checkout's payload"
    return None


def install_cli(mode: str) -> list[str]:
    if mode == "tool":
        say("Installing speckit-ac as a uv tool from this checkout (uv tool install --reinstall) ...")
        e2elib.checked(["uv", "tool", "install", "--reinstall", "--from", str(e2elib.REPO), "speckit-ac"],
                       e2elib.REPO, what="uv tool install")
    return e2elib.cli_command(mode)


def main():
    parser = argparse.ArgumentParser(description="Build the spec-kit-ac end-to-end sample project.")
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument("--force", action="store_true", help="replace a previous sample in --dest")
    parser.add_argument("--cli", choices=("tool", "checkout"), default="tool")
    args = parser.parse_args()
    dest = args.dest.resolve()
    action = check_destination(dest, args.force)
    if action in ("empty", "replace"):
        say(f"Removing {dest} ({'empty folder' if action == 'empty' else 'previous sample'})")
        remove_tree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    e2elib.checked(["specify", "init", dest.name, "--integration", "claude", "--script", "ps", "--non-interactive"],
                   dest.parent, what="specify init")
    shutil.copytree(e2elib.SAMPLE, dest, dirs_exist_ok=True)
    e2elib.git(dest, "init", "-q", "-b", "main")
    e2elib.commit(dest, "e2e: sample")
    say(f"Created {dest} (spec-kit + sample, committed)")

    cli = install_cli(args.cli)
    say(e2elib.checked([*cli, "--version"], dest, what="speckit-ac --version").strip())
    say(e2elib.checked([*cli, "install"], dest, what="speckit-ac install").rstrip())
    problem = payload_mismatch(e2elib.PAYLOAD, dest / e2elib.EXTENSION)
    if problem:
        raise E2EError(f"the installed extension does not match this checkout: {problem}. The uv tool may be stale; "
                       "re-run with a fresh install.")
    e2elib.commit(dest, "e2e: speckit-ac install")
    say("")
    say(f"Done. CLI: {' '.join(cli)}")
    say(f"Next (tests/e2e/RUNBOOK.md, stage 2): open a NEW Claude Code session in {dest}, trust the folder, "
        "and run /speckit-ac-init")


if __name__ == "__main__":
    e2elib.main_wrapper(main)
