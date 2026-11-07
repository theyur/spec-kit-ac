"""Record the AC items the user chose to skip after a translation.

Usage: record_skips.py <translate-run-id> <AC-id> [<AC-id> ...] [--feature …]
Only ids listed in that run's translation-report.md Issues table are accepted, so nothing but ids reaches the file.
Writes specs/NNN-x/ac/runs/<translate-run-id>/skipped.json.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Record the AC items the user chose to skip after a translation.")
    parser.add_argument("run")
    parser.add_argument("ids", nargs="+")
    aclib.add_feature_arg(parser)
    args = parser.parse_args()
    if not re.fullmatch(r"translate-\d{3,}", args.run):
        raise aclib.AcError("the run id must be a translate-NNN run")
    root = aclib.root(__file__)
    feature = aclib.resolve_feature(root, args.feature, aclib.load_config(root))
    run_dir = feature.path(root, "runsDir") / args.run
    report = run_dir / "translation-report.md"
    if not report.is_file():
        raise aclib.AcError(f"{aclib.rel_posix(root, run_dir)}/translation-report.md not found")

    text = report.read_text(encoding="utf-8")
    issues = text.split("## Issues", 1)[1].split("\n## ", 1)[0] if "## Issues" in text else ""
    issue_ids = set(re.findall(r"^\|\s*(AC-\d+)\s*\|", issues, re.MULTILINE))
    unknown = [i for i in args.ids if i not in issue_ids]
    if unknown:
        raise aclib.AcError(f"not in the report's Issues table: {', '.join(unknown)}")

    skipped = sorted(set(args.ids))
    aclib.write_text(run_dir / "skipped.json", json.dumps(skipped) + "\n")
    print(f"Skipped in {feature.dir} ({feature.tag}): {', '.join(skipped)}")


if __name__ == "__main__":
    aclib.run_main(main)
