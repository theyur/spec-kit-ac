"""Check one stage of the live end-to-end run from the files it left (spec S07-R06). Never calls a model.

Usage (from the spec-kit-ac checkout):
    uv run python tests/e2e/check_stage.py --project <sample> [--cli tool|checkout] <stage> [args]

Stages:
    init                          config (xunit3 / VSTest), AC project builds, speckit-ac doctor exits 0
    smoke                         guard.log: all three AC roles ran and handed back; nothing left behind
    ac <NNN>                      check_acceptance.py, sources lock; for 001 the 100.00 boundary item (WARN)
    features <NNN>                check_features.py, features lock, @F<NNN> on every feature file
    written <NNN>                 writer report, [Scope(Tag = "F<NNN>")], changes since HEAD within the writer's
                                  allowlist (commit right before /speckit-ac-tests-write)
    analyze <expectation> <NNN>   the latest analyze of feature NNN; expectation fault-001 | pass | superseded-002
Prints PASS / FAIL / WARN lines and exits 1 on any FAIL. The results and verdict tables are always printed.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2elib  # noqa: E402
from e2elib import E2EError, say  # noqa: E402

ROLES = ("ac-feature-translator", "ac-test-writer", "ac-test-fail-judge")
VERDICTS = ("TRANSLATION_FAULT", "TEST_FAULT", "IMPLEMENTATION_FAULT", "SPEC_AMBIGUITY", "UNEXPRESSIBLE",
            "SUPERSEDED", "INCONCLUSIVE")
FEATURE_ID = re.compile(r"\bF(\d{3,})\b", re.IGNORECASE)
AC_ID = re.compile(r"\bAC-(\d{3,})\b", re.IGNORECASE)
ITEM_HEADING = re.compile(r"^###\s+(AC-\d{3,})\b", re.IGNORECASE)
SCOPE = re.compile(r"Scope\s*\(\s*Tag\s*=\s*\"@?(F\d{3,})\"", re.IGNORECASE)
ONLY_CURRENT = "Not part of this analysis (--current)"
SMOKE_FEATURE = "specs/999-speckit-ac-smoke"
MARKER = ".workflow/active-run.json"
EXPECTATIONS = {"fault-001": "001", "pass": None, "superseded-002": "002"}


# ---------------------------------------------------------------- parsers (pure, unit-tested)

def ac_items(text: str) -> dict:
    """acceptance.md -> {AC-NNN: the item's text from its heading to the next heading}."""
    items, current = {}, None
    for line in text.splitlines():
        match = ITEM_HEADING.match(line.strip())
        if match:
            current = match[1].upper()
            items[current] = line + "\n"
        elif line.startswith("#"):
            current = None
        elif current:
            items[current] += line + "\n"
    return items


def results_rows(text: str) -> list[dict]:
    """ac-results.md -> [{feature, name, key, outcome, raw}] from the `| Feature | Scenario | Tags | Outcome |` rows."""
    rows, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced  # step traces may hold Gherkin tables
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if (fenced or not line.lstrip().startswith("|") or len(cells) != 5
                or cells[3].lower() not in ("passed", "failed", "pending", "skipped")):
            continue
        feature, name, tags, outcome = cells[:4]
        ac = AC_ID.search(tags)
        key = f"{feature.upper()}/AC-{ac[1]}" if feature and ac else ""
        rows.append({"feature": feature.upper(), "name": name, "key": key, "outcome": outcome.lower(), "raw": line})
    return rows


def judge_rows(text: str) -> list[dict]:
    """judge-report.md Summary table -> [{key, verdict, raw}]; key '' when no F/AC id could be read."""
    rows, in_summary = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            in_summary = line.strip().lower() == "## summary"
            continue
        if not in_summary or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        verdict_index = next((i for i, c in enumerate(cells) if c.strip("`* ").upper() in VERDICTS), None)
        if verdict_index is None:
            continue  # header or separator
        before = " ".join(cells[:verdict_index])
        feature, ac = FEATURE_ID.search(before), AC_ID.search(before)
        key = f"F{feature[1]}/AC-{ac[1]}" if feature and ac else ""
        rows.append({"key": key, "verdict": cells[verdict_index].strip("`* ").upper(), "raw": line})
    return rows


def guard_log(text: str) -> list[tuple[str, str, str]]:
    return [tuple(line.split("\t")[:3]) for line in text.splitlines() if line.count("\t") >= 2]


def numbered(folder: Path, prefix: str) -> list[Path]:
    found = [p for p in folder.glob(f"{prefix}*") if p.is_dir() and p.name[len(prefix):].isdigit()]
    return sorted(found, key=lambda p: int(p.name[len(prefix):]))


# ---------------------------------------------------------------- checker

class Checker:
    def __init__(self, project: Path, cli: list[str], runner=e2elib.run, analyze_name=None):
        self.project, self.cli, self.runner, self.analyze_name = project, cli, runner, analyze_name
        self.lines: list[tuple[str, str]] = []

    def record(self, status: str, check: str, detail: str = "") -> None:
        self.lines.append((status, check))
        say(f"{status} {check}" + (f": {detail}" if detail else ""))

    def ok(self, condition: bool, check: str, fail_detail: str = "", pass_detail: str = "") -> bool:
        self.record("PASS" if condition else "FAIL", check, pass_detail if condition else fail_detail)
        return condition

    @property
    def failed(self) -> bool:
        return any(status == "FAIL" for status, _ in self.lines)

    def config(self) -> dict:
        return e2elib.load_config(self.project)

    def script(self, cfg: dict, name: str, *args):
        return self.runner([*e2elib.python_cmd(cfg), f"{e2elib.EXTENSION}/scripts/{name}", *args], self.project)

    def script_check(self, cfg: dict, check: str, name: str, *args) -> None:
        code, out = self.script(cfg, name, *args)
        self.ok(code == 0, check, f"exit {code}: {tail(out)}")

    # ------------------------------------------------------------ stages

    def init(self) -> None:
        cfg = self.config()
        self.ok(cfg.get("testFramework") == "xunit3", "config testFramework is xunit3", str(cfg.get("testFramework")))
        command = str(cfg.get("acTestCommand", ""))
        self.ok('--logger "trx' in command and "--project" not in command, "config acTestCommand runs on VSTest",
                command)
        code, out = self.runner(["dotnet", "build", cfg.get("acProject", ""), "-nologo", "-v", "q"], self.project)
        self.ok(code == 0, "AC project builds", f"exit {code}: {tail(out)}")
        code, out = self.runner([*self.cli, "doctor"], self.project)
        self.ok(code == 0, "speckit-ac doctor exits 0", f"exit {code}: {tail(out)}")

    def smoke(self) -> None:
        cfg = self.config()
        log_file = self.project / ".workflow" / "guard.log"
        entries = guard_log(log_file.read_text(encoding="utf-8")) if log_file.is_file() else []
        self.ok(bool(entries), "guard.log has entries", f"{log_file} is missing or empty")
        for role in ROLES:
            mine = [e for e in entries if e[0] == role]
            self.ok(bool(mine), f"{role} ran under the guard", "no guard.log line for it")
            self.ok(any(e[1:] == ("SubagentHandback", "allow") for e in mine), f"{role} handed back",
                    "no `SubagentHandback allow` line: the hand-back was denied or never happened")
        if any(e == ("Explore", "Read", "deny") for e in entries):
            self.record("PASS", "an Explore subagent's Read was denied")
        else:
            self.record("WARN", "no `Explore Read deny` line",
                        "fine if the guard denied the Explore launch itself (a main-agent decision, never logged); "
                        "note what the session showed")
        self.ok(not (self.project / MARKER).exists(), "no active-run marker left", MARKER)
        self.ok(not (self.project / SMOKE_FEATURE).exists(), "no smoke feature left", SMOKE_FEATURE)
        leftover = self.project / cfg.get("acProjectDir", "") / "StepDefinitions" / "smoke-test.txt"
        self.ok(not leftover.exists(), "no smoke isolation file left",
                f"{leftover.relative_to(self.project).as_posix()} (smoke_test.py isolation-file delete)")
        say("Manual (not in guard.log): the main agent's own Read of the isolation file was blocked; the missing "
            "interpreter blocked every call. Note both in the notes file.")

    def ac(self, number: str) -> None:
        cfg = self.config()
        folder = e2elib.feature_dir(self.project, number)
        self.script_check(cfg, "check_acceptance.py passes", "check_acceptance.py", "--feature", number)
        self.script_check(cfg, "sources lock verifies", "ac_lock.py", "verify", "sources", "--feature", number)
        if number == "001":
            path = folder / "acceptance.md"
            items = ac_items(path.read_text(encoding="utf-8")) if path.is_file() else {}
            boundary = [k for k, body in items.items() if "100.00" in body and "90.00" in body]
            if boundary:
                self.record("PASS", "an item checks the boundary 100.00 -> 90.00", ", ".join(boundary))
            else:
                self.record("WARN", "no item checks the boundary 100.00 -> 90.00",
                            "the planted bug can only be caught by such an item (RUNBOOK stage 4 review)")

    def features(self, number: str) -> None:
        cfg = self.config()
        e2elib.feature_dir(self.project, number)
        tag = f"F{number}"
        self.script_check(cfg, "check_features.py passes", "check_features.py", "--feature", number)
        self.script_check(cfg, "features lock verifies", "ac_lock.py", "verify", "features", "--feature", number)
        folder = self.project / cfg.get("acProjectDir", "") / "Features" / tag
        files = sorted(folder.rglob("*.feature")) if folder.is_dir() else []
        self.ok(bool(files), f"feature files in Features/{tag}/", "none")
        for file in files:
            tags = {t for line in file.read_text(encoding="utf-8").splitlines() for t in line.split()
                    if line.strip().startswith("@")}
            self.ok(f"@{tag}" in tags, f"{file.name} carries @{tag}", "tag missing")

    def written(self, number: str) -> None:
        cfg = self.config()
        folder = e2elib.feature_dir(self.project, number)
        tag, ac_dir = f"F{number}", cfg.get("acProjectDir", "")
        runs = numbered(folder / "ac" / "runs", "run-")
        if not self.ok(bool(runs), "a run-NNN folder exists", f"none in {rel(self.project, folder / 'ac' / 'runs')}"):
            return
        run = runs[-1]
        self.ok((run / "writer-report.md").is_file(), f"{run.name}/writer-report.md exists", "missing")
        steps = self.project / ac_dir / "StepDefinitions" / tag
        code_files = sorted(steps.rglob("*.cs")) if steps.is_dir() else []
        self.ok(bool(code_files), f"step definitions in StepDefinitions/{tag}/", "no .cs file")
        for file in code_files:
            scopes = SCOPE.findall(file.read_text(encoding="utf-8"))
            self.ok(bool(scopes) and all(s.upper() == tag for s in scopes),
                    f"{file.name} is scoped to {tag}", f"Scope tags found: {scopes or 'none'}")
        run_rel = rel(self.project, run)
        allowed = [re.compile(rf"^{re.escape(ac_dir)}/(StepDefinitions|Support)/.+"),
                   re.compile(rf"^{re.escape(run_rel)}/(writer-report|input-feedback)\.md$")]
        outside = [p for p in e2elib.changed_paths(self.project)
                   if p.lower().endswith(".feature") or not any(r.match(p) for r in allowed)]
        self.ok(not outside, "changes since HEAD are within the writer's allowlist",
                "outside: " + ", ".join(outside[:10]) + " (if these are translate outputs, the commit before "
                "tests-write was skipped)")

    def analyze(self, expectation: str, number: str) -> None:
        folder = e2elib.feature_dir(self.project, number)
        runs = numbered(folder / "ac" / "runs", "run-")
        analyses = numbered(runs[-1], "analyze-") if runs else []
        if self.analyze_name:  # an earlier analyze of the latest run (a later re-run superseded it)
            analyses = [a for a in analyses if a.name == self.analyze_name]
        if not self.ok(bool(analyses), "an analyze folder exists",
                       f"no {self.analyze_name or 'analyze-K'} in the latest run under {rel(self.project, folder)}/ac/runs"):
            return
        analyze = analyses[-1]
        say(f"Reading {rel(self.project, analyze)}")
        results_file = analyze / "ac-results.md"
        if not self.ok(results_file.is_file(), "ac-results.md exists", "missing"):
            return
        results_text = results_file.read_text(encoding="utf-8")
        rows = results_rows(results_text)
        print_results(rows)
        failing = [r for r in rows if r["outcome"] != "passed"]
        for row in failing:
            if not row["key"]:
                self.record("FAIL", "a result without an AC id did not pass", row["raw"].strip())
        verdicts = {}
        judge_file = analyze / "judge-report.md"
        if judge_file.is_file():
            judged = judge_rows(judge_file.read_text(encoding="utf-8"))
            print_verdicts(judged)
            for row in judged:
                if row["key"]:  # one row per failing example: every verdict of a key counts
                    verdicts.setdefault(row["key"], set()).add(row["verdict"])
                else:
                    self.record("FAIL", "a judge row names no F/AC id", row["raw"].strip())

        if expectation == "pass":
            self.ok(bool(rows) and not failing, "every result passed",
                    f"{len(rows)} result(s), not passed: {', '.join(r['key'] or r['name'] for r in failing) or 'none'}")
            return
        if not self.ok(judge_file.is_file(), "judge-report.md exists", "missing (did every test pass?)"):
            return
        if expectation == "fault-001":
            f001 = [r for r in failing if r["feature"] == "F001"]
            others = [r for r in failing if r["feature"] != "F001"]
            self.ok(bool(f001), "F001 has failing results", "none: the planted bug was not caught")
            self.ok(not others, "no other feature fails", ", ".join(r["key"] or r["name"] for r in others))
            items_file = folder / "acceptance.md"
            items = ac_items(items_file.read_text(encoding="utf-8")) if items_file.is_file() else {}
            for key in sorted({r["key"] for r in f001 if r["key"]}):
                body = items.get(key.split("/")[1], "")
                self.ok("100.00" in body, f"{key} is a 100.00 boundary item", "it fails but is not a boundary item")
                self.ok(verdicts.get(key) == {"IMPLEMENTATION_FAULT"}, f"{key} judged IMPLEMENTATION_FAULT",
                        f"judged {', '.join(sorted(verdicts.get(key, ()))) or 'nothing'}")
        else:  # superseded-002
            if ONLY_CURRENT in results_text:
                self.record("FAIL", "F001 results are detailed",
                            "ac-results.md was written with --only-current: run /speckit-ac-tests-analyze for 002 "
                            "without --current")
            f002 = [r for r in failing if r["feature"] == "F002"]
            f001 = [r for r in failing if r["feature"] == "F001"]
            self.ok(not f002, "every F002 result passed", ", ".join(r["key"] or r["name"] for r in f002))
            self.ok(bool(f001), "F001 has failing results", "none")
            for key in sorted({r["key"] for r in f001 if r["key"]}):
                self.ok(verdicts.get(key) == {"SUPERSEDED"}, f"{key} judged SUPERSEDED",
                        f"judged {', '.join(sorted(verdicts.get(key, ()))) or 'nothing'}")


def tail(text: str, size: int = 600) -> str:
    text = (text or "").strip()
    return text if len(text) <= size else "..." + text[-size:]


def rel(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()


def print_results(rows) -> None:
    say(f"AC results ({len(rows)}):")
    for r in rows:
        say(f"  {r['key'] or r['feature'] + ' (no AC id)':<16} {r['outcome']:<8} {r['name']}")


def print_verdicts(rows) -> None:
    say(f"Judge verdicts ({len(rows)}):")
    for r in rows:
        say(f"  {r['key'] or '(no key)':<16} {r['verdict']}")


def main(argv=None, runner=e2elib.run) -> int:
    parser = argparse.ArgumentParser(description="Check one stage of the live end-to-end run.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--cli", choices=("tool", "checkout"), default="tool")
    parser.add_argument("--analyze", metavar="analyze-K", help="analyze: check this folder of the latest run, "
                                                                 "not the latest one")
    parser.add_argument("stage", choices=("init", "smoke", "ac", "features", "written", "analyze"))
    parser.add_argument("args", nargs="*")
    args = parser.parse_args(argv)
    wanted = {"init": 0, "smoke": 0, "ac": 1, "features": 1, "written": 1, "analyze": 2}[args.stage]
    if len(args.args) != wanted:
        parser.error(f"{args.stage} takes {wanted} argument(s)")
    if args.stage == "analyze":
        if args.args[0] not in EXPECTATIONS:
            parser.error(f"expectation must be one of: {', '.join(EXPECTATIONS)}")
        if EXPECTATIONS[args.args[0]] not in (None, args.args[1]):
            parser.error(f"{args.args[0]} is checked on feature {EXPECTATIONS[args.args[0]]}")
    if args.args and args.args[-1] not in e2elib.SPECS:
        parser.error(f"feature must be one of: {', '.join(e2elib.SPECS)}")
    project = e2elib.require_project(args.project)
    cli = e2elib.cli_command(args.cli) if args.stage == "init" else []
    if args.analyze and (args.stage != "analyze" or not re.fullmatch(r"analyze-\d+", args.analyze)):
        parser.error("--analyze analyze-K goes with the analyze stage")
    checker = Checker(project, cli, runner, args.analyze)
    getattr(checker, args.stage)(*args.args)
    say("")
    say("RESULT: FAIL" if checker.failed else "RESULT: PASS")
    return 1 if checker.failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except E2EError as error:
        say(f"ERROR: {error}")
        sys.exit(1)
