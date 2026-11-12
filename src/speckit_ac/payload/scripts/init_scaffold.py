"""Create the AC test project for /speckit-ac-init from .workflow/config.json (docs/WORKFLOW.md, setup).

Usage: init_scaffold.py --target-framework net10.0
Writes <acProjectDir>/ (csproj, Directory.Build.props, reqnroll.json, xunit.runner.json for xUnit, Features/
Samples/ StepDefinitions/ Support/Shared/ with .gitkeep) from the extension's templates/ac-project/, adds the packages with
`dotnet add package` (central package management adds the pins), installs the local tool ilspycmd, and writes the
managed blocks in .gitignore and .gitattributes. Never adds the AC project to the solution. Packages: the
(framework, runner) recipe of init_config.py, the Reqnroll adapter, Microsoft.Extensions.TimeProvider.Testing, and
every package of the surface projects that is not implicit or PrivateAssets=all (their public types must compile in
ref mode). Versions: central pins; else the surface's version, then the unit tests' (highest when several); else
the latest stable. On failure the AC folder is removed again (or emptied again, if it existed empty before) and the
other files changed so far are listed.
"""
import argparse
import hashlib
import posixpath
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402
import init_config  # noqa: E402
import init_detect  # noqa: E402

TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "ac-project"
TIME_PROVIDER = "Microsoft.Extensions.TimeProvider.Testing"
FOLDERS = ("Features", "Samples", "StepDefinitions", "Support/Shared")
# xUnit is the only supported framework that runs test collections (Reqnroll: one per feature) in parallel by default.
# Acceptance scenarios usually share one test environment (a database, files), so they run one collection at a time,
# as NUnit and MSTest do by default (Copilot on HT PR 16). A project that wants parallel runs edits the file.
XUNIT = ("xunit2", "xunit3")
XUNIT_RUNNER_ITEM = ("    <!-- Test collections run one at a time: scenarios usually share one test environment. -->\n"
                     '    <None Include="xunit.runner.json" CopyToOutputDirectory="PreserveNewest" />\n')
WATCHED = ("Directory.Packages.props", "dotnet-tools.json", ".config/dotnet-tools.json", ".gitignore",
           ".gitattributes")


version_key = init_detect.version_key
highest = init_detect.highest


def packages(framework: str, runner: str, surface: list[dict], unit_tests: list[dict], cpm: bool):
    """[(package id, version or None)] in install order, and notes about version choices."""
    rec = init_config.recipe(framework, runner)
    wanted = [*rec["packages"], init_config.ADAPTER[framework], TIME_PROVIDER]
    for project in surface:
        wanted += [p["id"] for p in project["packages"] if init_detect.public_package(p)]
    seen, out, notes = set(), [], []
    for pid in wanted:
        if pid.lower() in seen:
            continue
        seen.add(pid.lower())
        if cpm:
            out.append((pid, None))
            continue
        for source, projects in (("surface", surface), ("unit tests", unit_tests)):
            versions = {p["version"] for proj in projects for p in proj["packages"]
                        if p["id"].lower() == pid.lower() and p["version"]}
            if versions:
                chosen = highest(versions)
                if len(versions) > 1:
                    notes.append(f"{pid}: the {source} use {', '.join(sorted(versions, key=version_key))}; "
                                 f"using {chosen}")
                out.append((pid, chosen))
                break
        else:
            out.append((pid, None))
    return out, notes


def framework_references(surface: list[dict]) -> list[str]:
    refs = []
    for project in surface:
        for ref in project["frameworkReferences"]:
            if not ref["implicit"] and ref["id"] not in refs:
                refs.append(ref["id"])
    return refs


def render(cfg: dict, target_framework: str, runner: str, framework_refs: list[str]) -> dict:
    """{project-relative path: text} of every file the scaffold writes into the AC project folder."""
    ac, framework = cfg["acProjectDir"], cfg["testFramework"]
    rec = init_config.recipe(framework, runner)
    properties = "".join(f"    <{k}>{v}</{k}>\n" for k, v in rec["properties"].items())
    fw_refs = ("\n  <ItemGroup>\n" + "".join(f'    <FrameworkReference Include="{r}" />\n' for r in framework_refs)
               + "  </ItemGroup>") if framework_refs else ""
    project_refs = "".join(f'    <ProjectReference Include="{posixpath.relpath(p, ac)}" />\n'
                           for p in cfg["acSurfaceProjects"])
    values = {
        "TARGET_FRAMEWORK": target_framework,
        "PROPERTIES": properties,
        "ASSERT_NAMESPACE": init_config.ASSERT_NAMESPACE[framework],
        "FRAMEWORK_REFERENCES": fw_refs,
        "REFS_DIR": posixpath.relpath(cfg["refsDir"], ac),
        "PROJECT_REFERENCES": project_refs,
        "RUNNER_CONFIG": XUNIT_RUNNER_ITEM if framework in XUNIT else "",
    }

    def fill(name):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        if "{{" in text:
            raise aclib.AcError(f"{name}: unfilled placeholder {re.search(r'{{[A-Z_]+}}', text)[0]}")
        return text

    files = {
        cfg["acProject"]: fill("AcceptanceTests.csproj.template"),
        f"{ac}/Directory.Build.props": fill("Directory.Build.props.template"),
        f"{ac}/reqnroll.json": (TEMPLATES / "reqnroll.json").read_text(encoding="utf-8"),
    }
    if framework in XUNIT:
        files[f"{ac}/xunit.runner.json"] = (TEMPLATES / "xunit.runner.json").read_text(encoding="utf-8")
    files.update({f"{ac}/{folder}/.gitkeep": "" for folder in FOLDERS})
    return files


def gitignore_lines(cfg: dict) -> list[str]:
    return [f"/{cfg['refsDir']}/", "**/bin-ref/", "**/obj-ref/", "/.workflow/guard.log", "/.workflow/active-run.json",
            "/.specify/extensions/ac/**/__pycache__/"]


def gitattributes_lines(cfg: dict) -> list[str]:
    ac = cfg["acProjectDir"]
    return [f"{ac}/Samples/** binary", f"{ac}/Features/**/*.feature text eol=lf", "specs/*/acceptance.md text eol=lf",
            "specs/*/spec.md text eol=lf"]


def ilspy_installed(root: Path, runner=init_detect.run) -> bool:
    try:
        listing = runner(["dotnet", "tool", "list", "--local"], root)
    except aclib.AcError:
        return False  # no tool manifest yet
    return any(line.split()[0].lower() == "ilspycmd" for line in listing.splitlines() if line.strip())


def fingerprint(root: Path) -> dict:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() if (root / name).is_file() else None
            for name in WATCHED}


def changes(before: dict, after: dict) -> list[str]:
    return [f"{'created' if before[n] is None else 'changed'}: {n}" for n in WATCHED if before[n] != after[n]]


def main():
    parser = argparse.ArgumentParser(description="Create the AC test project from .workflow/config.json.")
    parser.add_argument("--target-framework", required=True, help="the TFM confirmed by the user, e.g. net10.0")
    args = parser.parse_args()
    root = aclib.root(__file__)
    cfg = aclib.load_config(root)
    runner = init_detect.runner_of(root)
    ac = root / cfg["acProjectDir"]
    if ac.exists() and (not ac.is_dir() or any(ac.iterdir())):
        raise aclib.AcError(f"{cfg['acProjectDir']} exists and is not empty; it is never overwritten.")
    describe = lambda p: init_detect.describe(root, p, init_detect.evaluate(root, p))  # noqa: E731
    surface = [describe(p) for p in cfg["acSurfaceProjects"]]
    unit_tests = [describe(p) for p in cfg["unitTestProjects"]]
    cpm = any(p["cpm"] for p in surface + unit_tests) or (root / "Directory.Packages.props").is_file()
    wanted, notes = packages(cfg["testFramework"], runner, surface, unit_tests, cpm)
    files = render(cfg, args.target_framework, runner, framework_references(surface))

    before, created_folder = fingerprint(root), not ac.exists()
    try:
        for rel, text in files.items():
            aclib.write_text(root / rel, text)
        for pid, version in wanted:
            init_detect.run(["dotnet", "add", cfg["acProject"], "package", pid,
                             *(["--version", version] if version else [])], root)
        if not ilspy_installed(root):
            init_detect.run(["dotnet", "tool", "install", "ilspycmd", "--create-manifest-if-needed"], root)
        aclib.write_block(root / ".gitignore", gitignore_lines(cfg))
        aclib.write_block(root / ".gitattributes", gitattributes_lines(cfg))
    except (aclib.AcError, OSError):
        # The folder was absent or empty before (checked above), so everything in it is this run's.
        shutil.rmtree(ac, ignore_errors=True)
        if not created_folder:
            ac.mkdir(parents=True, exist_ok=True)
        for line in changes(before, fingerprint(root)):
            print(line)
        state = "removed again" if created_folder else "emptied again, as it was before"
        print(f"The AC project folder {cfg['acProjectDir']} was {state}; review the files listed above.")
        raise

    for rel in files:
        print(f"created: {rel}")
    for line in changes(before, fingerprint(root)):
        print(line)
    print("packages: " + ", ".join(f"{pid} {version}" if version else pid for pid, version in wanted))
    for note in notes:
        print(f"note: {note}")


if __name__ == "__main__":
    aclib.run_main(main)
