"""Lock, verify, unlock or re-confirm a feature's group of AC files (docs/WORKFLOW.md §5).

Usage: ac_lock.py lock | verify | unlock | confirm-spec  sources | features  [--feature …]
- sources:  specs/NNN-x/acceptance.md and <ac>/Samples/FNNN/**, plus the hash of specs/NNN-x/spec.md.
- features: <ac>/Features/FNNN/** (the translator's .feature files).
The lock is specs/NNN-x/ac/<group>.lock: the SHA-256 of every file, hashed as the bytes on disk.
Exit codes of verify: 0 match, 1 files differ or not locked, 3 spec drift (only spec.md changed since locking).
confirm-spec (sources only): the user confirmed the AC are still valid after a spec change; re-records the spec hash.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402

SPEC_DRIFT = 3


def group_files(root, feature, group):
    """Project-relative path -> SHA-256 for every file of the group."""
    if group == "sources":
        acceptance = feature.path(root, "acceptance")
        if not acceptance.is_file():
            raise aclib.AcError(f"{feature.paths()['acceptance']} not found")
        files = [acceptance]
        samples = feature.path(root, "samplesDir")
        files += sorted(p for p in samples.rglob("*") if p.is_file()) if samples.is_dir() else []
    else:
        folder = feature.path(root, "featuresDir")
        files = sorted(p for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else []
        if not any(p.suffix == ".feature" for p in files):
            raise aclib.AcError(f"no .feature file in {feature.paths()['featuresDir']}")
    return {aclib.rel_posix(root, p): aclib.sha256(p) for p in files}


def spec_entry(root, feature):
    spec = feature.path(root, "spec")
    return {"path": feature.paths()["spec"], "sha256": aclib.sha256(spec) if spec.is_file() else None}


def lock_key(group):
    return "sourcesLock" if group == "sources" else "featuresLock"


def read_lock(root, feature, group):
    path = feature.path(root, lock_key(group))
    if not path.is_file():
        raise aclib.AcError(f"the {group} of {feature.dir} are not locked (ac_lock.py lock {group}).")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise aclib.AcError(f"{feature.paths()[lock_key(group)]} is not valid JSON") from None
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        raise aclib.AcError(f"{feature.paths()[lock_key(group)]} is not a lock file")
    return data


def write_lock(root, feature, group, files, spec=None):
    data = {"group": group, "feature": feature.dir, "files": files}
    if spec is not None:
        data["spec"] = spec
    aclib.write_text(feature.path(root, lock_key(group)), json.dumps(data, indent=2) + "\n")


def differences(locked, current):
    problems = [f"added: {p}" for p in sorted(current.keys() - locked.keys())]
    problems += [f"removed: {p}" for p in sorted(locked.keys() - current.keys())]
    problems += [f"changed: {p}" for p in sorted(locked.keys() & current.keys()) if locked[p] != current[p]]
    return problems


def current_spec(root, feature):
    spec = spec_entry(root, feature)
    if spec["sha256"] is None:
        raise aclib.AcError(f"{spec['path']} not found")
    return spec


def require_coverage(root, feature):
    """Locking the features needs a scenario for every acceptance item, or the user's skip of it (skipped.json of the
    latest translate run, written by record_skips.py): an item the translator dropped is never locked untested."""
    import check_features  # same folder; imported here so the sources group never needs it
    _, _, ids = check_features.scan(root, feature)
    run = aclib.latest_translation(root, feature)
    skipped = aclib.skipped_ids(run) if run else set()
    open_items = [i for i in check_features.uncovered(root, feature, ids) if i not in skipped]
    if open_items:
        run_id = run.name if run else "<translate-NNN>"
        raise aclib.AcError(f"the features of {feature.dir} have no scenario for {', '.join(open_items)} of "
                            f"{feature.paths()['acceptance']}. Lock only after the user chose to skip them "
                            f"(record_skips.py {run_id} <AC ids>) or fixed acceptance.md and translated again.")


def lock(root, feature, group):
    files = group_files(root, feature, group)
    if group == "features":
        require_coverage(root, feature)
    write_lock(root, feature, group, files, current_spec(root, feature) if group == "sources" else None)
    print(f"Locked {len(files)} {group} file(s) of {feature.dir} ({feature.tag}) in {feature.paths()[lock_key(group)]}")


def verify(root, feature, group):
    locked = read_lock(root, feature, group)
    problems = differences(locked["files"], group_files(root, feature, group))
    if problems:
        raise aclib.AcError(f"locked {group} of {feature.dir} differ from the lock\n  " + "\n  ".join(problems))
    if group == "sources" and spec_entry(root, feature) != locked.get("spec"):
        print(f"SPEC DRIFT: {feature.paths()['spec']} changed after the sources of {feature.dir} were locked. "
              "Ask the user to confirm the AC are still valid (ac_lock.py confirm-spec sources) "
              "or to unlock, edit and re-lock them.", file=sys.stderr)
        sys.exit(SPEC_DRIFT)
    print(f"OK: {len(locked['files'])} locked {group} file(s) of {feature.dir} ({feature.tag}) match")


def unlock(root, feature, group):
    path = feature.path(root, lock_key(group))
    if path.is_file():
        path.unlink()
        print(f"Unlocked {group} of {feature.dir} ({feature.tag})")
    else:
        print(f"No {group} lock to remove for {feature.dir} ({feature.tag})")


def confirm_spec(root, feature, group):
    if group != "sources":
        raise aclib.AcError("confirm-spec applies to sources only")
    locked = read_lock(root, feature, group)
    problems = differences(locked["files"], group_files(root, feature, group))
    if problems:
        raise aclib.AcError(f"locked sources of {feature.dir} differ from the lock; unlock, review and re-lock "
                            "instead\n  " + "\n  ".join(problems))
    spec = current_spec(root, feature)
    write_lock(root, feature, group, locked["files"], spec)
    print(f"Confirmed: the sources of {feature.dir} ({feature.tag}) stay locked against the current {spec['path']}")


COMMANDS = {"lock": lock, "verify": verify, "unlock": unlock, "confirm-spec": confirm_spec}


def main():
    parser = argparse.ArgumentParser(description="Lock, verify or unlock a feature's AC files.")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("group", choices=("sources", "features"))
    aclib.add_feature_arg(parser)
    args = parser.parse_args()
    root = aclib.root(__file__)
    feature = aclib.resolve_feature(root, args.feature, aclib.load_config(root))
    COMMANDS[args.command](root, feature, args.group)


if __name__ == "__main__":
    aclib.run_main(main)
