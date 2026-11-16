"""Write the cleaned AC results the judge may read (docs/WORKFLOW.md §4).

Usage: summarize_trx.py <ac-results.trx> <ac-results.md> [--current FNNN [--only-current]]
Tags come from the feature files, because the TRX doesn't carry them. A test's feature is taken from an F<digits>
segment of its class name (the generated namespace follows the Features/FNNN/ folder); otherwise from its scenario
name, marked ambiguous when two features have a scenario of that name. Stack frames outside the AC project are hidden.
With --current, results are split into "Current feature" and "Regression" (all other features); --only-current
reduces the regression section to one line of counts and the F00N/AC-NNN keys of the results that did not pass.
Fails (exit 1) when the TRX holds no result, or none of the --current feature: no test ran is never a pass.

The file is committed with the run records, so it holds no absolute local path (scrub_paths, on every written
line). Pass 1 finds the project root by its own prefix (both separators; case ignored on Windows) and writes what
follows as a repo-relative POSIX path. Pass 2 replaces every other Windows drive or UNC path with "[external path]",
up to its last separator on the line (or its last matching quote, or ":line" in a stack frame), so a user name with
spaces is hidden rather than cut. POSIX paths other than the root stay: they are more likely routes.
"""
import argparse
import os
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
EXTERNAL = "[external path]"
QUOTES = "'\""
# A drive path (not after a letter or digit, so `http://` is none) or a UNC path: two backslashes, a server name, a
# backslash and the first character of a share name (so regex text such as `\\d+\\.` is none).
START = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?<![\\A-Za-z0-9])\\\\[A-Za-z0-9._-]+\\[^\\\s<>|'\"]")
REGION_END = re.compile(r"[<>|]")
RUN_END = re.compile(r"[\s'\"<>|]|:line ")
FRAME_LINE = re.compile(r":line \d")


def root_pattern(root, windows):
    """A root form wherever it starts a path: not glued to a name before it, followed by a separator or by a
    character no path name holds. A bare drive root (`X:`, a subst drive) counts only with a separator."""
    root = root.rstrip("\\/")
    body = "".join(r"[\\/]" if c in "\\/" else re.escape(c) for c in root)
    bare = "" if re.fullmatch(r"[A-Za-z]:", root) else r"|(?=[\s'\"<>|]|$)"
    return re.compile(r"(?<![A-Za-z0-9_.\\/])" + body + r"(?:([\\/])" + bare + ")", re.IGNORECASE if windows else 0)


def relative_to_root(line, roots, windows):
    """Pass 1: every root path becomes repo-relative POSIX; the root itself becomes `.`."""
    patterns = [root_pattern(r, windows) for r in sorted(set(roots), key=len, reverse=True) if r.rstrip("\\/")]
    for pattern in patterns:
        matches = list(pattern.finditer(line))
        if not matches:
            continue
        out, pos = [], 0
        for i, match in enumerate(matches):
            if match.start() < pos:
                continue
            out.append(line[pos:match.start()])
            next_root = matches[i + 1].start() if i + 1 < len(matches) else len(line)
            if match.group(1) is None:
                out.append(".")
                pos = match.end()
                continue
            frame = line[:match.start()].endswith(" in ") and FRAME_LINE.search(line, match.end())
            if frame:  # a stack frame: the path runs to ":line", spaces included
                end = min(frame.start(), next_root)
            else:
                stop = RUN_END.search(line, match.end())
                end = min(stop.start() if stop else len(line), next_root)
            out.append(line[match.end():end].replace("\\", "/") or ".")
            pos = end
        out.append(line[pos:])
        line = "".join(out)
    return line


def hide_external(line):
    """Pass 2: every other Windows drive or UNC path becomes EXTERNAL. It ends at ":line" in a stack frame, at the
    last matching quote when quoted, else at the end of the run holding its last separator: hiding too much wins
    over leaking a tail (a user name with spaces). The search stops at `<`, `>` and `|` (table cells)."""
    pos = 0
    while True:
        match = START.search(line, pos)
        if not match:
            return line
        start = match.start()
        stop = REGION_END.search(line, match.end())
        region_end = stop.start() if stop else len(line)
        region = line[start:region_end]
        frame = FRAME_LINE.search(region)
        quote = line[start - 1] if start > 0 and line[start - 1] in QUOTES else ""
        if frame and line[:start].endswith(" in "):
            end = start + frame.start()
        elif quote and quote in region:
            end = start + region.rfind(quote)
        else:
            separator = "/" if match.group().endswith("/") and not match.group().startswith("\\\\") else "\\"
            last = start + region.rfind(separator)
            space = re.search(r"\s", line[last:region_end])
            end = last + space.start() if space else region_end
            while end > start and line[end - 1] in ".,;:)":
                end -= 1
        line = line[:start] + EXTERNAL + line[end:]
        pos = start + len(EXTERNAL)


def scrub_paths(line, roots, windows=os.name == "nt"):
    """One line of text without absolute local paths (S12-R05). `roots` are the project root's forms."""
    return hide_external(relative_to_root(line, roots, windows))


def root_forms(root):
    """The resolved root and, when the current folder is the root, the current folder as the OS spells it (subst
    drives, junctions): frames carry the path the compiler saw."""
    forms = [str(root)]
    try:
        cwd = os.getcwd()
        if cwd != str(root) and Path(cwd).resolve() == root:
            forms.append(cwd)
    except OSError:
        pass
    return forms


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
    # The file is committed: no absolute local path in any line. clean_stack() has already decided on raw frames.
    roots = root_forms(root)
    text = "\n".join(scrub_paths(line, roots) for line in "\n".join(lines).split("\n"))
    aclib.write_text(Path(args.out), text + "\n")
    print(f"Wrote {args.out}: {len(tests)} test(s), " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    if scopes:
        print(scopes)


if __name__ == "__main__":
    aclib.run_main(main)
