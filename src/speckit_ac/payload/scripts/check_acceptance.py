"""Check a feature's acceptance.md before its `sources` are locked (docs/WORKFLOW.md §1, coverage rule).

Usage: check_acceptance.py [--feature …]
Checks the item headings and ids, the Given/When/Then lines, every reference against spec.md, the coverage of every
FR-NNN and every spec scenario (US<N>-AS<M>), and the golden samples the items name. Prints one finding per line,
ids and file names only. Exit 0 = passes, 1 = findings or an error.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402

COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
FR_DEF = re.compile(r"^\s*[-*]\s*\*\*(FR-\d{3,})\*\*", re.MULTILINE)
STORY = re.compile(r"^###\s+User Story\s+(\d+)\b", re.IGNORECASE)
HEADING = re.compile(r"^#{2,3}\s")
NUMBERED = re.compile(r"^\s*(\d+)\.\s")
ITEM = re.compile(r"^(AC-\d{3,})\s*\(([^)]*)\)")  # id and refs; the title after them is free text
REF = re.compile(r"^(FR-\d{3,}|US\d+-AS\d+)$")
STEP = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?(Given|When|Then|And|But)\b")
SAMPLE = re.compile(r"^\s*(?:[-*]\s+)?Golden samples?:(.*)$", re.IGNORECASE)
NOT_TESTABLE = re.compile(r"Not testable through the API:\s*[^\s|]")  # a reason, not just the next table cell


def section(text, title):
    """[(line number, line)] of the `## <title>` section (up to the next `## ` heading), or None."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if re.match(rf"^##\s+{re.escape(title)}\s*$", line, re.I)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^##\s", lines[i])), len(lines))
    return [(i + 1, lines[i]) for i in range(start + 1, end)]


def read(path):
    """File text with HTML comments blanked out (newlines kept, so line numbers stay right)."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return COMMENT.sub(lambda m: "\n" * m[0].count("\n"), text)


def spec_refs(text):
    """FR ids and scenario ids (US<N>-AS<M>) defined in spec.md."""
    frs = set(FR_DEF.findall(text))
    scenarios, story, in_scenarios = [], None, False
    for line in text.split("\n"):
        match = STORY.match(line)
        if match:
            story, in_scenarios = match[1], False
            continue
        if HEADING.match(line):
            story, in_scenarios = None, False
            continue
        if story and "acceptance scenarios" in line.lower():
            in_scenarios = True
            continue
        match = NUMBERED.match(line)
        if story and in_scenarios and match:
            scenarios.append(f"US{story}-AS{match[1]}")
    return frs, scenarios


def items(lines, problems):
    """[(id, refs, body lines)] of the `## Acceptance criteria` section."""
    found, current = [], None
    for number, line in lines:
        if line.startswith("### "):
            match = ITEM.match(line[4:].strip())
            if not match:
                problems.append(f"line {number}: item heading is not `### AC-NNN (<refs>) <title>`")
                current = None
                continue
            refs = [r.strip() for r in re.split(r"[;,]", match[2]) if r.strip()]
            current = (match[1], refs, [])
            found.append(current)
        elif current is not None:
            current[2].append(line)
    return found


def main():
    parser = argparse.ArgumentParser(description="Check a feature's acceptance.md.")
    aclib.add_feature_arg(parser)
    args = parser.parse_args()
    root = aclib.root(__file__)
    feature = aclib.resolve_feature(root, args.feature, aclib.load_config(root))
    paths = feature.paths()
    spec_file, acceptance_file = root / paths["spec"], root / paths["acceptance"]
    for path in (spec_file, acceptance_file):
        if not path.is_file():
            raise aclib.AcError(f"{aclib.rel_posix(root, path)} not found")
    spec, text = read(spec_file), read(acceptance_file)
    frs, scenarios = spec_refs(spec)
    problems = []

    criteria = section(text, "Acceptance criteria")
    found = items(criteria or [], problems)
    if criteria is None:
        problems.append("no `## Acceptance criteria` section")
    elif not found:
        problems.append("no AC items")
    seen, covered = set(), set()
    samples_dir = root / paths["samplesDir"]
    for ac_id, refs, body in found:
        if ac_id in seen:
            problems.append(f"{ac_id}: duplicate id")
        seen.add(ac_id)
        if not refs:
            problems.append(f"{ac_id}: no references (FR-NNN or US<N>-AS<M>)")
        for ref in refs:
            if not REF.match(ref) or (ref.startswith("FR-") and ref not in frs) or (
                    ref.startswith("US") and ref not in scenarios):
                problems.append(f"{ac_id}: reference {ref} is not in spec.md")
            covered.add(ref)
        keywords = {m[1] for m in (STEP.match(line) for line in body) if m}
        for keyword in ("When", "Then"):
            if keyword not in keywords:
                problems.append(f"{ac_id}: no `{keyword}` line")
        for line in body:
            match = SAMPLE.match(line)
            if not match:
                continue
            names = re.findall(r"`([^`]+)`", match[1])
            if not names:
                problems.append(f"{ac_id}: golden sample line names no `file`")
            for name in names:
                clean = name.replace("\\", "/")
                if clean.startswith("/") or re.match(r"^[A-Za-z]:", clean) or ".." in clean.split("/"):
                    problems.append(f"{ac_id}: golden sample {name} must be a file name inside {paths['samplesDir']}")
                elif not (samples_dir / clean).is_file():
                    problems.append(f"{ac_id}: golden sample {name} not found in {paths['samplesDir']}")

    not_testable = set()
    for _, line in section(text, "Coverage") or []:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.strip().startswith("|") and cells and NOT_TESTABLE.search(line):
            not_testable.add(cells[0])
    for fr in sorted(frs):
        if fr not in covered:
            problems.append(f"{fr}: not covered by any AC item")
    for scenario in scenarios:
        if scenario not in covered and scenario not in not_testable:
            problems.append(f"{scenario}: not covered by any AC item and not listed as not testable with a reason")

    for problem in problems:
        print(problem)
    if problems:
        raise aclib.AcError(f"{len(problems)} problem(s) in {paths['acceptance']}")
    untestable = len([s for s in scenarios if s not in covered])
    print(f"OK: {len(found)} item(s); {len(frs)} FR and {len(scenarios) - untestable} scenario(s) covered, "
          f"{untestable} not testable")


if __name__ == "__main__":
    aclib.run_main(main)
