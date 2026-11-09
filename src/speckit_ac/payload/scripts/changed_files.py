"""Detect files an AC subagent changed outside its write allowlist (docs/WORKFLOW.md §3).

Usage: changed_files.py snapshot | check <ac-feature-translator|ac-test-writer|ac-test-fail-judge> | clear
`clear` ends a run that stopped before its subagent started (for example /speckit-ac-tests-analyze when every test
passed): it deletes the active-run marker, so no AC subagent can start with that run's task message. A smoke-test marker
is left alone.
Content hashes, not `git status`: git status can't see a second change to an already-modified file, or writes to
ignored paths. The snapshot is kept in the git directory, so it is not part of the working tree it describes.
The allowlist comes from the active-run marker (.workflow/active-run.json), the same rules the guard enforces.
Required order: new_run.py / new_analyze.py (writes the marker, copies input-feedback.md) -> task_message.py (adds
the task message to the marker) -> snapshot -> subagent -> check. A snapshot taken earlier would report those files as
changes. `check` deletes the marker once it has compared the files, whatever the result; a usage error before that
(no snapshot, a marker for another role) keeps it.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402

# Build output folders (bin, obj, obj-ref, bin_x, …) and .git; not folders that merely start with "bin" (Bindings/).
SKIPPED_SEGMENT = re.compile(r"^(\.git|bin|obj)([-_.].*)?$", re.IGNORECASE)
SKIPPED_FILES = {".workflow/guard.log"}  # written by the guard itself during the subagent run


def git(root, *args):
    try:
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise aclib.AcError(f"git {' '.join(args)} failed: {error}") from None


def snapshot_file(root):
    return Path(git(root, "rev-parse", "--absolute-git-dir").decode().strip()) / "ac-changed-files-snapshot.json"


def tree_hashes(root, cfg):
    paths = {p for p in git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")
             if p}
    # Ignored or generated folders a subagent might write to.
    extra = [root / ".workflow", root / cfg["refsDir"]]
    extra += [d / "ac" for d in sorted((root / "specs").glob("*"))] if (root / "specs").is_dir() else []
    for folder in extra:
        if folder.is_dir():
            paths |= {aclib.rel_posix(root, f) for f in folder.rglob("*") if f.is_file()}
    hashes = {}
    for p in sorted(paths):
        f = root / p
        if f.is_file() and p not in SKIPPED_FILES and not any(SKIPPED_SEGMENT.match(s) for s in Path(p).parts[:-1]):
            hashes[p] = aclib.sha256(f)
    return hashes


def check(root, cfg, role):
    snap = snapshot_file(root)
    if not snap.is_file():
        raise aclib.AcError("no snapshot. Run changed_files.py snapshot before the subagent.")
    marker = aclib.read_marker(root)
    if marker["role"] != role:
        raise aclib.AcError(f"the active run is for {marker['role']}, not {role}.")
    try:
        before, after = json.loads(snap.read_text(encoding="utf-8")), tree_hashes(root, cfg)
        changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
        breaches = [p for p in changed if not aclib.may_change(p, marker, cfg)]
        for p in changed:
            state = "added" if p not in before else "removed" if p not in after else "changed"
            print(f"{state}: {p}" + ("   <-- OUTSIDE ALLOWLIST" if p in breaches else ""))
        if not changed:
            print("No files changed")
        if breaches:
            raise aclib.AcError(f"isolation breach, {len(breaches)} file(s) outside the {role} allowlist")
    finally:
        # The run is over: without a marker no AC subagent can start or act until the next run script.
        (root / aclib.MARKER).unlink(missing_ok=True)


def clear(root: Path):
    """End a run whose subagent was never started: delete the marker (a smoke-test marker belongs to smoke_test.py)."""
    path = root / aclib.MARKER
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("No active run")
        return
    except (OSError, ValueError):
        marker = None
    if isinstance(marker, dict) and marker.get("smoke"):
        raise aclib.AcError(f"{aclib.MARKER} is a smoke-test marker; smoke_test.py end removes it.")
    path.unlink(missing_ok=True)
    print(f"Active run ended ({aclib.MARKER} deleted)")


def main():
    usage = f"Usage: changed_files.py snapshot | check <{'|'.join(aclib.ROLES)}> | clear"
    root = aclib.root(__file__)
    if sys.argv[1:] == ["clear"]:
        clear(root)
    elif sys.argv[1:] == ["snapshot"]:
        cfg = aclib.load_config(root)
        hashes = tree_hashes(root, cfg)
        snapshot_file(root).write_text(json.dumps(hashes), encoding="utf-8")
        print(f"Snapshot of {len(hashes)} file(s)")
    elif len(sys.argv) == 3 and sys.argv[1] == "check" and sys.argv[2] in aclib.ROLES:
        check(root, aclib.load_config(root), sys.argv[2])
    else:
        raise aclib.AcError(usage)


if __name__ == "__main__":
    aclib.run_main(main)
