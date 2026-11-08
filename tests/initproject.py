"""Small real .NET solutions for the /speckit-ac-init tests (step 5).

`make_solution` writes a git repository with spec-kit's files, the installed payload, a class library (the AC
surface) and, optionally, a unit test project for a (framework, runner) recipe. The csproj files are written by
hand (no `dotnet new`, no restore), so detection tests run without the network; `add_packages=True` adds the unit
test project's packages with `dotnet add package` (network) for the end-to-end runs.
"""

import json
import shutil
import subprocess
from pathlib import Path

from acproject import EXTENSION, PAYLOAD, write

ADAPTER_FREE_PACKAGES = {  # the unit test project's packages per recipe (no Reqnroll)
    ("xunit2", "vstest"): ["xunit", "xunit.runner.visualstudio", "Microsoft.NET.Test.Sdk"],
    ("xunit2", "mtp"): ["xunit", "xunit.runner.visualstudio", "Microsoft.NET.Test.Sdk"],
    ("xunit3", "vstest"): ["xunit.v3.mtp-off", "xunit.runner.visualstudio", "Microsoft.NET.Test.Sdk"],
    ("xunit3", "mtp"): ["xunit.v3"],
    ("nunit", "vstest"): ["NUnit", "NUnit3TestAdapter", "Microsoft.NET.Test.Sdk"],
    ("nunit", "mtp"): ["NUnit", "NUnit3TestAdapter"],
    ("mstest", "vstest"): ["MSTest"],
    ("mstest", "mtp"): ["MSTest"],
}
UNIT_PROPERTIES = {
    ("xunit3", "vstest"): {"OutputType": "Exe"}, ("xunit3", "mtp"): {"OutputType": "Exe"},
    ("nunit", "mtp"): {"OutputType": "Exe", "EnableNUnitRunner": "true"},
    ("mstest", "mtp"): {"OutputType": "Exe", "EnableMSTestRunner": "true"},
}
UNIT_TEST = {
    "xunit2": "namespace App.Tests;\npublic class CalculatorTests\n{\n    [Xunit.Fact]\n    public void Doubles() => "
              "Xunit.Assert.Equal(4, new App.Core.Calculator().Double(2));\n}\n",
    "xunit3": "namespace App.Tests;\npublic class CalculatorTests\n{\n    [Xunit.Fact]\n    public void Doubles() => "
              "Xunit.Assert.Equal(4, new App.Core.Calculator().Double(2));\n}\n",
    "nunit": "namespace App.Tests;\npublic class CalculatorTests\n{\n    [NUnit.Framework.Test]\n    public void "
             "Doubles() => NUnit.Framework.Assert.That(new App.Core.Calculator().Double(2), "
             "NUnit.Framework.Is.EqualTo(4));\n}\n",
    "mstest": "namespace App.Tests;\n[Microsoft.VisualStudio.TestTools.UnitTesting.TestClass]\npublic class "
              "CalculatorTests\n{\n    [Microsoft.VisualStudio.TestTools.UnitTesting.TestMethod]\n    public void "
              "Doubles() => Microsoft.VisualStudio.TestTools.UnitTesting.Assert.AreEqual(4, "
              "new App.Core.Calculator().Double(2));\n}\n",
}
LIBRARY = """namespace App.Core;

/// <summary>Doubles numbers.</summary>
public class Calculator
{
    /// <summary>Returns twice the value.</summary>
    public int Double(int value) => value * 2;

    internal int Secret() => 42;
}
"""


def run(args, cwd: Path, check=True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        raise AssertionError(f"{' '.join(args)} failed:\n{result.stdout[-3000:]}{result.stderr[-2000:]}")
    return result


def csproj(tfm="net10.0", properties=None, packages=(), references=()) -> str:
    props = "".join(f"    <{k}>{v}</{k}>\n" for k, v in (properties or {}).items())
    pkgs = "".join(f'    <PackageReference Include="{p}"{f" Version={chr(34)}{v}{chr(34)}" if v else ""} />\n'
                   for p, v in packages)
    refs = "".join(f'    <ProjectReference Include="{r}" />\n' for r in references)
    groups = "".join(f"  <ItemGroup>\n{body}  </ItemGroup>\n" for body in (pkgs, refs) if body)
    return (f'<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n    <TargetFramework>{tfm}</TargetFramework>\n'
            f"    <ImplicitUsings>enable</ImplicitUsings>\n    <Nullable>enable</Nullable>\n{props}"
            f"  </PropertyGroup>\n{groups}</Project>\n")


def slnx(projects) -> str:
    body = "".join(f'  <Project Path="{p}" />\n' for p in projects)
    return f"<Solution>\n{body}</Solution>\n"


def make_solution(base: Path, framework=None, runner="vstest", cpm=False, add_packages=False, git=True,
                  unit_packages=None, warnings_as_errors=False) -> Path:
    """A spec-kit .NET project: App.slnx with src/App.Core (+ tests/App.Tests for `framework`)."""
    base.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PAYLOAD, base / EXTENSION, ignore=shutil.ignore_patterns("__pycache__"))
    write(base / ".specify/memory/constitution.md", "# Constitution\n")
    write(base / ".specify/init-options.json", json.dumps({"script": "ps"}) + "\n")
    write(base / "CLAUDE.md", "# Project\n")
    write(base / ".gitignore", "bin/\nobj/\n")
    write(base / "src/App.Core/App.Core.csproj", csproj())
    write(base / "src/App.Core/Calculator.cs", LIBRARY)
    projects = ["src/App.Core/App.Core.csproj"]
    if runner == "mtp":
        write(base / "global.json", json.dumps({"test": {"runner": "Microsoft.Testing.Platform"}}, indent=2) + "\n")
    if warnings_as_errors:
        write(base / "Directory.Build.props", "<Project>\n  <PropertyGroup>\n    <TreatWarningsAsErrors>true"
                                             "</TreatWarningsAsErrors>\n  </PropertyGroup>\n</Project>\n")
    if cpm:
        write(base / "Directory.Packages.props", "<Project>\n  <PropertyGroup>\n    <ManagePackageVersionsCentrally>"
                                                 "true</ManagePackageVersionsCentrally>\n  </PropertyGroup>\n</Project>\n")
    if framework:
        names = unit_packages if unit_packages is not None else ADAPTER_FREE_PACKAGES[(framework, runner)]
        packages = [] if add_packages else [(p, None if cpm else "1.0.0") for p in names]
        write(base / "tests/App.Tests/App.Tests.csproj",
              csproj(properties=UNIT_PROPERTIES.get((framework, runner)), packages=packages,
                     references=["../../src/App.Core/App.Core.csproj"]))
        write(base / "tests/App.Tests/CalculatorTests.cs", UNIT_TEST[framework])
        projects.append("tests/App.Tests/App.Tests.csproj")
        if add_packages:
            for name in names:
                run(["dotnet", "add", "tests/App.Tests/App.Tests.csproj", "package", name], base)
    write(base / "App.slnx", slnx(projects))
    if git:
        run(["git", "init", "-q"], base)
        run(["git", "add", "-A"], base)
        run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"], base)
    return base
