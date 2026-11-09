"""Write the cleaned AC results the judge may read (docs/WORKFLOW.md §4).

Usage: summarize_trx.py <ac-results.trx> <ac-results.md> [--current FNNN [--only-current]]
Tags come from the feature files, because the TRX doesn't carry them. A test's feature is taken from an F<digits>
segment of its class name (the generated namespace follows the Features/FNNN/ folder); otherwise from its scenario
name, marked ambiguous when two features have a scenario of that name. Stack frames outside the AC project are hidden.
With --current, results are split into "Current feature" and "Regression" (all other features); --only-current
reduces the regression section to one line of counts and the F00N/AC-NNN keys of the results that did not pass.
Fails (exit 1) when the TRX holds no result, or none of the --current feature: no test ran is never a pass.
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402

NS = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
PENDING = ("PendingStepException", "MissingStepDefinitionException")
FRAME_FILE = re.compile(r" in (?P<file>.+?):line \d+\s*$")
FEATURE_SEGMENT = re.compile(r"^F\d{3,}$", re.IGNORECASE)
OUTCOMES = ("passed", "failed", "pending", "skipped")


def feature_of_file(feature_file, features_dir):
    """The FNNN folder a .feature file lives in (first folder below Features/), or '' if none."""
    parts = feature_file.relative_to(features_dir).parts
    return parts[0].upper() if len(parts) > 1 and FEATURE_SEGMENT.match(parts[0]) else ""


def scenario_tags(features_dir):
    """Map feature tag -> {scenario name -> tags (feature tags + scenario tags)} from every feature file."""
    index = {}
    for feature_file in sorted(features_dir.rglob("*.feature")) if features_dir.is_dir() else []:
        scenarios = index.setdefault(feature_of_file(feature_file, features_dir), {})
        feature_tags, pending_tags = [], []
        for raw in feature_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("@"):
                pending_tags += line.split()
            elif line.startswith("Feature:"):
                feature_tags, pending_tags = pending_tags, []
            elif re.match(r"(Scenario|Scenario Outline|Scenario Template|Example):", line):
                scenarios[line.split(":", 1)[1].strip()] = feature_tags + pending_tags
                pending_tags = []
            elif line.startswith("Examples:") or line.startswith("Rule:"):
                pending_tags = []
    return index


def comparable(name):
    """Letters and digits only, lower case: NUnit names a test after the generated method (`UnboundStep`), xUnit and
    MSTest after the scenario title (`Unbound step`)."""
    return "".join(c for c in name.lower() if c.isalnum())


def best_match(test_name, scenarios):
    # Scenario Outline rows get the example values appended to the scenario name.
    test = comparable(test_name)
    matches = [name for name in scenarios if comparable(name) and test.startswith(comparable(name))]
    return max(matches, key=lambda name: len(comparable(name))) if matches else None


def locate(test_name, class_name, index):
    """(feature tag, tags) for a test; feature '?' when the name matches scenarios of several features."""
    for segment in class_name.split("."):
        if FEATURE_SEGMENT.match(segment) and segment.upper() in index:
            match = best_match(test_name, index[segment.upper()])
            return segment.upper(), " ".join(index[segment.upper()][match]) if match else ""
    found = {f: best_match(test_name, s) for f, s in index.items()}
    found = {f: m for f, m in found.items() if m}
    if len(found) == 1:
        (feature, match), = found.items()
        return feature, " ".join(index[feature][match])
    if len(found) > 1:
        return "?", f"(ambiguous: {', '.join(sorted(found))})"
    return "", ""


def in_ac_project(frame, ac_dir):
    match = FRAME_FILE.search(frame)
    if not match:
        return False
    try:
        Path(match.group("file")).resolve().relative_to(ac_dir)
        return True
    except ValueError:
        return False


def clean_stack(stack, ac_dir):
    kept, hidden = [], False
    for frame in stack.splitlines():
        if not frame.strip():
            continue
        if in_ac_project(frame, ac_dir):
            kept.append(frame.strip())
            hidden = False
        elif not hidden:
            kept.append("[non-AC frame(s) hidden]")
            hidden = True
    return kept


def outcome(result, error):
    raw = result.get("outcome", "")
    if raw == "Passed":
        return "passed"
    if raw in ("NotExecuted", "Inconclusive"):
        return "skipped"
    return "pending" if any(p in error for p in PENDING) else "failed"


def read_tests(trx, ac_dir):
    index = scenario_tags(ac_dir / "Features")
    tree = ET.parse(trx).getroot()
    classes = {u.get("id"): (u.find("t:TestMethod", NS).get("className", "") if u.find("t:TestMethod", NS) is not None
                             else "")
               for u in tree.iterfind(".//t:TestDefinitions/t:UnitTest", NS)}
    tests = []
    for result in tree.iterfind(".//t:Results/t:UnitTestResult", NS):
        error = result.findtext("t:Output/t:ErrorInfo/t:Message", "", NS).strip()
        stack = result.findtext("t:Output/t:ErrorInfo/t:StackTrace", "", NS)
        trace = [m.text or "" for m in result.iterfind("t:Output/t:TextMessages/t:Message", NS)]
        stdout = result.findtext("t:Output/t:StdOut", "", NS).strip()
        name = result.get("testName", "")
        feature, tags = locate(name, classes.get(result.get("testId"), ""), index)
        ac = next((t[1:] for t in tags.split() if t.startswith("@AC-")), "")
        tests.append({
            "name": name,
            "feature": feature,
            "key": "/".join(x for x in (feature, ac) if x),
            "tags": tags,
            "outcome": outcome(result, error),
            "duration": result.get("duration", ""),
            "trace": trace + ([stdout] if stdout else []),
            "error": error,
            "stack": clean_stack(stack, ac_dir),
        })
    return tests


def section(tests, heading_level):
    counts = {k: sum(t["outcome"] == k for t in tests) for k in OUTCOMES}
    lines = [f"Total: {len(tests)} · " + " · ".join(f"{k}: {counts[k]}" for k in OUTCOMES), "",
             "| Feature | Scenario | Tags | Outcome | Duration |", "|---|---|---|---|---|"]
    lines += [f"| {t['feature']} | {t['name']} | {t['tags']} | {t['outcome']} | {t['duration']} |" for t in tests]
    for t in (t for t in tests if t["outcome"] != "passed"):
        title = " ".join(x for x in (t["key"], t["name"]) if x)
        lines += ["", f"{'#' * heading_level} {title} — {t['outcome']}", "",
                  "Step trace:", "```", *("\n".join(t["trace"]) or "(none)").splitlines(), "```", "",
                  "Exception:", "```", *(t["error"] or "(none)").splitlines(), "```", "",
                  "Stack trace (AC project frames only):", "```", *(t["stack"] or ["(none)"]), "```"]
    return lines, counts


def main():
    parser = argparse.ArgumentParser(description="Write the cleaned AC results the judge may read.")
    parser.add_argument("trx")
    parser.add_argument("out")
    parser.add_argument("--current", help="the current feature's tag, e.g. F003")
    parser.add_argument("--only-current", action="store_true",
                        help="with --current: detail only the current feature; other features are counted and named")
    args = parser.parse_args()
    root = aclib.root(__file__)
    cfg = aclib.load_config(root)
    ac_dir = (root / cfg["acProjectDir"]).resolve()
    tests = read_tests(args.trx, ac_dir)
    # No result is never "everything passed": no AC test ran (an empty feature set, a filter, a runner problem).
    if not tests:
        raise aclib.AcError(f"{args.trx} holds no test results: no AC test ran")

    lines = ["# AC results", ""]
    if args.current:
        current = args.current.upper()
        if not FEATURE_SEGMENT.match(current):
            raise aclib.AcError(f"--current must be a feature tag like F001: {args.current}")
        mine = [t for t in tests if t["feature"] == current]
        if not mine:
            raise aclib.AcError(f"{args.trx} holds no result of the current feature {current}: none of its AC tests ran")
        others = [t for t in tests if t["feature"] != current]
        body, counts = section(mine, 3)
        lines += [f"## Current feature ({current})", "", *body, ""]
        body, other_counts = section(others, 3)
        if args.only_current:
            # The judge looks only at the current feature; regressions are counted and named, never detailed.
            keys = ", ".join(t["key"] or t["name"] for t in others if t["outcome"] != "passed") or "none"
            body = [f"Not part of this analysis (--current): {len(others)} result(s) of other features "
                    f"({' · '.join(f'{k} {other_counts[k]}' for k in OUTCOMES)}); not passed: {keys}."]
        lines += ["## Regression (other features)", "", *body]
        scopes = (f"current {current}: " + ", ".join(f"{k} {counts[k]}" for k in OUTCOMES)
                  + "; regression: " + ", ".join(f"{k} {other_counts[k]}" for k in OUTCOMES))
        counts = {k: counts[k] + other_counts[k] for k in OUTCOMES}
    else:
        if args.only_current:
            raise aclib.AcError("--only-current needs --current <tag>")
        body, counts = section(tests, 2)
        lines += body
        scopes = None
    aclib.write_text(Path(args.out), "\n".join(lines) + "\n")
    print(f"Wrote {args.out}: {len(tests)} test(s), " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    if scopes:
        print(scopes)


if __name__ == "__main__":
    aclib.run_main(main)
