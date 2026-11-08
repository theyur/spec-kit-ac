"""Change the end-to-end sample between the slash commands (spec S07-R05). The only way the runbook changes it.

Usage (from the spec-kit-ac checkout):
    uv run python tests/e2e/stage.py --project <sample> spec 001|002
    uv run python tests/e2e/stage.py --project <sample> implement 001-buggy|001-fixed|002
    uv run python tests/e2e/stage.py --project <sample> fix 001
    uv run python tests/e2e/stage.py --project <sample> commit <label>

spec: writes specs/NNN-name/spec.md (seeded instead of /speckit-specify) and points .specify/feature.json at it.
implement: copies an implementation fixture over src/ and tests/ (instead of /speckit-implement).
fix 001: implement 001-fixed (fallback when the main agent's own fix is not wanted).
commit: commits what the slash commands left (acceptance.md, locks, features, runs, step definitions).
Every action but `commit` refuses a dirty tree, and every action commits, so each stage starts clean.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2elib  # noqa: E402
from e2elib import E2EError, say  # noqa: E402


def write_spec(project: Path, number: str) -> list[str]:
    name = e2elib.SPECS[number]
    target = project / "specs" / name / "spec.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(e2elib.SPEC_SOURCES / name / "spec.md", target)
    feature_json = project / ".specify" / "feature.json"
    feature_json.write_text(json.dumps({"feature_directory": f"specs/{name}"}), encoding="utf-8")
    return [f"specs/{name}/spec.md", ".specify/feature.json"]


def copy_fixture(project: Path, fixture: str) -> list[str]:
    source = e2elib.FIXTURES / fixture
    written = []
    for file in sorted(p for p in source.rglob("*") if p.is_file()):
        rel = file.relative_to(source)
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
        written.append(rel.as_posix())
    return written


def apply(project: Path, action: str, arg: str) -> list[str]:
    """Run one action; returns the files written (empty for `commit`)."""
    project = e2elib.require_project(project)
    if action == "commit":
        if e2elib.commit(project, f"e2e: after {arg}"):
            say(f"Committed: e2e: after {arg}")
        else:
            say("Nothing to commit.")
        return []
    pending = e2elib.dirty(project)
    if pending:
        raise E2EError("the sample has uncommitted changes; commit them first (stage.py commit <label>):\n  "
                       + "\n  ".join(pending[:20]))
    if action == "spec":
        written, message = write_spec(project, arg), f"e2e: spec {arg}"
    elif action == "implement":
        written, message = copy_fixture(project, arg), f"e2e: implement {arg}"
    else:  # fix 001
        written, message = copy_fixture(project, "001-fixed"), "e2e: fix 001 (fallback)"
    for rel in written:
        say(f"wrote {rel}")
    if not e2elib.commit(project, message):
        say("(no change: the files were already like this)")
    else:
        say(f"Committed: {message}")
    return written


CHOICES = {"spec": tuple(e2elib.SPECS), "implement": e2elib.FIXTURE_NAMES, "fix": ("001",)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Change the end-to-end sample between slash commands.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("action", choices=("spec", "implement", "fix", "commit"))
    parser.add_argument("arg", help="001|002 (spec), 001-buggy|001-fixed|002 (implement), 001 (fix), a label (commit)")
    args = parser.parse_args(argv)
    if args.action in CHOICES and args.arg not in CHOICES[args.action]:
        parser.error(f"{args.action} takes one of: {', '.join(CHOICES[args.action])}")
    if args.action == "commit" and not args.arg.strip():
        parser.error("commit needs a label")
    apply(args.project, args.action, args.arg)


if __name__ == "__main__":
    e2elib.main_wrapper(main)
