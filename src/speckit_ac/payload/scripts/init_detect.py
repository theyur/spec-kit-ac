"""Detect what /speckit-ac-init needs to know about the project; print it as JSON. Changes nothing.

Usage: init_detect.py [--solution App.slnx] [--framework xunit3]
Prints: the v1.0 environment problems, the solution(s), each C# project of the solution (evaluated with
`dotnet msbuild -getProperty/-getItem`, so root props and central package management count), the test runner
(global.json), central package management, the root Directory.Build.props, the implementation folders (never spec
inputs), proposals for every config value, whether the (framework, runner) pair is supported, and blockers.
--framework re-checks `supported` for the framework the user chose.
"""
import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402
import init_config  # noqa: E402

PROPERTIES = ("TargetFramework", "TargetFrameworks", "OutputType", "IsTestProject", "AssemblyName",
              "ManagePackageVersionsCentrally")
ITEMS = ("PackageReference", "FrameworkReference", "PackageVersion")
RUNNABLE_TFM = re.compile(r"^net(?:coreapp)?(\d+)\.(\d+)(-.+)?$", re.IGNORECASE)
SOURCE_SUFFIXES = (".cs", ".csproj", ".props", ".targets")
BUILD_FOLDER = re.compile(r"^(bin|obj)([-_.].*)?$", re.IGNORECASE)


def run(args, cwd: Path) -> str:
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as error:
        raise aclib.AcError(f"{' '.join(args)} could not start: {error}") from None
    if result.returncode != 0:
        raise aclib.AcError(f"{' '.join(args)} failed:\n{(result.stdout + result.stderr)[-3000:]}")
    return result.stdout


def framework_of(package_ids) -> list[str]:
    """Test frameworks named by package ids (sorted; several means a mix)."""
    found = set()
    for pid in package_ids:
        name = pid.lower()
        if name.startswith("xunit.v3"):
            found.add("xunit3")
        elif name in ("xunit", "xunit.core"):
            found.add("xunit2")
        elif name == "nunit":
            found.add("nunit")
        elif name in ("mstest", "mstest.testframework", "mstest.sdk"):
            found.add("mstest")
    return sorted(found)


def git_ok(root: Path) -> bool:
    try:
        return subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, capture_output=True,
                              text=True).stdout.strip() == "true"
    except OSError:
        return False


def environment(root: Path, which=shutil.which, system=platform.system, git=git_ok) -> list[str]:
    """Problems with the v1.0 environment (DESIGN §2); empty when everything is in place."""
    problems = []
    if system() != "Windows":
        problems.append(f"OS is {system()}; spec-kit-ac v1.0 supports Windows only")
    for tool in ("uv", "pwsh", "dotnet"):
        if which(tool) is None:
            problems.append(f"{tool} is not on PATH")
    options = root / ".specify" / "init-options.json"
    try:
        data = json.loads(options.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        problems.append(".specify/init-options.json is missing or not valid JSON (is spec-kit initialised?)")
    elif data.get("script") != "ps":
        problems.append(f'.specify/init-options.json has "script": {json.dumps(data.get("script"))}; v1.0 needs '
                        '"ps" (specify init --script ps)')
    if aclib._feature_numbering(root) == "timestamp":
        problems.append(f".specify/init-options.json uses timestamp feature numbering. {aclib.V1_LIMIT}")
    specs = root / "specs"
    stamped = sorted(d.name for d in specs.iterdir() if d.is_dir() and aclib.TIMESTAMP_NAME.match(d.name)) \
        if specs.is_dir() else []
    if stamped:
        problems.append(f"timestamp feature folders under specs/ ({', '.join(stamped)}). {aclib.V1_LIMIT}")
    if not (root / "CLAUDE.md").is_file():
        problems.append("CLAUDE.md is missing")
    if not git(root):
        problems.append("the project is not a git repository")
    return problems


def solutions(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.is_file() and p.suffix.lower() in (".sln", ".slnx"))


def sln_projects(root: Path, solution: str, runner=run) -> list[str]:
    """Project paths of a solution (project-relative posix), as `dotnet sln list` prints them."""
    lines = runner(["dotnet", "sln", solution, "list"], root).splitlines()
    dashes = next((i for i, line in enumerate(lines) if line.strip().startswith("---")), None)
    entries = lines[dashes + 1:] if dashes is not None else []
    base = (root / solution).parent
    out = []
    for entry in (e.strip() for e in entries):
        if entry:
            out.append(aclib.rel_posix(root, base / entry.replace("\\", "/")))
    return out


def evaluate(root: Path, project: str, runner=run) -> dict:
    args = ["dotnet", "msbuild", project, *[f"-getProperty:{p}" for p in PROPERTIES],
            *[f"-getItem:{i}" for i in ITEMS]]
    try:
        return json.loads(runner(args, root))
    except ValueError as error:
        raise aclib.AcError(f"dotnet msbuild {project}: unexpected output ({error})") from None


def internals_visible_to(root: Path, project: str) -> list[str]:
    """Files of the project (and root props/targets) that mention InternalsVisibleTo (same search as export_refs)."""
    folder = (root / project).parent
    files = [f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in SOURCE_SUFFIXES
             and not any(BUILD_FOLDER.match(s) for s in f.relative_to(folder).parts[:-1])]
    files += [root / n for n in ("Directory.Build.props", "Directory.Build.targets") if (root / n).is_file()]
    return sorted({aclib.rel_posix(root, f) for f in files
                   if "InternalsVisibleTo" in f.read_text(encoding="utf-8", errors="replace")})


def _true(value) -> bool:
    return isinstance(value, str) and value.strip().lower() == "true"


def package_refs(evaluation: dict) -> list[dict]:
    """[{id, version, privateAssets, implicit}] of a project's PackageReference items (msbuild evaluation with
    -getItem:PackageReference and -getItem:PackageVersion). Version: VersionOverride, Version, the central pin."""
    items = evaluation.get("Items", {})
    pins = {i["Identity"].lower(): i.get("Version") for i in items.get("PackageVersion", [])}
    packages = []
    for item in items.get("PackageReference", []):
        pid = item["Identity"]
        version = item.get("VersionOverride") or item.get("Version") or pins.get(pid.lower()) or None
        packages.append({"id": pid, "version": version, "privateAssets": item.get("PrivateAssets", ""),
                         "implicit": _true(item.get("IsImplicitlyDefined"))})
    return packages


def public_package(package: dict) -> bool:
    """A package whose public types a consumer compiles against: not implicit (SDK) and not PrivateAssets=all.
    /speckit-ac-init adds these to the AC project; export_refs.py checks that they are still there."""
    return not package["implicit"] and package["privateAssets"].strip().lower() != "all"


def version_key(version: str):
    parts = re.split(r"[.-]", version)
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in parts]


def highest(versions):
    versions = sorted({v for v in versions if v}, key=version_key)
    return versions[-1] if versions else None


def describe(root: Path, project: str, evaluation: dict) -> dict:
    """One project's facts from its msbuild evaluation."""
    props, items = evaluation.get("Properties", {}), evaluation.get("Items", {})
    packages = package_refs(evaluation)
    frameworks = framework_of(p["id"] for p in packages)
    tfms = [t for t in (props.get("TargetFrameworks") or props.get("TargetFramework") or "").split(";") if t.strip()]
    return {
        "path": project,
        "assemblyName": props.get("AssemblyName", ""),
        "targetFrameworks": [t.strip() for t in tfms],
        "outputType": props.get("OutputType", ""),
        # IsTestProject comes from package props, which exist only after a restore: packages decide too.
        "isTestProject": _true(props.get("IsTestProject")) or bool(frameworks),
        "frameworks": frameworks,
        "cpm": _true(props.get("ManagePackageVersionsCentrally")),
        "packages": packages,
        "frameworkReferences": [{"id": i["Identity"], "implicit": _true(i.get("IsImplicitlyDefined"))}
                                for i in items.get("FrameworkReference", [])],
        "internalsVisibleTo": internals_visible_to(root, project),
    }


def runner_of(root: Path) -> str:
    """mtp when global.json selects Microsoft.Testing.Platform, else vstest."""
    try:
        data = json.loads((root / "global.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "vstest"
    test = data.get("test") if isinstance(data, dict) else None
    runner = test.get("runner") if isinstance(test, dict) else None
    return "mtp" if isinstance(runner, str) and runner.lower() == "microsoft.testing.platform" else "vstest"


def root_props(root: Path) -> dict:
    path = root / "Directory.Build.props"
    if not path.is_file():
        return {"exists": False, "treatWarningsAsErrors": None}
    match = re.search(r"<TreatWarningsAsErrors[^>]*>\s*(\w+)\s*<", path.read_text(encoding="utf-8", errors="replace"))
    return {"exists": True, "treatWarningsAsErrors": match[1].lower() if match else None}  # for the report only


def tfm_key(tfm: str):
    match = RUNNABLE_TFM.match(tfm)
    return (int(match[1]), int(match[2])) if match else None


def highest_runnable(tfms) -> str | None:
    runnable = [t for t in tfms if tfm_key(t)]
    return max(runnable, key=tfm_key) if runnable else None


def propose(root: Path, solution: str | None, projects: list[dict]) -> dict:
    tests = [p for p in projects if p["isTestProject"]]
    candidates = [p for p in projects if not p["isTestProject"] and p["outputType"].lower() == "library"]
    frameworks = sorted({f for p in tests for f in p["frameworks"]})
    framework = frameworks[0] if len(frameworks) == 1 else None
    framework_reason = None if framework else ("mixed test frameworks: " + ", ".join(frameworks) if frameworks
                                               else "no test project with a known test framework")
    stem = Path(solution).stem if solution else "App"
    if (root / "tests").is_dir() or not tests:
        ac_dir = f"tests/{stem}.AcceptanceTests"
    else:
        parent = str(Path(tests[0]["path"]).parent.parent.as_posix())
        ac_dir = f"{stem}.AcceptanceTests" if parent in (".", "") else f"{parent}/{stem}.AcceptanceTests"
    tfm, tfm_reason = None, None
    common = None
    for test in tests:
        runnable = {t for t in test["targetFrameworks"] if tfm_key(t)}
        common = runnable if common is None else common & runnable
    if common:
        tfm = highest_runnable(common)
    else:
        tfm = highest_runnable(t for p in candidates for t in p["targetFrameworks"])
        if tfm is None:
            tfm_reason = ("the surface candidates target only netstandard (or nothing runnable): ask which netX.Y the "
                          "AC test project should target")
    return {
        "acSurfaceProjects": [p["path"] for p in candidates],
        "unitTestProjects": [p["path"] for p in tests],
        "testFramework": framework,
        "testFrameworkReason": framework_reason,
        "acProjectDir": ac_dir,
        "refsDir": "artifacts/refs",
        "targetFramework": tfm,
        "targetFrameworkReason": tfm_reason,
    }


def supported(framework: str | None, runner: str) -> dict:
    pairs = init_config.supported_pairs()
    if framework is None:
        return {"pair": None, "supported": None, "supportedPairs": pairs}
    ok = (framework, runner) in init_config.RECIPES
    reason = None if ok else init_config.UNSUPPORTED.get((framework, runner), "not verified")
    return {"pair": f"{framework}/{runner}", "supported": ok, "reason": reason, "supportedPairs": pairs}


def blockers(root: Path, proposal: dict, projects: list[dict]) -> list[str]:
    out = []
    if (root / aclib.CONFIG).exists():
        out.append(f"{aclib.CONFIG} exists: the project is initialised (verify mode)")
    ac = root / proposal["acProjectDir"]
    if ac.exists() and any(ac.iterdir()):
        out.append(f"{proposal['acProjectDir']} exists and is not empty")
    for p in projects:
        if p["path"] in proposal["acSurfaceProjects"] and p["internalsVisibleTo"]:
            out.append(f"surface candidate {p['path']} uses InternalsVisibleTo ({', '.join(p['internalsVisibleTo'])}); "
                       "remove it, or leave the project out of the AC surface")
    return out


def detect(root: Path, solution: str | None, framework: str | None, runner=run) -> dict:
    found = solutions(root)
    if solution is None and len(found) == 1:
        solution = found[0]
    projects, ignored = [], []
    if solution is not None:
        if not (root / solution).is_file():
            raise aclib.AcError(f"solution {solution} not found")
        for path in sln_projects(root, solution, runner):
            if path.lower().endswith(".csproj"):
                projects.append(describe(root, path, evaluate(root, path, runner)))
            else:
                ignored.append(path)
    test_runner = runner_of(root)
    proposal = propose(root, solution, projects) if solution else None
    chosen = framework or (proposal["testFramework"] if proposal else None)
    return {
        "environment": environment(root),
        "solutions": found,
        "solution": solution,
        "runner": test_runner,
        "cpm": any(p["cpm"] for p in projects),
        "rootProps": root_props(root),
        "projects": projects,
        "ignored": ignored,
        "implementationFolders": init_config.implementation_folders(root),
        "proposal": proposal,
        "supported": supported(chosen, test_runner),
        "blockers": blockers(root, proposal, projects) if proposal else [],
    }


def main():
    parser = argparse.ArgumentParser(description="Detect the project's setup for /speckit-ac-init (JSON).")
    parser.add_argument("--solution")
    parser.add_argument("--framework", choices=aclib.ENUM_KEYS["testFramework"])
    args = parser.parse_args()
    root = aclib.root(__file__)
    print(json.dumps(detect(root, args.solution, args.framework), indent=2))


if __name__ == "__main__":
    aclib.run_main(main)
