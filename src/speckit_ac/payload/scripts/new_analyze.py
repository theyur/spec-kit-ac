"""Create the next analyze-K/ folder in the feature's latest run-NNN, mark it as the judge's active run, print it.

Usage: new_analyze.py [--feature …]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Create the next analyze folder of a feature's latest run.")
    aclib.add_feature_arg(parser)
    args = parser.parse_args()
    root = aclib.root(__file__)
    feature = aclib.resolve_feature(root, args.feature, aclib.load_config(root))
    runs = aclib.numbered(feature.path(root, "runsDir"), "run-")
    if not runs:
        raise aclib.AcError(f"no run folder in {feature.paths()['runsDir']}. Run /speckit-ac-tests-write first.")
    analyses = aclib.numbered(runs[-1], "analyze-")
    k = int(analyses[-1].name[len("analyze-"):]) + 1 if analyses else 1
    folder = runs[-1] / f"analyze-{k}"
    folder.mkdir()
    aclib.write_marker(root, aclib.JUDGE, feature, runs[-1].name, folder.name)
    print(aclib.rel_posix(root, folder))
    print(f"feature: {feature.dir} ({feature.tag}); active run: {aclib.JUDGE} {runs[-1].name}/{folder.name}")


if __name__ == "__main__":
    aclib.run_main(main)
