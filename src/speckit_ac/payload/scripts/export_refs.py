"""Export reference assemblies and C# API listings of the AC surface (docs/WORKFLOW.md §3).

Copies only reference assemblies (never real dlls, pdbs or XML docs) of each config.acSurfaceProjects entry and of
its project-to-project dependencies into config.refsDir, writes <refsDir>/api/<Assembly>.cs with ilspycmd, and
fails loudly if anything could leak implementation.

Reference assemblies drop method bodies and private members but keep every type, internal and private nested ones
included, with their non-private members. Those name the implementation's structure, so the listing keeps public
(and protected nested) types only.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402

ROOT = None  # the project root, set by main() (not at import, so the pure functions can be imported by tests)
CONFIGURATION = "Debug"
# Statements that can't appear in a reference-assembly listing, where every body is `throw null`.
LOGIC = re.compile(r"\breturn\b|\bif\s*\(|\bfor(each)?\s*\(|\bwhile\s*\(|\bswitch\b|\bawait\b|\btry\b")
# A type declaration as ilspycmd writes it: tab indentation, modifiers, keyword. Body braces are on their own lines.
TYPE_DECL = re.compile(r"^(?P<indent>\t*)(?P<mods>(?:(?:public|internal|private|protected|sealed|abstract|static|"
                       r"readonly|partial|file|unsafe|ref|new)\s+)*)(?:class|struct|interface|enum|record|delegate)\s")
NON_PUBLIC = re.compile(r"^\s*(?:internal|private|file)\b")
NAMESPACE = re.compile(r"^namespace (?P<name>[\w.]+)$")


def run(*args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"FAIL: {' '.join(args)}\n{result.stdout}{result.stderr}")
    return result.stdout


def msbuild_json(project, *queries):
    return json.loads(run("dotnet", "msbuild", str(project), f"-p:Configuration={CONFIGURATION}", *queries))


def with_dependencies(projects):
    seen, todo = [], [Path(p).resolve() for p in projects]
    while todo:
        project = todo.pop()
        if project in seen:
            continue
        seen.append(project)
        items = msbuild_json(project, "-getItem:ProjectReference")["Items"].get("ProjectReference", [])
        todo += [Path(i["FullPath"]).resolve() for i in items]
    return seen


def check_no_internals_visible_to(project):
    folder = project.parent
    candidates = [f for f in folder.rglob("*") if f.suffix in (".cs", ".csproj", ".props", ".targets")
                  and not any(re.match(r"(bin|obj)", s, re.IGNORECASE) for s in f.relative_to(folder).parts)]
    candidates += [ROOT / n for n in ("Directory.Build.props", "Directory.Build.targets") if (ROOT / n).is_file()]
    hits = [f.relative_to(ROOT).as_posix() for f in candidates
            if "InternalsVisibleTo" in f.read_text(encoding="utf-8", errors="replace")]
    if hits:
        sys.exit("FAIL: InternalsVisibleTo puts internal members into the reference assembly:\n  " + "\n  ".join(hits))


def visible(mods):
    words = mods.split()
    return "public" in words or ("protected" in words and "private" not in words)


def public_only(listing):
    """Drops non-public type declarations (with their attributes and bodies), then namespaces left empty."""
    lines, out, i = listing.splitlines(), [], 0
    while i < len(lines):
        decl = TYPE_DECL.match(lines[i])
        if not decl or visible(decl["mods"]):
            out.append(lines[i])
            i += 1
            continue
        indent = decl["indent"]
        while out and out[-1].startswith(indent + "[") and not out[-1].startswith(("[assembly:", "[module:")):
            out.pop()  # the type's attributes
        if not lines[i].rstrip().endswith(";"):
            while i < len(lines) and lines[i] != indent + "}":
                i += 1
        i += 1

    empty, kept, i = set(), [], 0
    while i < len(out):
        ns = NAMESPACE.match(out[i])
        end = out.index("}", i) if ns and i + 1 < len(out) and out[i + 1] == "{" and "}" in out[i:] else -1
        if end >= 0 and not any(line.strip() for line in out[i + 2:end]):
            empty.add(ns["name"])
            i = end + 1
            continue
        kept.append(out[i])
        i += 1
    return "\n".join(line for line in kept if line.strip() not in {f"using {n};" for n in empty}) + "\n"


def main():
    global ROOT
    ROOT = aclib.root(__file__)
    cfg = aclib.load_config(ROOT)
    refs = ROOT / cfg["refsDir"]
    shutil.rmtree(refs, ignore_errors=True)
    (refs / "api").mkdir(parents=True)

    for surface in cfg["acSurfaceProjects"]:
        run("dotnet", "build", surface, "-c", CONFIGURATION, "-p:ProduceReferenceAssembly=true", "-nologo", "-v", "q")

    exported = []
    for project in with_dependencies(cfg["acSurfaceProjects"]):
        check_no_internals_visible_to(project)
        props = msbuild_json(project, "-p:ProduceReferenceAssembly=true",
                             "-getProperty:TargetRefPath", "-getProperty:AssemblyName")["Properties"]
        ref_path = Path(props["TargetRefPath"])
        if not ref_path.is_file() or ref_path.parent.name != "ref":
            sys.exit(f"FAIL: no reference assembly for {project.name} (expected {ref_path})")
        if b"ReferenceAssemblyAttribute" not in ref_path.read_bytes():
            sys.exit(f"FAIL: {ref_path} is not a reference assembly")
        shutil.copyfile(ref_path, refs / ref_path.name)
        exported.append(refs / ref_path.name)

    for dll in exported:
        listing = run("dotnet", "tool", "run", "ilspycmd", "--", str(dll), "-r", str(refs), "--disable-updatecheck")
        bad = [line.strip() for line in listing.splitlines() if LOGIC.search(line)]
        if bad:
            sys.exit(f"FAIL: the {dll.name} listing contains logic, not only stubs:\n  " + "\n  ".join(bad[:10]))
        listing = public_only(listing)
        hidden = [line.strip() for line in listing.splitlines() if NON_PUBLIC.match(line)]
        if hidden:
            sys.exit(f"FAIL: the {dll.name} listing still declares non-public members or types:\n  " + "\n  ".join(hidden[:10]))
        (refs / "api" / f"{dll.stem}.cs").write_text(listing, encoding="utf-8", newline="\n")

    print("Exported: " + ", ".join(d.name for d in exported) + f" -> {cfg['refsDir']}")


if __name__ == "__main__":
    aclib.run_main(main)
