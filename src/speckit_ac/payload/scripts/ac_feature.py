"""Print the paths of one feature as JSON, for the AC commands' prompt templates.

Usage: ac_feature.py [--feature specs/NNN-name | NNN-name | NNN | FNNN]   (default: .specify/feature.json)
       ac_feature.py --all     every feature folder with its tag: [{"featureDir": ..., "tag": ...}, ...]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Print the paths of one feature, or every feature, as JSON.")
    group = parser.add_mutually_exclusive_group()
    aclib.add_feature_arg(group)
    group.add_argument("--all", action="store_true", help="list every feature folder with its tag")
    args = parser.parse_args()
    root = aclib.root(__file__)
    cfg = aclib.load_config(root)
    if args.all:
        listing = [{"featureDir": f.dir, "tag": f.tag} for f in aclib.all_features(root, cfg)]
        print(json.dumps(listing, indent=2))
        return
    feature = aclib.resolve_feature(root, args.feature, cfg)
    print(json.dumps(feature.paths(), indent=2))


if __name__ == "__main__":
    aclib.run_main(main)
