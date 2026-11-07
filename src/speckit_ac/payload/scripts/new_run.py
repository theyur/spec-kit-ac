"""Create the next run folder of a feature, mark it as the active run, print its path.

Usage: new_run.py translate [--feature …]   -> specs/NNN-x/ac/runs/translate-NNN/  (role ac-feature-translator)
       new_run.py write     [--feature …]   -> specs/NNN-x/ac/runs/run-NNN/        (role ac-test-writer)
For a write run: if the newest analyze-* folder of the previous run has writer-feedback.md, it is copied to
input-feedback.md. The active-run marker (.workflow/active-run.json) tells the guard which feature and run the
next subagent works on.
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Create the next run folder of a feature.")
    parser.add_argument("kind", choices=("translate", "write"))
    aclib.add_feature_arg(parser)
    args = parser.parse_args()
    root = aclib.root(__file__)
    feature = aclib.resolve_feature(root, args.feature, aclib.load_config(root))
    prefix, role = ("translate-", aclib.TRANSLATOR) if args.kind == "translate" else ("run-", aclib.WRITER)

    runs_dir = feature.path(root, "runsDir")
    runs_dir.mkdir(parents=True, exist_ok=True)
    runs = aclib.numbered(runs_dir, prefix)
    n = int(runs[-1].name[len(prefix):]) + 1 if runs else 1
    new_run = runs_dir / f"{prefix}{n:03d}"
    new_run.mkdir()

    if prefix == "run-" and runs:
        analyses = aclib.numbered(runs[-1], "analyze-")
        if analyses and (analyses[-1] / "writer-feedback.md").is_file():
            shutil.copyfile(analyses[-1] / "writer-feedback.md", new_run / "input-feedback.md")

    aclib.write_marker(root, role, feature, new_run.name)
    print(aclib.rel_posix(root, new_run))
    print(f"feature: {feature.dir} ({feature.tag}); active run: {role} {new_run.name}")


if __name__ == "__main__":
    aclib.run_main(main)
