"""Write .workflow/config.json for /speckit-ac-init from the user's confirmed answers (docs/CONFIG.md).

Usage: init_config.py --solution App.slnx --surface src/App.Core/App.Core.csproj [--surface …]
                      [--unit-tests tests/App.Tests/App.Tests.csproj …] --ac-project-dir tests/App.AcceptanceTests
                      [--refs-dir artifacts/refs] [--spec-input docs/domain …] --framework xunit3 --runner mtp
The test commands come from RECIPES, one entry per (framework, runner) pair verified for real in step 5: packages,
MSBuild properties and the TRX option that makes acTestCommand write {analyzeDir}/ac-results.trx. Other pairs are
refused. init_scaffold.py takes the packages and properties from the same table. An existing config is never
overwritten.
"""
import argparse
import json
import posixpath
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402

PYTHON = "uv run --no-project python -I"  # v1.0 environment (DESIGN §2)
RUNNERS = ("vstest", "mtp")
VSTEST_TRX = '--logger "trx;LogFileName=ac-results.trx"'
MTP_TRX = "--report-trx --report-trx-filename ac-results.trx"
ADAPTER = {"xunit2": "Reqnroll.xUnit", "xunit3": "Reqnroll.xunit.v3", "nunit": "Reqnroll.NUnit",
           "mstest": "Reqnroll.MSTest"}
ASSERT_NAMESPACE = {"xunit2": "Xunit", "xunit3": "Xunit", "nunit": "NUnit.Framework",
                    "mstest": "Microsoft.VisualStudio.TestTools.UnitTesting"}
# (framework, runner) -> test packages (besides the Reqnroll adapter), MSBuild properties, TRX option.
# Verified 2026-11-08 with SDK 10.0.403 and Reqnroll 3.3.4 (docs/steps/TRACKER.md, step 5).
RECIPES = {
    ("xunit2", "vstest"): {"packages": ["xunit", "xunit.runner.visualstudio", "Microsoft.NET.Test.Sdk"],
                           "properties": {}, "trx": VSTEST_TRX},
    # Plain xunit.v3 turns on Microsoft.Testing.Platform, which the .NET 10 SDK refuses under VSTest.
    ("xunit3", "vstest"): {"packages": ["xunit.v3.mtp-off", "xunit.runner.visualstudio", "Microsoft.NET.Test.Sdk"],
                           "properties": {"OutputType": "Exe"}, "trx": VSTEST_TRX},
    ("xunit3", "mtp"): {"packages": ["xunit.v3"], "properties": {"OutputType": "Exe"},
                        "trx": "--report-xunit-trx --report-xunit-trx-filename ac-results.trx"},
    ("nunit", "vstest"): {"packages": ["NUnit", "NUnit3TestAdapter", "Microsoft.NET.Test.Sdk"],
                          "properties": {}, "trx": VSTEST_TRX},
    # The NUnit runner has no TRX report of its own.
    ("nunit", "mtp"): {"packages": ["NUnit", "NUnit3TestAdapter", "Microsoft.Testing.Extensions.TrxReport"],
                       "properties": {"OutputType": "Exe", "EnableNUnitRunner": "true"}, "trx": MTP_TRX},
    ("mstest", "vstest"): {"packages": ["MSTest"], "properties": {}, "trx": VSTEST_TRX},
    ("mstest", "mtp"): {"packages": ["MSTest"], "properties": {"OutputType": "Exe", "EnableMSTestRunner": "true"},
                        "trx": MTP_TRX},
}
UNSUPPORTED = {
    ("xunit2", "mtp"): "xUnit v2 has no Microsoft.Testing.Platform runner; `dotnet test` refuses a VSTest project when "
                       "global.json selects Microsoft.Testing.Platform",
}
BUILD_FOLDER = re.compile(r"^(bin|obj)([-_.].*)?$", re.IGNORECASE)


def supported_pairs() -> list[str]:
    return [f"{framework}/{runner}" for framework, runner in RECIPES]


def recipe(framework: str, runner: str) -> dict:
    if (framework, runner) not in RECIPES:
        reason = UNSUPPORTED.get((framework, runner), "not verified")
        raise aclib.AcError(f"{framework} on {runner} is not supported ({reason}). "
                            f"Supported: {', '.join(supported_pairs())}")
    return RECIPES[(framework, runner)]


def implementation_folders(root: Path) -> list[str]:
    """`src` plus every folder that holds a .csproj (outside bin/obj): never spec inputs for the AC subagents."""
    folders = {"src"}
    for csproj in root.rglob("*.csproj"):
        parts = csproj.relative_to(root).parts
        if any(BUILD_FOLDER.match(p) or p in (".git", ".specify", "node_modules") for p in parts[:-1]):
            continue
        folders.add(posixpath.join(*parts[:-1]) if len(parts) > 1 else ".")
    return sorted(folders)


def overlapping_folder(value: str, folders: list[str]):
    """The implementation folder `value` (project-relative posix) equals, contains or lies inside, or None."""
    for folder in folders:
        if folder == "." or aclib._overlaps(value, folder):
            return folder
    return None


def no_whitespace(value: str, key: str):
    if re.search(r"\s", value):
        raise aclib.AcError(f"{key} must not contain whitespace (it is part of commands split on spaces): {value}")


def build(args, root: Path) -> dict:
    rec = recipe(args.framework, args.runner)
    ac_dir = aclib._relative_clean(args.ac_project_dir, "acProjectDir")
    refs = aclib._relative_clean(args.refs_dir, "refsDir")
    for value, key in [(ac_dir, "acProjectDir"), (refs, "refsDir")] + [(u, "unitTestProjects") for u in args.unit_tests]:
        no_whitespace(value, key)
    ac_project = f"{ac_dir}/{posixpath.basename(ac_dir)}.csproj"
    if args.runner == "mtp":
        unit = "dotnet test --project {project}"
        ac_test = "dotnet test --project {acProject} --no-build --results-directory {analyzeDir} " + rec["trx"]
    else:
        unit = "dotnet test {project}"
        ac_test = "dotnet test {acProject} --no-build --results-directory {analyzeDir} " + rec["trx"]
    folders = implementation_folders(root)
    spec_inputs = []
    for value in args.spec_input:
        clean = aclib._relative_clean(value, "specInputs")
        folder = overlapping_folder(clean, folders)
        if folder is not None:
            raise aclib.AcError(f"spec input {clean} overlaps the implementation folder {folder}: the AC subagents must "
                                "never see the implementation. Choose documents outside the code.")
        spec_inputs.append(clean)
    cfg = {
        "schemaVersion": aclib.SCHEMA_VERSION,
        "python": PYTHON,
        "solution": args.solution.replace("\\", "/"),
        "specInputs": spec_inputs,
        "acSurfaceProjects": [p.replace("\\", "/") for p in args.surface],
        "unitTestProjects": [p.replace("\\", "/") for p in args.unit_tests],
        "acProjectDir": ac_dir,
        "acProject": ac_project,
        "refsDir": refs,
        "acRefBuildCommand": f"dotnet build {ac_project} -p:AcRefMode=true -nologo -v q",
        "unitTestCommand": unit,
        "acTestCommand": ac_test,
        "testFramework": args.framework,
    }
    return aclib.validate_config(cfg)


def main():
    parser = argparse.ArgumentParser(description="Write .workflow/config.json for the AC workflow.")
    parser.add_argument("--solution", required=True)
    parser.add_argument("--surface", action="append", required=True)
    parser.add_argument("--unit-tests", action="append", default=[])
    parser.add_argument("--ac-project-dir", required=True)
    parser.add_argument("--refs-dir", default="artifacts/refs")
    parser.add_argument("--spec-input", action="append", default=[])
    parser.add_argument("--framework", required=True, choices=aclib.ENUM_KEYS["testFramework"])
    parser.add_argument("--runner", required=True, choices=RUNNERS)
    args = parser.parse_args()
    root = aclib.root(__file__)
    path = root / aclib.CONFIG
    if path.exists():
        raise aclib.AcError(f"{aclib.CONFIG} already exists; it is never overwritten. Edit it by hand, or delete it to "
                            "run the setup again.")
    cfg = build(args, root)
    text = json.dumps(cfg, indent=2) + "\n"
    aclib.write_text(path, text)
    print(f"Wrote {aclib.CONFIG}:")
    print(text, end="")


if __name__ == "__main__":
    aclib.run_main(main)
