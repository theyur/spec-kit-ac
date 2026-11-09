"""Check the AC setup end to end with temporary files (CT doc §6 items 1 and 3-7); used by /speckit-ac-init.

Usage: init_verify.py
Prints one line per check (PASS / FAIL / SKIP) and a total; exit 1 on any FAIL. A failed build prints its error and
warning lines (codes and files) under the FAIL line.
Temporary files only: the feature specs/999-speckit-ac-check/ (tag F999), its folders Features/F999/,
Samples/F999/ and StepDefinitions/F999/ in the AC project, and .workflow/init-check/. They are removed at the end,
whatever happens; the product's projects are never written. A last check compares the working tree's content hashes
with a snapshot taken after the first builds (build output and refsDir excluded) and fails on any leftover.
"""
import contextlib
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402
import changed_files  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
FEATURE_DIR = "specs/999-speckit-ac-check"
NUMBER, TAG = "999", "F999"
RESULTS = ".workflow/init-check"
DIAGNOSTIC = re.compile(r"\b(error|warning)\s+[A-Z]{2,}\d+", re.IGNORECASE)
MAX_LINES = 40

SPEC = """# Feature Specification: speckit-ac init check (temporary)

## Requirements

- **FR-001**: The system doubles a number.
"""
ACCEPTANCE = """# Acceptance criteria: speckit-ac init check (temporary)

### AC-001 (FR-001) Doubling
- Given a number 2
- When it is doubled
- Then the result is 4

### AC-002 (FR-001) Doubling other numbers
- Given a number 3
- When it is doubled
- Then the result is 6

### AC-003 (FR-001) Unbound step
- Given a step nobody has bound
- When it is doubled
- Then the result is 4
"""
FEATURE = """@F999
Feature: speckit-ac init check

Background:
  Given a number 2

@AC-001
Scenario: Doubling
  When it is doubled
  Then the result is 4

@AC-002
Scenario Outline: Doubling other numbers
  Given a number <n>
  When it is doubled
  Then the result is <r>

  Examples:
    | n | r |
    | 3 | 6 |

@AC-003
Scenario: Unbound step
  Given a step nobody has bound
  When it is doubled
  Then the result is 4
"""
# A valid feature turned invalid in the four ways check_features.py must catch: (label, old, new).
BROKEN_FEATURES = [
    ("mistyped keyword", "  When it is doubled\n  Then the result is 4\n\n@AC-002", "  Whn it is doubled\n  Then the result is 4\n\n@AC-002"),
    ("missing When", "  Given a step nobody has bound\n  When it is doubled\n", "  Given a step nobody has bound\n"),
    ("missing @AC- tag", "@AC-003\n", ""),
    ("duplicate id", "@AC-002\n", "@AC-001\n"),
]
STEPS = """namespace SpeckitAcInitCheck.F999;

/// <summary>Temporary step definitions of the speckit-ac init check.</summary>
[Reqnroll.Binding, Reqnroll.Scope(Tag = "F999")]
public class InitCheckSteps
{
    private int _number;

    /// <summary>Sets the number.</summary>
    [Reqnroll.Given("a number {int}")]
    public void GivenANumber(int number) => _number = number;

    /// <summary>Doubles the number.</summary>
    [Reqnroll.When("it is doubled")]
    public void WhenItIsDoubled() => _number *= 2;

    /// <summary>Checks the number.</summary>
    [Reqnroll.Then("the result is {int}")]
    public void ThenTheResultIs(int expected)
    {
        if (_number != expected)
        {
            throw new System.InvalidOperationException($"{_number} != {expected}");
        }
    }
}
"""
WARNING_FILE = """namespace SpeckitAcInitCheck.F999;

internal static class AcInitCheckWarning
{
    internal static void Unused()
    {
        int unused;
    }
}
"""


def run(args, cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as error:
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]} could not start: {error}")


def script(root: Path, name: str, *args) -> subprocess.CompletedProcess:
    return run([sys.executable, "-I", str(SCRIPTS / name), *args], root)


def diagnostics(result) -> list[str]:
    lines, seen = [], set()
    for line in (result.stdout + result.stderr).splitlines():
        line = line.strip()
        if DIAGNOSTIC.search(line) and line not in seen:
            seen.add(line)
            lines.append(line)
    return lines[:MAX_LINES]


def tail(result) -> list[str]:
    return [line for line in (result.stdout + result.stderr).splitlines() if line.strip()][-MAX_LINES:]


class Checks:
    def __init__(self):
        self.counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}

    def add(self, status: str, check: str, text: str, details=()):
        self.counts[status] += 1
        print(f"{status} {check} {text}")
        for line in details:
            print(f"    {line}")

    def ok(self, passed: bool, check: str, text: str, details=()):
        self.add("PASS" if passed else "FAIL", check, text, () if passed else details)
        return passed


class Verify:
    def __init__(self, root: Path, cfg: dict):
        self.root, self.cfg, self.checks = root, cfg, Checks()
        ac = cfg["acProjectDir"]
        self.ac = root / ac
        self.feature_paths = {name: root / f"{ac}/{name}/{TAG}" for name in ("Features", "Samples", "StepDefinitions")}
        self.spec, self.acceptance = root / FEATURE_DIR / "spec.md", root / FEATURE_DIR / "acceptance.md"
        self.sample = self.feature_paths["Samples"] / "sample.txt"
        self.feature = self.feature_paths["Features"] / "check.feature"
        self.steps = self.feature_paths["StepDefinitions"] / "InitCheckSteps.cs"
        self.warning = self.feature_paths["StepDefinitions"] / "AcInitCheckWarning.cs"
        self.snapshot = None

    # ---- temporary files -------------------------------------------------------------------------------------

    def temp_paths(self) -> list[Path]:
        specs = self.root / "specs"
        numbered = sorted(specs.glob(f"{NUMBER}-*")) if specs.is_dir() else []
        return [*numbered, *self.feature_paths.values(), self.root / RESULTS]

    def write_temp_files(self):
        aclib.write_text(self.spec, SPEC)
        aclib.write_text(self.acceptance, ACCEPTANCE)
        aclib.write_text(self.sample, "golden sample\n")
        aclib.write_text(self.feature, FEATURE)
        aclib.write_text(self.steps, STEPS)

    def remove_temp_files(self):
        for path in self.temp_paths():
            shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink(missing_ok=True)

    def tree(self) -> dict:
        refs = self.cfg["refsDir"] + "/"
        # __pycache__: Python writes bytecode next to the workflow scripts the checks run.
        return {p: h for p, h in changed_files.tree_hashes(self.root, self.cfg).items()
                if not p.startswith(refs) and not p.startswith(RESULTS + "/") and "/__pycache__/" not in f"/{p}"}

    # ---- helpers ---------------------------------------------------------------------------------------------

    def dotnet_build(self, target: str, *extra) -> subprocess.CompletedProcess:
        return run(["dotnet", "build", target, *extra, "-nologo", "-v", "q"], self.root)

    def config_command(self, key: str, **values) -> list[str]:
        command = self.cfg[key]
        for name, value in values.items():
            command = command.replace("{" + name + "}", value)
        return shlex.split(command)

    @contextlib.contextmanager
    def changed_byte(self, path: Path):
        data = path.read_bytes()
        path.write_bytes(data[:-1] + bytes([data[-1] ^ 0x01]))
        try:
            yield
        finally:
            path.write_bytes(data)

    @contextlib.contextmanager
    def extra_file(self, path: Path):
        aclib.write_text(path, "extra\n")
        try:
            yield
        finally:
            path.unlink(missing_ok=True)

    # ---- checks ----------------------------------------------------------------------------------------------

    def builds(self) -> bool:
        solution = self.dotnet_build(self.cfg["solution"])
        if not self.checks.ok(solution.returncode == 0, "[1]", f"dotnet build {self.cfg['solution']}",
                              diagnostics(solution) or tail(solution)):
            return False
        ac = self.dotnet_build(self.cfg["acProject"])
        return self.checks.ok(ac.returncode == 0, "[1]", f"dotnet build {self.cfg['acProject']} (normal mode)",
                              diagnostics(ac) or tail(ac))

    def locks(self):
        problems = []

        def lock(*args, want=0):
            result = script(self.root, "ac_lock.py", *args, "--feature", NUMBER)
            if result.returncode != want:
                problems.append(f"ac_lock.py {' '.join(args)}: exit {result.returncode}, expected {want} "
                                f"({(result.stdout + result.stderr).strip()[-200:]})")

        lock("lock", "sources")
        lock("verify", "sources")
        with self.changed_byte(self.acceptance):
            lock("verify", "sources", want=1)
        with self.changed_byte(self.sample):
            lock("verify", "sources", want=1)
        with self.extra_file(self.sample.with_name("extra.txt")):
            lock("verify", "sources", want=1)
        with self.changed_byte(self.spec):
            lock("verify", "sources", want=3)
        lock("verify", "sources")
        lock("unlock", "sources")
        lock("lock", "features")
        lock("verify", "features")
        with self.changed_byte(self.feature):
            lock("verify", "features", want=1)
        with self.extra_file(self.feature.with_name("extra.txt")):
            lock("verify", "features", want=1)
        lock("unlock", "features")
        self.checks.ok(not problems, "[3]", "ac_lock.py: lock, verify, changed byte / extra file / spec drift detected, "
                       "unlock (sources and features)", problems)

    def export(self):
        restore = run(["dotnet", "tool", "restore"], self.root)
        if not self.checks.ok(restore.returncode == 0, "[4]", "dotnet tool restore (ilspycmd)", tail(restore)):
            return
        result = script(self.root, "export_refs.py")
        if not self.checks.ok(result.returncode == 0, "[4]", "export_refs.py", tail(result)):
            return
        refs = self.root / self.cfg["refsDir"]
        dlls = sorted(refs.glob("*.dll"))
        problems = [f"{d.name} is not a reference assembly" for d in dlls
                    if b"ReferenceAssemblyAttribute" not in d.read_bytes()]
        problems += [f"api/{d.stem}.cs is missing" for d in dlls if not (refs / "api" / f"{d.stem}.cs").is_file()]
        problems += ["no reference assembly exported"] if not dlls else []
        self.checks.ok(not problems, "[4]", f"reference assemblies and API listings in {self.cfg['refsDir']}: "
                       + ", ".join(d.name for d in dlls), problems)

    def ref_mode(self):
        build = run(self.config_command("acRefBuildCommand"), self.root)
        if not self.checks.ok(build.returncode == 0, "[5]", "acRefBuildCommand (ref mode)",
                              diagnostics(build) or tail(build)):
            return
        exported = {d.name.lower() for d in (self.root / self.cfg["refsDir"]).glob("*.dll")}
        bin_ref, obj_ref = self.ac / "bin-ref", self.ac / "obj-ref"
        copied = sorted({f.name for f in bin_ref.rglob("*.dll") if f.name.lower() in exported}) \
            if bin_ref.is_dir() else []
        problems = [f"{name} is missing" for name in ("bin-ref", "obj-ref") if not (self.ac / name).is_dir()]
        problems += [f"bin-ref/ holds a copy of {name}" for name in copied]
        self.checks.ok(not problems, "[5]", "ref-mode output only in bin-ref/ and obj-ref/, no surface assembly copied",
                       problems)
        behind = list(obj_ref.rglob("check.feature.cs")) if obj_ref.is_dir() else []
        stray = [aclib.rel_posix(self.root, f) for f in (self.ac / "Features").rglob("*.feature.cs")]
        self.checks.ok(bool(behind) and not stray, "[6]", "feature code-behind under obj-ref/, none in Features/",
                       stray or ["no check.feature.cs under obj-ref/"])
        self.warnings_as_errors()
        normal = self.dotnet_build(self.cfg["acProject"])
        self.checks.ok(normal.returncode == 0, "[5]", "normal-mode build after the ref-mode build",
                       diagnostics(normal) or tail(normal))

    def warnings_as_errors(self):
        query = run(["dotnet", "msbuild", self.cfg["acProject"], "-p:AcRefMode=true",
                     "-getProperty:TreatWarningsAsErrors", "-getProperty:NoWarn", "-getProperty:WarningsNotAsErrors"],
                    self.root)
        try:
            props = json.loads(query.stdout)["Properties"]
        except (ValueError, KeyError, TypeError):
            self.checks.add("FAIL", "[5]", "could not read TreatWarningsAsErrors of the AC project", tail(query))
            return
        if props.get("TreatWarningsAsErrors", "").strip().lower() != "true":
            self.checks.add("SKIP", "[5]", "warnings-as-errors check: TreatWarningsAsErrors is not set for the AC project")
            return
        exempt = [k for k in ("NoWarn", "WarningsNotAsErrors") if "cs0168" in props.get(k, "").lower()]
        if exempt:
            self.checks.add("SKIP", "[5]", f"warnings-as-errors check: CS0168 is listed in {', '.join(exempt)}")
            return
        aclib.write_text(self.warning, WARNING_FILE)
        try:
            build = run(self.config_command("acRefBuildCommand"), self.root)
        finally:
            self.warning.unlink(missing_ok=True)
        output = build.stdout + build.stderr
        self.checks.ok(build.returncode != 0 and "CS0168" in output, "[5]",
                       "root Directory.Build.props applies in ref mode (a CS0168 warning fails the build)",
                       ["the ref-mode build did not fail on CS0168"])

    def feature_check(self):
        valid = script(self.root, "check_features.py", "--feature", NUMBER)
        problems = [] if valid.returncode == 0 else [f"valid feature rejected: {tail(valid)}"]
        for label, old, new in BROKEN_FEATURES:
            assert old in FEATURE, label
            aclib.write_text(self.feature, FEATURE.replace(old, new, 1))
            try:
                if script(self.root, "check_features.py", "--feature", NUMBER).returncode != 1:
                    problems.append(f"{label} not detected")
            finally:
                aclib.write_text(self.feature, FEATURE)
        self.checks.ok(not problems, "[6]", "check_features.py: valid feature passes; mistyped keyword, missing When, "
                       "missing @AC- tag, duplicate id fail", problems)

    def test_run(self):
        listing = run(["dotnet", "sln", self.cfg["solution"], "list"], self.root)
        name = Path(self.cfg["acProject"]).name.lower()
        in_solution = any(line.strip().replace("\\", "/").lower().endswith(name)
                          for line in listing.stdout.splitlines())
        self.checks.ok(listing.returncode == 0 and not in_solution, "[7]", "the AC project is not in the solution",
                       tail(listing) if listing.returncode else ["the solution lists the AC project"])
        analyze = f"{RESULTS}/analyze"
        test = run(self.config_command("acTestCommand", acProject=self.cfg["acProject"], analyzeDir=analyze),
                   self.root)
        trx = self.root / analyze / "ac-results.trx"
        if not self.checks.ok(trx.is_file(), "[7]", f"acTestCommand writes {analyze}/ac-results.trx", tail(test)):
            return
        md = self.root / RESULTS / "ac-results.md"
        summary = script(self.root, "summarize_trx.py", str(trx), str(md), "--current", TAG)
        if not self.checks.ok(summary.returncode == 0 and md.is_file(), "[7]", "summarize_trx.py", tail(summary)):
            return
        text = md.read_text(encoding="utf-8")
        rows = {key: next((line for line in text.splitlines() if line.startswith("|") and f"@{key}" in line), "")
                for key in ("AC-001", "AC-003")}
        problems = []
        if "| passed |" not in rows["AC-001"]:
            problems.append("AC-001 (bound) did not pass")
        if "| pending |" not in rows["AC-003"]:
            problems.append("AC-003 (unbound) is not pending")
        if "@F999 @AC-001" not in text:
            problems.append("tags @F999 @AC-001 missing")
        if "a step nobody has bound" not in text:
            problems.append("the step trace of the unbound scenario is missing")
        self.checks.ok(not problems, "[7]", "results: bound scenario passed, unbound pending, tags and step trace shown",
                       problems)

    def leftovers(self):
        after = self.tree()
        changed = sorted(p for p in self.snapshot.keys() | after.keys() if self.snapshot.get(p) != after.get(p))
        self.checks.ok(not changed, "[9]", "no leftovers: the working tree is as before the checks",
                       changed[:MAX_LINES] + ["(build side effects such as packages.lock.json can cause this)"])

    def run_all(self):
        existing = [aclib.rel_posix(self.root, p) for p in self.temp_paths() if p.exists()]
        if existing:
            raise aclib.AcError("temporary paths of the check already exist (a previous run was interrupted?): "
                                + ", ".join(existing) + ". Delete them, then run init_verify.py again.")
        try:
            if self.builds():
                self.snapshot = self.tree()
                self.write_temp_files()
                self.locks()
                self.export()
                self.ref_mode()
                self.feature_check()
                self.test_run()
        finally:
            self.remove_temp_files()
            if self.snapshot is not None:
                self.leftovers()
        c = self.checks.counts
        print(f"Total: {c['PASS']} passed, {c['FAIL']} failed, {c['SKIP']} skipped")
        return c["FAIL"] == 0


def main():
    root = aclib.root(__file__)
    if not Verify(root, aclib.load_config(root)).run_all():
        sys.exit(1)


if __name__ == "__main__":
    aclib.run_main(main)
