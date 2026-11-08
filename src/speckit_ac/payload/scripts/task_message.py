"""Print the exact task message for the AC subagent of the active run, and record it in the marker.

Usage: task_message.py [--feature …]
The message is the agent's `## Your task message` template (.specify/extensions/ac/agents/<role>.md, the installed
payload copy), filled deterministically: a placeholder <UPPER_SNAKE> is the camelCase key of the feature's paths
(ac_feature.py), else of .workflow/config.json (lists joined with ", "); RUN_ID / ANALYZE_ID come from the marker,
FEATURE_LIST lists every feature folder. The command passes the output to the Agent tool unchanged; the guard
compares the launch prompt with the `taskMessage` stored here. Run it right after new_run.py / new_analyze.py and
before changed_files.py snapshot.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402

PLACEHOLDER = re.compile(r"<([A-Z_]+)>")


def main():
    parser = argparse.ArgumentParser(description="Print the task message of the active AC run.")
    aclib.add_feature_arg(parser)
    args = parser.parse_args()
    root = aclib.root(__file__)
    cfg = aclib.load_config(root)
    feature = aclib.resolve_feature(root, args.feature, cfg)
    marker = aclib.read_marker(root)
    if marker.get("feature") != feature.dir:
        raise aclib.AcError(f"the active run is for {marker.get('feature')}, not {feature.dir}. "
                            "Start the run for this feature first.")
    role = marker["role"]
    agent = Path(__file__).resolve().parent.parent / "agents" / f"{role}.md"
    if not agent.is_file():
        raise aclib.AcError(f"agent file {aclib.rel_posix(root, agent)} not found. Reinstall the extension.")
    paths = feature.paths()
    run_dir = root / paths["runsDir"] / marker["run"]
    optional = {
        "Other spec inputs": bool(cfg["specInputs"]),
        "Feedback to address": (run_dir / "input-feedback.md").is_file(),
    }

    def value(name):
        if name == "RUN_ID":
            return marker["run"]
        if name == "ANALYZE_ID":
            if not marker.get("analyze"):
                raise aclib.AcError(f"{aclib.MARKER} has no analyze id")
            return marker["analyze"]
        if name == "FEATURE_LIST":  # only the judge's template uses it; all_features fails on stray folders
            return ", ".join(f"{f.dir} ({f.tag})" for f in aclib.all_features(root, cfg))
        key = aclib.camel(name)
        found = paths[key] if key in paths else cfg.get(key)
        if found is None:
            raise aclib.AcError(f"{aclib.rel_posix(root, agent)}: unknown placeholder <{name}>")
        return ", ".join(found) if isinstance(found, list) else str(found)

    lines = []
    for label, raw in aclib.template_lines(agent):
        if optional.get(label, True):
            lines.append(f"{label}: {PLACEHOLDER.sub(lambda m: value(m[1]), raw)}")
    message = "\n".join(lines)
    marker["taskMessage"] = message
    aclib.write_text(root / aclib.MARKER, json.dumps(marker, indent=2) + "\n")
    print(message)


if __name__ == "__main__":
    aclib.run_main(main)
