"""Structural check of one feature's generated .feature files (docs/WORKFLOW.md §4).

Gherkin is forgiving: a mistyped keyword ("Givn ...") is read as free description text, not as an error, so the
build passes and the scenario has no steps, and a scenario without steps passes. This check fails on:
- a scenario with no step, or without both a When and a Then step (counting And/But after them, and Background),
- description text inside a scenario after its first step, or any non-keyword line between Scenario and its first step,
- a scenario without an @AC- tag, or an @AC- id used by two scenarios of the feature,
- a file whose Feature-level tags do not include the feature tag @FNNN, or that carries another @F<digits> tag,
- no .feature file at all.
Usage: check_features.py [--feature …]
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402

STEP = re.compile(r"^(Given|When|Then|And|But|\*)\s")
SCENARIO = re.compile(r"^(Scenario|Scenario Outline|Scenario Template|Example):")
FEATURE_TAG = re.compile(r"^@F\d+$")


def check_file(feature_file, name, tag, problems, ids):
    scenarios, current, background, tags, in_doc = [], None, None, [], False
    feature_tags = None
    for number, raw in enumerate(feature_file.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line.startswith(('"""', "```")):
            in_doc = not in_doc
            continue
        if in_doc or not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            tags += line.split()
        elif line.startswith("Feature:"):
            feature_tags, tags, current = tags, [], None
        elif line.startswith("Background:"):
            background = current = {"title": "Background", "line": number, "kinds": [], "tags": []}
        elif SCENARIO.match(line):
            current = {"title": line, "line": number, "kinds": [], "tags": tags}
            scenarios.append(current)
            tags = []
        elif line.startswith(("Rule:", "Examples:", "Scenarios:")):
            if line.startswith("Rule:"):
                current = None
            tags = []
        elif STEP.match(line):
            if current is None:
                problems.append(f"{name}:{number}: step outside a scenario")
                continue
            keyword = line.split()[0]
            current["kinds"].append(current["kinds"][-1] if keyword in ("And", "But", "*") and current["kinds"]
                                    else keyword)
        elif current is not None and not line.startswith("|"):
            problems.append(f"{name}:{number}: not a Gherkin step (mistyped keyword or description text): {line[:60]}")

    found = {t for t in (feature_tags or []) if FEATURE_TAG.match(t)}
    if found != {f"@{tag}"}:
        problems.append(f"{name}: the Feature line must carry the feature tag @{tag} and no other @F tag "
                        f"(found: {', '.join(sorted(found)) or 'none'})")
    for s in scenarios:
        kinds = (background["kinds"] if background else []) + s["kinds"]
        if not s["kinds"]:
            problems.append(f"{name}:{s['line']}: scenario has no steps: {s['title']}")
        elif "When" not in kinds or "Then" not in kinds:
            problems.append(f"{name}:{s['line']}: scenario needs a When and a Then step: {s['title']}")
        other = [t for t in s["tags"] if FEATURE_TAG.match(t) and t != f"@{tag}"]
        if other:
            problems.append(f"{name}:{s['line']}: scenario carries another feature's tag {', '.join(other)}: "
                            f"{s['title']}")
        ac = [t for t in s["tags"] if t.startswith("@AC-")]
        if len(ac) != 1:
            problems.append(f"{name}:{s['line']}: scenario needs exactly one @AC- tag: {s['title']}")
        else:
            ids.setdefault(ac[0], []).append(f"{name}:{s['line']}")


def main():
    parser = argparse.ArgumentParser(description="Structural check of one feature's .feature files.")
    aclib.add_feature_arg(parser)
    args = parser.parse_args()
    root = aclib.root(__file__)
    feature = aclib.resolve_feature(root, args.feature, aclib.load_config(root))
    folder = feature.path(root, "featuresDir")
    files = sorted(folder.rglob("*.feature")) if folder.is_dir() else []
    if not files:
        raise aclib.AcError(f"no .feature file in {feature.paths()['featuresDir']}")
    problems, ids = [], {}
    for feature_file in files:
        check_file(feature_file, aclib.rel_posix(root, feature_file), feature.tag, problems, ids)
    for ac, places in sorted(ids.items()):
        # A Scenario Outline is one scenario; the same id on two scenarios means one AC item was split or duplicated.
        if len(places) > 1:
            problems.append(f"{ac} is used by {len(places)} scenarios: {', '.join(places)}")
    if problems:
        raise aclib.AcError(f"feature check of {feature.dir} ({feature.tag})\n  " + "\n  ".join(problems))
    print(f"OK: {len(ids)} scenario(s) in {len(files)} feature file(s) of {feature.dir} ({feature.tag})")


if __name__ == "__main__":
    aclib.run_main(main)
