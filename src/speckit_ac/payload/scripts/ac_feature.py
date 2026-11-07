"""Print the paths of one feature as JSON, for the AC commands' prompt templates.

Usage: ac_feature.py [--feature specs/NNN-name | NNN-name | NNN | FNNN]   (default: .specify/feature.json)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Print the paths of one feature as JSON.")
    aclib.add_feature_arg(parser)
    args = parser.parse_args()
    root = aclib.root(__file__)
    feature = aclib.resolve_feature(root, args.feature, aclib.load_config(root))
    print(json.dumps(feature.paths(), indent=2))


if __name__ == "__main__":
    aclib.run_main(main)
