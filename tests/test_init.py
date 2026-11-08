"""Tests for /speckit-ac-init's scripts (step 5): init_detect, init_config, init_scaffold, init_verify, smoke_test,
the managed blocks in aclib, and the export_refs fix.

Detection tests evaluate small hand-written solutions with `dotnet msbuild` (no restore, no network; skipped without
dotnet). Verification tests run init_verify with every dotnet call stubbed. The smoke tests check the smoke marker and
every listed action against the real guard. The real dotnet runs are in test_init_e2e.py (opt-in).
"""

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from acproject import AC, CONFIG, EXTENSION, PAYLOAD, make_project, run_guard, run_script, write
from initproject import csproj, make_solution, slnx

SCRIPTS = PAYLOAD / "scripts"
needs_dotnet = pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet not installed")
T, W, J = "ac-feature-translator", "ac-test-writer", "ac-test-fail-judge"
ALLOW, DENY = 0, 2


def load(name, folder=SCRIPTS):
    """Import a payload script as a module (no bytecode: a __pycache__ in the payload would be shipped)."""
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    sys.path.insert(0, str(folder))
    try:
        key = f"{name}_{abs(hash(str(folder)))}"
        spec = importlib.util.spec_from_file_location(key, folder / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module  # dataclasses look their module up there
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(folder))
        sys.dont_write_bytecode = previous
    return module


@pytest.fixture(scope="module")
def detect():
    return load("init_detect")


@pytest.fixture(scope="module")
def config():
    return load("init_config")


@pytest.fixture(scope="module")
def scaffold():
    return load("init_scaffold")


@pytest.fixture(scope="module")
def aclib():
    return load("aclib")


# ---- init_detect: pure parts --------------------------------------------------------------------------------------

@pytest.mark.parametrize("ids,expected", [
    (["xunit.v3", "Reqnroll"], ["xunit3"]), (["xunit.v3.mtp-off"], ["xunit3"]), (["xunit"], ["xunit2"]),
    (["xunit.core"], ["xunit2"]), (["NUnit", "NUnit3TestAdapter"], ["nunit"]), (["MSTest"], ["mstest"]),
    (["MSTest.TestFramework"], ["mstest"]), (["Newtonsoft.Json"], []), (["xunit", "NUnit"], ["nunit", "xunit2"]),
])
def test_framework_of(detect, ids, expected):
    assert detect.framework_of(ids) == expected


def env_project(tmp_path, options=None, claude=True, specs=()):
    root = tmp_path / "env"
    root.mkdir()
    if options is not None:
        write(root / ".specify/init-options.json", json.dumps(options))
    if claude:
        write(root / "CLAUDE.md")
    for name in specs:
        (root / "specs" / name).mkdir(parents=True)
    return root


def problems(detect, root, which=lambda tool: f"C:/bin/{tool}", system=lambda: "Windows", git=lambda r: True):
    return detect.environment(root, which=which, system=system, git=git)


def test_environment_ok(detect, tmp_path):
    assert problems(detect, env_project(tmp_path, {"script": "ps"}, specs=["001-a"])) == []


@pytest.mark.parametrize("case,setup,kwargs,needle", [
    ("linux", {"options": {"script": "ps"}}, {"system": lambda: "Linux"}, "Windows only"),
    ("no uv", {"options": {"script": "ps"}}, {"which": lambda t: None if t == "uv" else t}, "uv is not on PATH"),
    ("no pwsh", {"options": {"script": "ps"}}, {"which": lambda t: None if t == "pwsh" else t}, "pwsh is not"),
    ("no dotnet", {"options": {"script": "ps"}}, {"which": lambda t: None if t == "dotnet" else t}, "dotnet is not"),
    ("no init-options", {}, {}, "init-options.json is missing"),
    ("sh scripts", {"options": {"script": "sh"}}, {}, '"script": "sh"'),
    ("timestamp option", {"options": {"script": "ps", "feature_numbering": "timestamp"}}, {}, "timestamp feature numb"),
    ("timestamp folder", {"options": {"script": "ps"}, "specs": ["20260101-120000-x"]}, {}, "timestamp feature fold"),
    ("no CLAUDE.md", {"options": {"script": "ps"}, "claude": False}, {}, "CLAUDE.md is missing"),
    ("no git", {"options": {"script": "ps"}}, {"git": lambda r: False}, "not a git repository"),
])
def test_environment_problems(detect, tmp_path, case, setup, kwargs, needle):
    found = problems(detect, env_project(tmp_path, **setup), **kwargs)
    assert len(found) == 1 and needle in found[0], found


def test_runner_of(detect, tmp_path):
    assert detect.runner_of(tmp_path) == "vstest"
    write(tmp_path / "global.json", json.dumps({"sdk": {"version": "10.0.100"}}))
    assert detect.runner_of(tmp_path) == "vstest"
    write(tmp_path / "global.json", json.dumps({"test": {"runner": "Microsoft.Testing.Platform"}}))
    assert detect.runner_of(tmp_path) == "mtp"


def test_supported(detect):
    assert detect.supported("xunit3", "mtp")["supported"] is True
    unsupported = detect.supported("xunit2", "mtp")
    assert unsupported["supported"] is False and "no Microsoft.Testing.Platform runner" in unsupported["reason"]
    assert detect.supported(None, "vstest")["supported"] is None


def project_facts(path, tfms, output="Library", test=False, frameworks=(), ivt=()):
    return {"path": path, "targetFrameworks": list(tfms), "outputType": output, "isTestProject": test,
            "frameworks": list(frameworks), "internalsVisibleTo": list(ivt)}


def test_propose_target_framework(detect, tmp_path):
    lib = project_facts("src/A/A.csproj", ["net8.0", "net10.0"])
    tests = [project_facts("tests/T/T.csproj", ["net10.0", "net8.0"], test=True, frameworks=["nunit"]),
             project_facts("tests/U/U.csproj", ["net8.0"], test=True, frameworks=["nunit"])]
    assert detect.propose(tmp_path, "App.slnx", [lib, *tests])["targetFramework"] == "net8.0"  # what they share
    assert detect.propose(tmp_path, "App.slnx", [lib])["targetFramework"] == "net10.0"  # highest of the surface
    only_standard = detect.propose(tmp_path, "App.slnx", [project_facts("src/A/A.csproj", ["netstandard2.0"])])
    assert only_standard["targetFramework"] is None and "netstandard" in only_standard["targetFrameworkReason"]


def test_propose_framework_and_folder(detect, tmp_path):
    xunit = project_facts("test/X/X.csproj", ["net10.0"], test=True, frameworks=["xunit3"])
    nunit = project_facts("test/N/N.csproj", ["net10.0"], test=True, frameworks=["nunit"])
    mixed = detect.propose(tmp_path, "Shop.slnx", [xunit, nunit])
    assert mixed["testFramework"] is None and "mixed" in mixed["testFrameworkReason"]
    assert mixed["acProjectDir"] == "test/Shop.AcceptanceTests"  # next to the test projects: there is no tests/
    none = detect.propose(tmp_path, "Shop.slnx", [project_facts("src/A/A.csproj", ["net10.0"])])
    assert none["testFramework"] is None and none["acProjectDir"] == "tests/Shop.AcceptanceTests"
    (tmp_path / "tests").mkdir()
    assert detect.propose(tmp_path, "Shop.slnx", [xunit])["acProjectDir"] == "tests/Shop.AcceptanceTests"


def test_internals_visible_to_reads_any_encoding(detect, tmp_path):
    write(tmp_path / "src/A/A.csproj", "<Project />\n")
    (tmp_path / "src/A/Info.cs").write_bytes("// Gr\xfc\xdfe\n[assembly: InternalsVisibleTo(\"T\")]\n".encode("latin-1"))
    (tmp_path / "src/A/obj").mkdir()
    (tmp_path / "src/A/obj/Gen.cs").write_text("InternalsVisibleTo", encoding="utf-8")
    assert detect.internals_visible_to(tmp_path, "src/A/A.csproj") == ["src/A/Info.cs"]


# ---- init_detect: real msbuild evaluation --------------------------------------------------------------------------

def detect_json(project, *args):
    result = run_script(project, "init_detect.py", *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_dotnet
def test_detect_solution(tmp_path):
    project = make_solution(tmp_path / "p", "nunit", git=False)
    write(project / "src/App.Cli/App.Cli.csproj", csproj(properties={"OutputType": "Exe"}))
    write(project / "db/Db.sqlproj", "<Project />\n")
    write(project / "App.slnx", slnx(["src/App.Core/App.Core.csproj", "src/App.Cli/App.Cli.csproj",
                                      "tests/App.Tests/App.Tests.csproj", "db/Db.sqlproj"]))
    found = detect_json(project)
    assert found["solution"] == "App.slnx" and found["runner"] == "vstest" and found["cpm"] is False
    assert found["ignored"] == ["db/Db.sqlproj"]
    tests = next(p for p in found["projects"] if p["path"] == "tests/App.Tests/App.Tests.csproj")
    assert tests["isTestProject"] and tests["frameworks"] == ["nunit"]  # never restored: known by its packages
    assert {p["id"]: p["version"] for p in tests["packages"]}["NUnit"] == "1.0.0"
    proposal = found["proposal"]
    assert proposal["acSurfaceProjects"] == ["src/App.Core/App.Core.csproj"]  # not the exe, not the tests
    assert proposal["unitTestProjects"] == ["tests/App.Tests/App.Tests.csproj"]
    assert proposal["testFramework"] == "nunit" and proposal["targetFramework"] == "net10.0"
    assert proposal["acProjectDir"] == "tests/App.AcceptanceTests" and proposal["refsDir"] == "artifacts/refs"
    assert found["supported"]["supported"] is True and found["blockers"] == []
    assert {"src", "src/App.Core", "src/App.Cli", "tests/App.Tests"} <= set(found["implementationFolders"])
    assert detect_json(project, "--framework", "xunit2")["supported"]["pair"] == "xunit2/vstest"


@needs_dotnet
def test_detect_central_packages_and_mtp(tmp_path):
    project = make_solution(tmp_path / "p", "xunit3", "mtp", cpm=True, git=False)
    write(project / "Directory.Packages.props",
          "<Project>\n  <PropertyGroup>\n    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>\n"
          "  </PropertyGroup>\n  <ItemGroup>\n    <PackageVersion Include=\"xunit.v3\" Version=\"3.0.0\" />\n"
          "  </ItemGroup>\n</Project>\n")
    found = detect_json(project)
    assert found["runner"] == "mtp" and found["cpm"] is True
    tests = next(p for p in found["projects"] if p["isTestProject"])
    assert {p["id"]: p["version"] for p in tests["packages"]}["xunit.v3"] == "3.0.0"
    assert found["proposal"]["testFramework"] == "xunit3" and found["supported"]["supported"] is True


@needs_dotnet
def test_detect_blockers(tmp_path):
    project = make_solution(tmp_path / "p", "mstest", git=False)
    write(project / "src/App.Core/Friends.cs", "[assembly: System.Runtime.CompilerServices.InternalsVisibleTo(\"X\")]\n")
    write(project / "tests/App.AcceptanceTests/old.txt")
    write(project / ".workflow/config.json", "{}")
    blockers = detect_json(project)["blockers"]
    assert len(blockers) == 3
    assert any("config.json exists" in b for b in blockers)
    assert any("tests/App.AcceptanceTests exists and is not empty" in b for b in blockers)
    assert any("src/App.Core/App.Core.csproj uses InternalsVisibleTo (src/App.Core/Friends.cs)" in b for b in blockers)


@needs_dotnet
def test_detect_several_solutions(tmp_path):
    project = make_solution(tmp_path / "p", git=False)
    shutil.copyfile(project / "App.slnx", project / "Other.slnx")
    found = detect_json(project)
    assert found["solution"] is None and found["solutions"] == ["App.slnx", "Other.slnx"] and found["proposal"] is None
    assert detect_json(project, "--solution", "Other.slnx")["proposal"]["acProjectDir"] == "tests/Other.AcceptanceTests"


# ---- init_config ---------------------------------------------------------------------------------------------------

def config_args(**overrides):
    values = {"solution": "App.slnx", "surface": ["src/App.Core/App.Core.csproj"],
              "unit_tests": ["tests/App.Tests/App.Tests.csproj"], "ac_project_dir": "tests/App.AcceptanceTests",
              "refs_dir": "artifacts/refs", "spec_input": [], "framework": "xunit3", "runner": "mtp"}
    values.update(overrides)
    return argparse.Namespace(**values)


def test_recipes_cover_seven_pairs(config):
    assert len(config.RECIPES) == 7 and ("xunit2", "mtp") not in config.RECIPES
    assert set(config.UNSUPPORTED) == {("xunit2", "mtp")}


@pytest.mark.parametrize("pair", sorted(load("init_config").RECIPES))
def test_config_per_recipe(config, aclib, tmp_path, pair):
    framework, runner = pair
    cfg = config.build(config_args(framework=framework, runner=runner), tmp_path)
    assert aclib.validate_config(dict(cfg)) == cfg
    assert cfg["acProject"] == "tests/App.AcceptanceTests/App.AcceptanceTests.csproj"
    assert cfg["python"] == "uv run --no-project python -I" and cfg["testFramework"] == framework
    assert cfg["acRefBuildCommand"] == f"dotnet build {cfg['acProject']} -p:AcRefMode=true -nologo -v q"
    for token in ("{acProject}", "{analyzeDir}", "ac-results.trx", "--no-build", "--results-directory {analyzeDir}"):
        assert token in cfg["acTestCommand"]
    if runner == "mtp":
        assert cfg["unitTestCommand"] == "dotnet test --project {project}"
        assert cfg["acTestCommand"].startswith("dotnet test --project {acProject} ")
    else:
        assert cfg["unitTestCommand"] == "dotnet test {project}"
        assert cfg["acTestCommand"].endswith('--logger "trx;LogFileName=ac-results.trx"')


def test_config_xunit2_on_mtp_is_refused(config, tmp_path):
    with pytest.raises(Exception, match=r"xunit2 on mtp is not supported .*Supported: xunit2/vstest"):
        config.build(config_args(framework="xunit2"), tmp_path)


@pytest.mark.parametrize("spec_input,ok", [
    ("docs/domain", True), ("src", False), ("src/App.Core", False), ("src/App.Core/Docs", False), ("tests", False),
    (".", False), ("../outside", False), ("specs", False),
])
def test_config_spec_inputs(config, tmp_path, spec_input, ok):
    write(tmp_path / "src/App.Core/App.Core.csproj", "<Project />\n")
    write(tmp_path / "tests/App.Tests/App.Tests.csproj", "<Project />\n")
    args = config_args(spec_input=[spec_input])
    if ok:
        assert config.build(args, tmp_path)["specInputs"] == [spec_input]
    else:
        with pytest.raises(Exception):
            config.build(args, tmp_path)


@pytest.mark.parametrize("override", [{"ac_project_dir": "tests/My App.AcceptanceTests"},
                                      {"refs_dir": "artifacts/my refs"},
                                      {"unit_tests": ["tests/My Tests/My Tests.csproj"]}])
def test_config_rejects_whitespace(config, tmp_path, override):
    with pytest.raises(Exception, match="whitespace"):
        config.build(config_args(**override), tmp_path)


def test_config_script_writes_once(tmp_path):
    project = make_project(tmp_path / "p", config=None)
    args = ["--solution", "App.slnx", "--surface", "src/App.Core/App.Core.csproj", "--ac-project-dir",
            "tests/App.AcceptanceTests", "--framework", "nunit", "--runner", "vstest", "--spec-input", "docs/domain"]
    first = run_script(project, "init_config.py", *args)
    assert first.returncode == 0, first.stderr
    written = json.loads((project / ".workflow/config.json").read_text(encoding="utf-8"))
    assert written["specInputs"] == ["docs/domain"] and written["unitTestProjects"] == []
    again = run_script(project, "init_config.py", *args)
    assert again.returncode == 1 and "never overwritten" in again.stderr


# ---- init_scaffold -------------------------------------------------------------------------------------------------

def scaffold_config(framework="xunit3", runner="mtp", **extra):
    cfg = dict(CONFIG, testFramework=framework, **extra)
    return cfg


@pytest.mark.parametrize("pair", sorted(load("init_config").RECIPES))
def test_render(scaffold, config, pair):
    framework, runner = pair
    files = scaffold.render(scaffold_config(framework, runner), "net9.0", runner, ["Microsoft.AspNetCore.App"])
    project = files[f"{AC}/App.AcceptanceTests.csproj"]
    assert "<TargetFramework>net9.0</TargetFramework>" in project
    for key, value in config.RECIPES[pair]["properties"].items():
        assert f"<{key}>{value}</{key}>" in project
    assert f'<Using Include="{config.ASSERT_NAMESPACE[framework]}" />' in project
    assert '<Using Include="Reqnroll" />' in project
    assert "<ReqnrollUseIntermediateOutputPathForCodeBehind>true</ReqnrollUseIntermediateOutputPathForCodeBehind>" \
        in project
    assert '<None Include="Samples/**" CopyToOutputDirectory="PreserveNewest" />' in project
    assert ("<ItemGroup Condition=\"'$(AcRefMode)' == 'true'\">\n    <Reference Include=\"$(MSBuildThisFileDirectory)"
            "../../artifacts/refs/*.dll\" Private=\"false\" />") in project
    assert ("<ItemGroup Condition=\"'$(AcRefMode)' != 'true'\">\n    <ProjectReference "
            "Include=\"../../src/App.Core/App.Core.csproj\" />") in project
    assert '<FrameworkReference Include="Microsoft.AspNetCore.App" />' in project
    assert "{{" not in project
    props = files[f"{AC}/Directory.Build.props"]
    assert "GetPathOfFileAbove('Directory.Build.props', '$(MSBuildThisFileDirectory)../')" in props
    assert "Condition=\"'$(_AcParentBuildProps)' != ''\"" in props
    assert "<BaseIntermediateOutputPath>obj-ref\\</BaseIntermediateOutputPath>" in props
    assert "<DefaultItemExcludes>$(DefaultItemExcludes);bin/**;obj/**;bin-ref/**;obj-ref/**</DefaultItemExcludes>" in props
    assert json.loads(files[f"{AC}/reqnroll.json"])["runtime"]["missingOrPendingStepsOutcome"] == "Error"
    assert sorted(p for p in files if p.endswith(".gitkeep")) == sorted(
        f"{AC}/{f}/.gitkeep" for f in ("Features", "Samples", "StepDefinitions", "Support/Shared"))


def test_render_without_framework_references(scaffold):
    project = scaffold.render(scaffold_config(), "net10.0", "mtp", [])[f"{AC}/App.AcceptanceTests.csproj"]
    assert "FrameworkReference" not in project


def facts(*packages, refs=()):
    return {"packages": [{"id": i, "version": v, "privateAssets": pa, "implicit": imp} for i, v, pa, imp in packages],
            "frameworkReferences": [{"id": r, "implicit": imp} for r, imp in refs]}


def test_packages_order_and_filters(scaffold):
    surface = [facts(("Newtonsoft.Json", "13.0.1", "", False), ("StyleCop.Analyzers", "1.1", "all", False),
                     ("Microsoft.NET.ILLink.Tasks", "10.0.0", "", True), ("xunit.v3", "2.0.0", "", False),
                     refs=[("Microsoft.AspNetCore.App", False), ("Microsoft.NETCore.App", True)])]
    wanted, notes = scaffold.packages("xunit3", "mtp", surface, [], cpm=False)
    assert [p for p, _ in wanted] == ["xunit.v3", "Reqnroll.xunit.v3", "Microsoft.Extensions.TimeProvider.Testing",
                                      "Newtonsoft.Json"]
    assert dict(wanted) == {"xunit.v3": "2.0.0", "Reqnroll.xunit.v3": None,
                            "Microsoft.Extensions.TimeProvider.Testing": None, "Newtonsoft.Json": "13.0.1"}
    assert notes == [] and scaffold.framework_references(surface) == ["Microsoft.AspNetCore.App"]


def test_packages_versions(scaffold):
    surface = [facts(("Polly", "8.0.0", "", False)), facts(("Polly", "8.4.1", "", False))]
    unit = [facts(("NUnit", "4.1.0", "", False), ("Polly", "7.0.0", "", False)), facts(("NUnit", "4.3.2", "", False))]
    wanted, notes = scaffold.packages("nunit", "vstest", surface, unit, cpm=False)
    versions = dict(wanted)
    assert versions["Polly"] == "8.4.1" and versions["NUnit"] == "4.3.2" and versions["NUnit3TestAdapter"] is None
    assert any(n.startswith("Polly: the surface use 8.0.0, 8.4.1; using 8.4.1") for n in notes)
    central, _ = scaffold.packages("nunit", "vstest", surface, unit, cpm=True)
    assert all(version is None for _, version in central)  # central pins decide


def test_ilspy_installed(scaffold, aclib):
    table = "Package Id      Version      Commands      Manifest\n-------\nilspycmd   11.2.0.10050   ilspycmd   x\n"
    assert scaffold.ilspy_installed(Path("."), runner=lambda args, cwd: table)
    assert not scaffold.ilspy_installed(Path("."), runner=lambda args, cwd: "Package Id\n-----\n")

    def no_manifest(args, cwd):
        raise scaffold.aclib.AcError("no manifest")
    assert not scaffold.ilspy_installed(Path("."), runner=no_manifest)


def test_scaffold_refuses_a_non_empty_folder(tmp_path):
    project = make_project(tmp_path / "p")  # its AC folder already has files
    result = run_script(project, "init_scaffold.py", "--target-framework", "net10.0")
    assert result.returncode == 1 and "is never overwritten" in result.stderr


# ---- managed blocks ------------------------------------------------------------------------------------------------

def test_block_in_a_new_file(aclib, tmp_path):
    path = tmp_path / ".gitignore"
    assert aclib.write_block(path, ["/a/", "/b/"])
    assert path.read_bytes() == f"{aclib.BLOCK_BEGIN}\n/a/\n/b/\n{aclib.BLOCK_END}\n".encode()
    assert not aclib.write_block(path, ["/a/", "/b/"])  # unchanged
    assert aclib.remove_block(path) and path.read_bytes() == b""


@pytest.mark.parametrize("original", ["bin/\nobj/\n", "bin/\nobj/", "bin/\r\nobj/\r\n", "* text=auto\n\n# end\n"])
def test_block_keeps_the_rest(aclib, tmp_path, original):
    path = tmp_path / "file"
    path.write_bytes(original.encode())
    assert aclib.write_block(path, ["x"])
    text = path.read_bytes().decode()
    newline = "\r\n" if "\r\n" in original else "\n"
    assert text.startswith(original) and text.endswith(f"{aclib.BLOCK_BEGIN}{newline}x{newline}{aclib.BLOCK_END}{newline}")
    assert text.count(aclib.BLOCK_BEGIN) == 1
    aclib.write_block(path, ["y", "z"])  # replaced in place, no duplicate
    text = path.read_bytes().decode()
    assert text.count(aclib.BLOCK_BEGIN) == 1 and f"y{newline}z" in text and f"{newline}x{newline}" not in text
    path.write_bytes((text + "after\n").encode())
    aclib.write_block(path, ["w"])
    assert path.read_bytes().decode().endswith(f"{aclib.BLOCK_END}{newline}after\n")
    assert aclib.remove_block(path)
    rest = path.read_bytes().decode()
    assert aclib.BLOCK_BEGIN not in rest and rest.startswith(original.rstrip("\r\n")) and rest.endswith("after\n")


def test_remove_block_restores_an_appended_file(aclib, tmp_path):
    path = tmp_path / "file"
    path.write_bytes(b"bin/\n")
    aclib.write_block(path, ["x"])
    assert aclib.remove_block(path) and path.read_bytes() == b"bin/\n"
    assert not aclib.remove_block(path) and not aclib.remove_block(tmp_path / "missing")


# ---- init_verify (dotnet stubbed) ----------------------------------------------------------------------------------

def git_project(tmp_path):
    project = make_project(tmp_path / "p")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "i"]):
        subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)
    return project


def verifier(project):
    module = load("init_verify", project / EXTENSION / "scripts")
    cfg = json.loads((project / ".workflow/config.json").read_text(encoding="utf-8"))
    return module, module.Verify(project, cfg)


def fake_dotnet(module, project, monkeypatch, handler):
    """Route every dotnet call of init_verify through `handler(args) -> (code, output) | None` (None: success)."""
    real = module.run
    calls = []

    def run(args, cwd):
        if args[0] != "dotnet":
            return real(args, cwd)
        calls.append(args)
        outcome = handler(args) or (0, "")
        return subprocess.CompletedProcess(args, outcome[0], outcome[1], "")
    monkeypatch.setattr(module, "run", run)
    return calls


def test_verify_refuses_existing_temporary_paths(tmp_path):
    for leftover in ("specs/999-old/spec.md", f"{AC}/Features/F999/x.feature"):
        project = make_project(tmp_path / leftover.split("/")[0] / "p")
        write(project / leftover)
        result = run_script(project, "init_verify.py")
        assert result.returncode == 1 and "already exist" in result.stderr
        assert (project / leftover).is_file()  # nothing deleted


def test_verify_stops_after_a_failed_build(tmp_path, monkeypatch, capsys):
    project = git_project(tmp_path)
    module, verify = verifier(project)

    def handler(args):
        if args[:2] == ["dotnet", "build"]:
            return 1, "Program.cs(3,1): error CS1002: ; expected [App.csproj]\nBuild FAILED.\n"
    fake_dotnet(module, project, monkeypatch, handler)
    assert verify.run_all() is False
    out = capsys.readouterr().out
    assert "FAIL [1] dotnet build App.slnx\n    Program.cs(3,1): error CS1002: ; expected [App.csproj]" in out
    assert "[3]" not in out and "[9]" not in out  # no temporary files, no tree check
    assert not (project / "specs/999-speckit-ac-check").exists()


def test_verify_cleans_up_after_failures(tmp_path, monkeypatch, capsys):
    """Builds pass (one writes packages.lock.json, before the snapshot); the export fails; everything temporary
    is removed and the tree check passes."""
    project = git_project(tmp_path)
    module, verify = verifier(project)
    lock_file = project / "src/App.Core/packages.lock.json"

    def handler(args):
        if args[:3] == ["dotnet", "build", "App.slnx"]:
            write(lock_file, "{}\n")
        if args[:3] == ["dotnet", "tool", "restore"]:
            return 1, "error NU1101: Unable to find package ilspycmd\n"
        if args[:2] == ["dotnet", "msbuild"]:
            return 0, json.dumps({"Properties": {"TreatWarningsAsErrors": ""}})
    fake_dotnet(module, project, monkeypatch, handler)
    assert verify.run_all() is False
    out = capsys.readouterr().out
    assert "PASS [3] ac_lock.py" in out  # the real lock script on the temporary feature
    assert "FAIL [4] dotnet tool restore (ilspycmd)\n    error NU1101" in out
    assert "PASS [6] check_features.py" in out  # the real feature check, valid and broken variants
    assert "FAIL [7] acTestCommand writes .workflow/init-check/analyze/ac-results.trx" in out
    assert "PASS [9] no leftovers" in out
    for path in ("specs/999-speckit-ac-check", f"{AC}/Features/F999", f"{AC}/Samples/F999",
                 f"{AC}/StepDefinitions/F999", ".workflow/init-check"):
        assert not (project / path).exists(), path


def test_verify_reports_leftovers(tmp_path, monkeypatch, capsys):
    project = git_project(tmp_path)
    module, verify = verifier(project)

    def handler(args):
        if args[:3] == ["dotnet", "build", CONFIG["acRefBuildCommand"].split()[2]] and "-p:AcRefMode=true" in args:
            write(project / "src/App.Core/Generated.cs", "// written by a build\n")
    fake_dotnet(module, project, monkeypatch, handler)
    verify.run_all()
    out = capsys.readouterr().out
    assert "FAIL [9] no leftovers" in out and "src/App.Core/Generated.cs" in out


@pytest.mark.parametrize("props,expected", [
    ({"TreatWarningsAsErrors": "false"}, "SKIP [5] warnings-as-errors check: TreatWarningsAsErrors is not set"),
    ({"TreatWarningsAsErrors": "true", "NoWarn": "1701;CS0168"}, "SKIP [5] warnings-as-errors check: CS0168 is listed in NoWarn"),
    ({"TreatWarningsAsErrors": "true", "WarningsNotAsErrors": "CS0168"}, "listed in WarningsNotAsErrors"),
    ({"TreatWarningsAsErrors": "true"}, "PASS [5] root Directory.Build.props applies in ref mode"),
])
def test_verify_warnings_as_errors(tmp_path, monkeypatch, capsys, props, expected):
    project = git_project(tmp_path)
    module, verify = verifier(project)
    seen = []

    def handler(args):
        if args[:2] == ["dotnet", "msbuild"]:
            return 0, json.dumps({"Properties": props})
        if "-p:AcRefMode=true" in args:
            seen.append(verify.warning.is_file())
            return 1, "AcInitCheckWarning.cs(7,13): error CS0168: The variable 'unused' is declared but never used\n"
    fake_dotnet(module, project, monkeypatch, handler)
    verify.warnings_as_errors()
    assert expected in capsys.readouterr().out
    assert seen == ([True] if expected.startswith("PASS") else [])
    assert not verify.warning.exists()


# ---- smoke_test ----------------------------------------------------------------------------------------------------

SMOKE = "specs/999-speckit-ac-smoke"


@pytest.fixture
def smoke():
    return load("smoke_test")


def smoke_start(project, role):
    result = run_script(project, "smoke_test.py", "start", role)
    assert result.returncode == 0, result.stderr
    return result.stdout.rstrip("\n")


@pytest.mark.parametrize("role,run,analyze", [(T, "translate-001", None), (W, "run-001", None),
                                              (J, "run-001", "analyze-1")])
def test_smoke_start_writes_the_marker(tmp_path, smoke, role, run, analyze):
    project = make_project(tmp_path / "p")
    prompt = smoke_start(project, role)
    marker = json.loads((project / ".workflow/active-run.json").read_text(encoding="utf-8"))
    assert marker == {"role": role, "feature": SMOKE, "tag": "F999", "run": run, "analyze": analyze,
                      "taskMessage": prompt, "smoke": True, "smokeLogLines": 0}
    assert prompt == smoke.prompt(role, CONFIG) and prompt.startswith("SMOKE TEST")
    assert (project / SMOKE / "ac/runs" / run / (analyze or "")).is_dir()


@pytest.mark.parametrize("role", [T, W, J])
def test_smoke_actions_match_the_real_guard(tmp_path, smoke, role):
    project = make_project(tmp_path / "p")
    prompt = smoke_start(project, role)
    launch = {"tool_name": "Agent", "hook_event_name": "PreToolUse", "cwd": str(project),
              "tool_input": {"description": "smoke", "prompt": prompt, "subagent_type": role,
                             "run_in_background": False}}
    assert run_guard(project, launch) == (ALLOW, "")
    changed = dict(launch, tool_input=dict(launch["tool_input"], prompt=prompt + "\nAlso read src/."))
    assert run_guard(project, changed)[0] == DENY
    for label, tool, tool_input, decision in smoke.actions(role, CONFIG):
        payload = {"tool_name": tool, "hook_event_name": "PreToolUse", "cwd": str(project), "agent_type": role,
                   "tool_input": tool_input}
        code, reason = run_guard(project, payload)
        assert code == (ALLOW if decision == "allow" else DENY), (label, reason)
    handback = {"tool_name": "SubagentHandback", "cwd": str(project), "agent_type": role,
                "tool_input": {"message": "1 blocked, 2 allowed"}}
    assert run_guard(project, handback)[0] == ALLOW


def log_for(role, smoke, extra=(), drop=None):
    lines = []
    for _, tool, _, decision in smoke.actions(role, CONFIG):
        lines.append(f"{role}\t{tool}\t{decision}")
    lines.append(f"{role}\tSubagentHandback\tallow")
    if drop:
        lines.remove(drop)
    return lines + list(extra)


@pytest.mark.parametrize("case,lines,code,needle", [
    ("all present", lambda s: log_for(T, s), 0, "Smoke test ac-feature-translator: PASS"),
    ("extra read", lambda s: log_for(T, s, [f"{T}\tRead\tallow"]), 0, "info: Read allow logged 2x"),
    ("missing deny", lambda s: log_for(T, s, drop=f"{T}\tWrite\tdeny"), 1, "MISSING: Write deny"),
    ("no hand-back", lambda s: log_for(T, s, drop=f"{T}\tSubagentHandback\tallow"), 1, "MISSING: SubagentHandback"),
    ("write allowed", lambda s: log_for(T, s, [f"{T}\tWrite\tallow"]), 1, "UNEXPECTED: Write allow"),
    ("other role's lines", lambda s: [f"{W}\t{t}\t{d}" for t, d in [("Read", "deny")]] + log_for(T, s), 0, "PASS"),
])
def test_smoke_end_evaluates_the_log(tmp_path, smoke, case, lines, code, needle):
    project = make_project(tmp_path / "p")
    write(project / ".workflow/guard.log", "main-era line\tRead\tallow\n")
    smoke_start(project, T)
    with open(project / ".workflow/guard.log", "a", encoding="utf-8") as log:
        log.write("\n".join(lines(smoke)) + "\n")
    result = run_script(project, "smoke_test.py", "end", T)
    assert result.returncode == code and needle in result.stdout, result.stdout
    assert not (project / ".workflow/active-run.json").exists() and not (project / SMOKE).exists()


def test_smoke_end_without_or_with_a_foreign_marker(tmp_path):
    project = make_project(tmp_path / "p")
    write(project / SMOKE / "spec.md")
    result = run_script(project, "smoke_test.py", "end", T)
    assert result.returncode == 1 and "nothing to evaluate" in result.stdout and not (project / SMOKE).exists()
    foreign = json.dumps({"role": W, "feature": "specs/001-alpha", "tag": "F001", "run": "run-001", "analyze": None})
    write(project / ".workflow/active-run.json", foreign)
    result = run_script(project, "smoke_test.py", "end", W)
    assert result.returncode == 1 and "not a smoke-test marker" in result.stdout
    assert (project / ".workflow/active-run.json").read_text(encoding="utf-8") == foreign  # left alone


def test_smoke_start_refusals(tmp_path):
    project = make_project(tmp_path / "p")
    write(project / ".workflow/active-run.json", "{}")
    result = run_script(project, "smoke_test.py", "start", T)
    assert result.returncode == 1 and "delete that file by hand" in result.stderr
    (project / ".workflow/active-run.json").unlink()
    write(project / "specs/999-other/spec.md")
    result = run_script(project, "smoke_test.py", "start", T)
    assert result.returncode == 1 and "needs feature number 999" in result.stderr
    assert run_script(project, "smoke_test.py", "start", "main").returncode == 1


def test_smoke_isolation_file(tmp_path):
    project = make_project(tmp_path / "p")
    result = run_script(project, "smoke_test.py", "isolation-file", "create")
    assert result.stdout.strip() == f"{AC}/StepDefinitions/smoke-test.txt"
    assert (project / AC / "StepDefinitions/smoke-test.txt").is_file()
    read = {"tool_name": "Read", "hook_event_name": "PreToolUse", "cwd": str(project),
            "tool_input": {"file_path": str(project / result.stdout.strip())}}
    assert run_guard(project, read)[0] == DENY  # the main agent's manual check
    run_script(project, "smoke_test.py", "isolation-file", "delete")
    assert not (project / AC / "StepDefinitions/smoke-test.txt").exists()


# ---- export_refs fix (R11) ----------------------------------------------------------------------------------------

def test_export_refs_msbuild_json(monkeypatch):
    module = load("export_refs")
    seen = []
    monkeypatch.setattr(module, "run", lambda *args: seen.append(args) or '{"Properties": {"TargetRefPath": "x"}}')
    assert module.msbuild_json("App.csproj", "-getProperty:TargetRefPath") == {"Properties": {"TargetRefPath": "x"}}
    assert seen == [("dotnet", "msbuild", "App.csproj", "-p:Configuration=Debug", "-getProperty:TargetRefPath")]
