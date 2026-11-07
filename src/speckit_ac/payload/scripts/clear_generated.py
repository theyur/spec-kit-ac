"""Delete one feature's generated files in the AC project, keeping .gitkeep.

Usage: clear_generated.py features [--feature …]   -> Features/FNNN/ (before the translator writes them again)
       clear_generated.py steps    [--feature …]   -> StepDefinitions/FNNN/ and Support/FNNN/ (tests-write fresh)
Support/Shared/ and other features are never touched. A script, because the guard blocks main-agent tool calls that
name StepDefinitions/ or Support/. It never prints file contents.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402

FOLDERS = {"features": ["featuresDir"], "steps": ["stepDefinitionsDir", "supportDir"]}


def main():
    parser = argparse.ArgumentParser(description="Delete one feature's generated files in the AC project.")
    parser.add_argument("kind", choices=FOLDERS)
    aclib.add_feature_arg(parser)
    args = parser.parse_args()
    root = aclib.root(__file__)
    feature = aclib.resolve_feature(root, args.feature, aclib.load_config(root))
    if args.kind == "features" and feature.path(root, "featuresLock").is_file():
        raise aclib.AcError(f"the features of {feature.dir} are locked. Unlock them only when the user asks "
                            "(ac_lock.py unlock features).")
    removed = 0
    for key in FOLDERS[args.kind]:
        for f in sorted(feature.path(root, key).rglob("*"), reverse=True):
            if f.is_file() and f.name != ".gitkeep":
                f.unlink()
                removed += 1
            elif f.is_dir() and not any(f.iterdir()):
                f.rmdir()
    names = ", ".join(feature.paths()[key] + "/" for key in FOLDERS[args.kind])
    print(f"Removed {removed} file(s) of {feature.dir} ({feature.tag}) from {names}")


if __name__ == "__main__":
    aclib.run_main(main)
