"""End-to-end runs of /speckit-ac-init's scripts against real .NET solutions (step 5, S05-R12). Opt-in.

Each supported (framework, runner) pair: a git repository with a class library and a unit test project of that
recipe (real packages from NuGet), then init_detect -> init_config -> init_scaffold -> init_verify, as the command
runs them. Every verification line must be PASS or SKIP. xunit2 on Microsoft.Testing.Platform must be refused.
Needs dotnet, git and network access; takes minutes. Run with SPECKIT_AC_DOTNET_E2E=1.
"""

import json
import os
import shutil
import sys

import pytest

from acproject import EXTENSION
from initproject import HOST_PROJECT, make_host_solution, make_solution, run

pytestmark = pytest.mark.skipif(os.environ.get("SPECKIT_AC_DOTNET_E2E") != "1" or shutil.which("dotnet") is None,
                                reason="opt-in: SPECKIT_AC_DOTNET_E2E=1 and dotnet on PATH")

# (framework, runner, variant): "cpm" = central package management, "twae" = root props with TreatWarningsAsErrors.
PAIRS = [("xunit2", "vstest", ""), ("xunit3", "vstest", ""), ("xunit3", "mtp", "twae"), ("nunit", "vstest", ""),
         ("nunit", "mtp", ""), ("mstest", "vstest", ""), ("mstest", "mtp", "cpm")]


def script(project, name, *args, check=True):
    return run([sys.executable, "-I", str(project / EXTENSION / "scripts" / name), *args], project, check=check)


@pytest.mark.parametrize("framework,runner,variant", PAIRS, ids=["-".join(filter(None, p)) for p in PAIRS])
def test_init_end_to_end(tmp_path, framework, runner, variant):
    cpm = variant == "cpm"
    project = make_solution(tmp_path / "p", framework, runner, cpm=cpm, add_packages=True,
                            warnings_as_errors=variant == "twae")
    shutil.rmtree(project / "tests/App.Tests/obj", ignore_errors=True)  # detection before any restore (A2)
    detected = json.loads(script(project, "init_detect.py").stdout)
    assert detected["environment"] == [] or all("PATH" in p or "OS" in p for p in detected["environment"])
    proposal = detected["proposal"]
    assert proposal["acSurfaceProjects"] == ["src/App.Core/App.Core.csproj"]
    assert proposal["unitTestProjects"] == ["tests/App.Tests/App.Tests.csproj"]
    assert proposal["testFramework"] == framework and detected["runner"] == runner
    assert detected["supported"]["supported"] is True and detected["blockers"] == []
    assert detected["cpm"] is cpm

    script(project, "init_config.py", "--solution", detected["solution"], "--surface", proposal["acSurfaceProjects"][0],
           "--unit-tests", proposal["unitTestProjects"][0], "--ac-project-dir", proposal["acProjectDir"],
           "--framework", framework, "--runner", runner)
    scaffold = script(project, "init_scaffold.py", "--target-framework", proposal["targetFramework"], check=False)
    assert scaffold.returncode == 0, scaffold.stdout + scaffold.stderr
    verify = script(project, "init_verify.py", check=False)
    output = verify.stdout + verify.stderr
    print(output)
    assert verify.returncode == 0, output
    lines = [line for line in verify.stdout.splitlines() if line[:4] in ("PASS", "FAIL", "SKIP")]
    assert lines and all(not line.startswith("FAIL") for line in lines), output
    assert "PASS [7] results: bound scenario passed" in output
    if variant == "twae":
        assert "PASS [5] root Directory.Build.props applies in ref mode" in output


HOST_PROBE = {  # a step file that uses the host's public API; the web one needs Microsoft.AspNetCore.Routing (S14-R08)
    "worker": "namespace App.AcceptanceTests.StepDefinitions;\npublic static class HostProbe\n{\n    public static "
              "App.Host.Worker Make() => new(Microsoft.Extensions.Logging.Abstractions.NullLogger<App.Host.Worker>"
              ".Instance);\n}\n",
    "web": "namespace App.AcceptanceTests.StepDefinitions;\npublic static class HostProbe\n{\n    public static "
           "Microsoft.AspNetCore.Routing.IEndpointRouteBuilder Map(Microsoft.AspNetCore.Routing.IEndpointRouteBuilder "
           "routes) => App.Host.Greeting.MapGreeting(routes);\n}\n",
}
HOSTS = [("worker", "xunit3", "vstest"), ("web", "mstest", "mtp")]


@pytest.mark.parametrize("kind,framework,runner", HOSTS, ids=[h[0] for h in HOSTS])
def test_init_with_a_host_surface(tmp_path, kind, framework, runner):
    """Step 14 (#16): a product that is one host project. Init proposes no library, the user chooses the host by hand,
    and the export, both builds and the bound scenario work; a step file using the host's API builds in ref mode."""
    project = make_host_solution(tmp_path / "p", kind, framework, runner)
    detected = json.loads(script(project, "init_detect.py").stdout)
    proposal = detected["proposal"]
    assert proposal["acSurfaceProjects"] == [] and proposal["hostProjects"] == [HOST_PROJECT]
    assert proposal["testFramework"] == framework and detected["runner"] == runner and detected["blockers"] == []

    script(project, "init_config.py", "--solution", detected["solution"], "--surface", HOST_PROJECT,
           "--unit-tests", proposal["unitTestProjects"][0], "--ac-project-dir", proposal["acProjectDir"],
           "--framework", framework, "--runner", runner)
    scaffold = script(project, "init_scaffold.py", "--target-framework", proposal["targetFramework"], check=False)
    assert scaffold.returncode == 0, scaffold.stdout + scaffold.stderr
    cfg = json.loads((project / ".workflow/config.json").read_text(encoding="utf-8"))
    ac_csproj = (project / cfg["acProject"]).read_text(encoding="utf-8")
    assert ('<FrameworkReference Include="Microsoft.AspNetCore.App" />' in ac_csproj) is (kind == "web")
    verify = script(project, "init_verify.py", check=False)
    output = verify.stdout + verify.stderr
    print(output)
    assert verify.returncode == 0, output
    lines = [line for line in verify.stdout.splitlines() if line[:4] in ("PASS", "FAIL", "SKIP")]
    assert lines and all(not line.startswith("FAIL") for line in lines), output
    assert "PASS [7] results: bound scenario passed" in output

    api = (project / cfg["refsDir"] / "api" / "App.Host.cs").read_text(encoding="utf-8")
    assert ("public static class Pricing" if kind == "worker" else "public static class Greeting") in api
    assert "Main(" not in api
    (project / cfg["acProjectDir"] / "StepDefinitions" / "HostProbe.cs").write_text(HOST_PROBE[kind], encoding="utf-8")
    build = run(cfg["acRefBuildCommand"].split(), project, check=False)
    assert build.returncode == 0, build.stdout[-3000:] + build.stderr[-2000:]


def test_xunit2_on_mtp_is_refused(tmp_path):
    project = make_solution(tmp_path / "p", "xunit2", "mtp")
    detected = json.loads(script(project, "init_detect.py").stdout)
    assert detected["supported"]["supported"] is False and "xunit3/mtp" in detected["supported"]["supportedPairs"]
    result = script(project, "init_config.py", "--solution", "App.slnx", "--surface", "src/App.Core/App.Core.csproj",
                    "--ac-project-dir", "tests/App.AcceptanceTests", "--framework", "xunit2", "--runner", "mtp",
                    check=False)
    assert result.returncode == 1 and "not supported" in result.stderr
    assert not (project / ".workflow/config.json").exists()
