"""Export reference assemblies and C# API listings of the AC surface (docs/WORKFLOW.md §3).

Copies only reference assemblies (never real dlls, pdbs or XML docs) of each config.acSurfaceProjects entry and of
its project-to-project dependencies into config.refsDir, writes <refsDir>/api/<Assembly>.cs with ilspycmd, and
fails loudly if anything could leak implementation.

Two checks guard it:
- Packages, before anything is built or deleted: every package of the surface projects that is not implicit or
  PrivateAssets=all must also be referenced by the AC project in ref mode. Ref mode compiles against the reference
  assemblies only, which carry no package graph, so a package the surface gained after /speckit-ac-init would be
  missing there. The FAIL message lists the `dotnet add` lines that fix it; nothing is added automatically.
- Logic: no listing line may hold a statement outside string literals and comments; a reference assembly has only
  `throw null` bodies.
- Friends: an InternalsVisibleTo friend of an exported assembly may not be the AC project's own assembly (its
  AssemblyName in ref mode, compared case-insensitively, the public key ignored). The names come from the listing's
  `[assembly: InternalsVisibleTo(...)]` lines, which is what the compiler honours (csproj, props and `.cs` forms
  alike). A friend line in another form fails, and so does a DLL that names the attribute while its listing shows
  no friend line.

Reference assemblies drop method bodies but keep every type, internal and private nested ones included, and some
members that code outside the assembly cannot use: internal virtual and abstract members, internal interface
members, struct fields, and with InternalsVisibleTo every internal member. Those name the implementation's
structure, so the listing keeps public (and protected nested) types only, and of their members only the public,
protected and protected internal ones; the friend lines go too. Two backstops fail the export when anything hidden
is left: a line that starts with `internal` / `private` / `file`, and the keyword `private` or `internal` (not in
`protected internal`) anywhere in the code. Any failure after the refs folder is recreated removes it again, so no
unchecked DLL stays where the ref-mode build would compile against it.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aclib  # noqa: E402
import init_detect  # noqa: E402

ROOT = None  # the project root, set by main() (not at import, so the pure functions can be imported by tests)
CONFIGURATION = "Debug"
# Statements that can't appear in a reference-assembly listing, where every body is `throw null`. `return` followed
# by `:` is the attribute target of `[return: NotNullIfNotNull(...)]`, not a statement. Scanned line by line on
# code_only(listing).
LOGIC = re.compile(r"\breturn\b(?!\s*:)|\bif\s*\(|\bfor(each)?\s*\(|\bwhile\s*\(|\bswitch\b|\bawait\b|\btry\b")
# A type declaration as ilspycmd writes it: tab indentation, modifiers, keyword. Body braces are on their own lines.
TYPE_DECL = re.compile(r"^(?P<indent>\t*)(?P<mods>(?:(?:public|internal|private|protected|sealed|abstract|static|"
                       r"readonly|partial|file|unsafe|ref|new)\s+)*)(?:class|struct|interface|enum|record|delegate)\s")
NON_PUBLIC = re.compile(r"^\s*(?:internal|private|file)\b")
# The access keywords of a hidden member anywhere on a line's code (literals and comments blanked): `private`
# (`private protected` included) and `internal` not preceded by `protected `; never `@internal` or `Internal`.
HIDDEN_WORD = re.compile(r"(?<![@\w])private(?!\w)|(?<![@\w])(?<!protected )internal(?!\w)")
# A member declaration as ilspycmd writes it: at least one tab, then its modifier words.
MEMBER_DECL = re.compile(r"^(?P<indent>\t+)(?P<mods>(?:(?:public|private|protected|internal|static|readonly|const|"
                         r"virtual|abstract|override|sealed|new|extern|unsafe|volatile|async|required|ref|fixed)\s+)+)")
# A one-line accessor list at the end of a line (abstract, interface and extern properties, indexers, events):
# `public abstract int P { get; internal set; }`.
ONE_LINE_LIST = re.compile(r"\{(?P<body>[^{}]*)\}\s*$")
ACCESSOR = re.compile(r"^(?P<mods>(?:(?:public|private|protected|internal)\s+)*)(?:get|set|init|add|remove)$")
# A friend assembly line. A candidate is found on the code form of a line (literals blanked), so a string that
# mentions the name is not one; every candidate must have the one form ilspycmd writes.
FRIEND_CANDIDATE = re.compile(r"^\[\s*assembly\s*:.*InternalsVisibleTo")
FRIEND_LINE = re.compile(r'^\[assembly: (?:(?:global::)?System\.Runtime\.CompilerServices\.)?'
                         r'InternalsVisibleTo(?:Attribute)?\("(?P<text>[^"\\]*)"\)\]$')
NAMESPACE = re.compile(r"^namespace (?P<name>[\w.]+)$")
# The start of a string literal: an optional $ / @ prefix (interpolated, verbatim) and the run of quotes after it
# (3 or more open a raw string; 1, or 2 for an empty string, open a regular one).
STRING_START = re.compile(r'([$@]*)("+)')


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


def code_only(text):
    """The text with string and char literals emptied and comments removed, so keywords inside them don't count.
    Works on a line or the whole listing and keeps every newline, so the result has as many lines as the input.
    Verbatim and raw strings and /* */ comments may span lines; regular and interpolated strings, char literals and
    // comments end at their line (C# allows no newline in them). An unterminated verbatim or raw string or block
    comment hides the rest of the text, an unterminated one-line literal the rest of its line."""
    out, i, n = [], 0, len(text)

    def line_literal_end(j, close):
        """The index after a one-line literal whose content starts at j: past its closing quote, or at its line end."""
        while j < n and text[j] not in (close, "\n"):
            j += 2 if text[j] == "\\" and j + 1 < n and text[j + 1] != "\n" else 1
        return j + 1 if j < n and text[j] == close else j

    while i < n:
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            stop = n if end < 0 else end + 2
            out.append(" " + "\n" * text.count("\n", i, stop))
            i = stop
            continue
        c = text[i]
        if c == "'":
            out.append("''")
            i = line_literal_end(i + 1, "'")
            continue
        start = STRING_START.match(text, i) if c in '$@"' else None
        if not start:
            out.append(c)
            i += 1
            continue
        prefix, quotes = start.group(1), start.group(2)
        if "@" in prefix:  # verbatim, whatever the quote count: @"""a"" b" starts with an escaped quote
            j = i + len(prefix) + 1
            while j < n:
                if text[j] == '"':
                    if text.startswith('""', j):
                        j += 2
                        continue
                    break
                j += 1
            stop = min(j + 1, n)
        elif len(quotes) >= 3:  # raw string: ends at the same run of quotes
            end = text.find(quotes, start.end())
            stop = n if end < 0 else end + len(quotes)
        else:
            stop = line_literal_end(i + len(prefix) + 1, '"')
        out.append('""' + "\n" * text.count("\n", i, stop))
        i = stop
    return "".join(out)


def code_lines(listing):
    """(lines, code): the listing's lines and the same lines with literals emptied and comments removed. code_only
    runs once over the whole listing, so a multi-line literal or comment is not read as code."""
    lines, code = listing.split("\n"), code_only(listing).split("\n")
    if len(code) != len(lines):
        raise ValueError(f"code_only changed the line count ({len(lines)} -> {len(code)})")
    return lines, code


def logic_lines(listing):
    """The listing lines (stripped, otherwise as written) that hold a statement outside literals and comments."""
    return [line.strip() for line, scanned in zip(*code_lines(listing)) if LOGIC.search(scanned)]


def friends(listing):
    """The friend assembly names of the listing's InternalsVisibleTo lines: the text before the first comma (a
    PublicKey follows it), trimmed. Raises ValueError with the line when a candidate has another form."""
    names = []
    for line, scanned in zip(*code_lines(listing)):
        if FRIEND_CANDIDATE.match(scanned):
            match = FRIEND_LINE.match(line)
            if not match:
                raise ValueError(line.strip())
            names.append(match["text"].split(",", 1)[0].strip())
    return names


def hidden_access(mods):
    """True for modifier words whose access is not visible outside the assembly."""
    words = mods.split()
    return "private" in words or ("internal" in words and "protected" not in words)


def one_line_list(code):
    """The accessor-list match of a code line that ends with `{ … }` and has no other brace, else None."""
    return ONE_LINE_LIST.search(code) if code.count("{") == 1 and code.count("}") == 1 else None


def member_end(code, i, indent):
    """The index of the last line of the member declared on code line i, or None for a shape not known."""
    if code[i].rstrip().endswith(";") or one_line_list(code[i]):
        return i
    if i + 1 < len(code) and code[i + 1] == indent + "{":
        return next((j for j in range(i + 2, len(code)) if code[j] == indent + "}"), None)
    return None


def without_hidden_accessors(line, code):
    """The line with its hidden accessors removed from the one-line accessor list it ends with, or None when there
    is none to remove or the list can't be read (the keyword check then sees what is left)."""
    match = one_line_list(code)
    if not match:
        return None
    tail = code[match.start():]
    if not line.rstrip().endswith(tail.rstrip()):
        return None  # a comment after the list (code_only removed it)
    tokens = [t.strip() for t in match["body"].split(";")]
    if tokens[-1]:
        return None  # text after the last `;`
    accessors = [ACCESSOR.match(t) for t in tokens[:-1]]
    if not accessors or not all(accessors):
        return None
    kept = [a.group(0) for a in accessors if not hidden_access(a["mods"])]
    if len(kept) == len(accessors) or not kept:
        return None
    head = line.rstrip()[:len(line.rstrip()) - len(tail.rstrip())]
    return head + "{ " + " ".join(t + ";" for t in kept) + " }"


def visible_members(listing):
    """Strips the members that code outside the assembly can't use (internal, private and private protected, with
    their attributes and bodies, accessors too) and the InternalsVisibleTo lines. Run after public_only(): type
    declarations are left alone. Structure is read on the code form, so a literal is never taken for a member; the
    lines written are the original ones. A declaration of a shape not known stays, for the backstop checks."""
    lines, code = code_lines(listing)
    out, out_code, i, n = [], [], 0, len(lines)
    while i < n:
        line, scanned = lines[i], code[i]
        if FRIEND_CANDIDATE.match(scanned) and FRIEND_LINE.match(line):
            i += 1
            continue
        decl = MEMBER_DECL.match(scanned)
        if decl and not TYPE_DECL.match(scanned) and hidden_access(decl["mods"]):
            end = member_end(code, i, decl["indent"])
            if end is not None:
                while out_code and out_code[-1].startswith(decl["indent"] + "["):  # the member's attributes
                    out.pop()
                    out_code.pop()
                while out and not out[-1].strip():
                    out.pop()
                    out_code.pop()
                i = end + 1
                while i < n and not lines[i].strip():
                    i += 1
                if out and not out_code[-1].rstrip().endswith("{") and i < n and code[i].strip() != "}":
                    out.append("")
                    out_code.append("")
                continue
        elif scanned.startswith("\t") and not TYPE_DECL.match(scanned):
            rewritten = without_hidden_accessors(line, scanned)
            if rewritten is not None:
                line = scanned = rewritten
        out.append(line)
        out_code.append(scanned)
        i += 1
    return "\n".join(out)


def hidden_lines(listing):
    """The stripped lines of a filtered listing that still declare something hidden: NON_PUBLIC on the line as
    written (first word), or HIDDEN_WORD anywhere in its code."""
    lines, code = code_lines(listing)
    return [line.strip() for line, scanned in zip(lines, code) if NON_PUBLIC.match(line) or HIDDEN_WORD.search(scanned)]


def project_path(project):
    return project.relative_to(ROOT).as_posix() if project.is_relative_to(ROOT) else str(project)


def check_friends(dll, listing, ac_name, project):
    """Fail when a friend of the DLL is the AC assembly, or when its friends can't be read."""
    try:
        names = friends(listing)
    except ValueError as error:
        sys.exit(f"FAIL: cannot read a friend assembly line in the {dll.name} listing:\n  {error}")
    if not names and b"InternalsVisibleToAttribute" in dll.read_bytes():
        sys.exit(f"FAIL: {dll.name} has InternalsVisibleTo, but its listing shows no friend line; the friend check "
                 "cannot run (did the ilspycmd output change?)")
    for name in names:
        if name.casefold() == ac_name.casefold():
            sys.exit(f"FAIL: {dll.name} grants InternalsVisibleTo to the AC assembly {ac_name}; the acceptance tests "
                     f"may use only the public API. Remove that friend from {project_path(project)} (or the props "
                     "file that adds it).")


def missing_packages(surface, ac, cpm):
    """[(id, version or None)] of the public packages of the surface projects (package_refs lists) that the AC
    project (its package ids) lacks; first-seen order, case-insensitive. Version: the surface's (the highest when
    projects disagree), None under central package management or when the surface has none."""
    present = {pid.lower() for pid in ac}
    wanted, seen = [], set()
    for packages in surface:
        for p in packages:
            key = p["id"].lower()
            if init_detect.public_package(p) and key not in present and key not in seen:
                seen.add(key)
                wanted.append(p["id"])
    if cpm:
        return [(pid, None) for pid in wanted]
    return [(pid, init_detect.highest(p["version"] for packages in surface for p in packages
                                      if p["id"].lower() == pid.lower())) for pid in wanted]


def check_packages(cfg):
    """Fail before anything is built or deleted when the AC project lacks a public package of the surface. Returns
    the AC project's AssemblyName in ref mode (read in the same evaluation), for the friend check."""
    evaluations = [msbuild_json(p, "-getItem:PackageReference", "-getItem:PackageVersion",
                                "-getProperty:ManagePackageVersionsCentrally") for p in cfg["acSurfaceProjects"]]
    cpm = (any(init_detect._true(e.get("Properties", {}).get("ManagePackageVersionsCentrally")) for e in evaluations)
           or (ROOT / "Directory.Packages.props").is_file())
    ac_items = msbuild_json(cfg["acProject"], "-p:AcRefMode=true", "-getItem:PackageReference",
                            "-getProperty:AssemblyName")
    ac = [i["Identity"] for i in ac_items.get("Items", {}).get("PackageReference", [])]
    missing = missing_packages([init_detect.package_refs(e) for e in evaluations], ac, cpm)
    if missing:
        lines = [f'dotnet add "{cfg["acProject"]}" package {pid}' + (f" --version {version}" if version else "")
                 for pid, version in missing]
        sys.exit("FAIL: the AC project lacks packages that the AC surface references (ref mode compiles only against "
                 "the\nreference assemblies, so their types are missing there):\n  " + "\n  ".join(lines) +
                 "\nAdd them to the AC project (they go into the shared ItemGroup, so both modes get them), then run "
                 "the command again.")
    name = (ac_items.get("Properties", {}).get("AssemblyName") or "").strip()
    if not name:
        sys.exit(f"FAIL: cannot read the AssemblyName of {cfg['acProject']} (ref mode)")
    return name


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


def export(cfg, refs, ac_name):
    """Build the surface, copy its reference assemblies into refs and write their checked listings; returns the
    DLLs. Runs after refs is recreated: main() removes refs again when anything here fails."""
    for surface in cfg["acSurfaceProjects"]:
        run("dotnet", "build", surface, "-c", CONFIGURATION, "-p:ProduceReferenceAssembly=true", "-nologo", "-v", "q")

    exported = []
    for project in with_dependencies(cfg["acSurfaceProjects"]):
        props = msbuild_json(project, "-p:ProduceReferenceAssembly=true",
                             "-getProperty:TargetRefPath", "-getProperty:AssemblyName")["Properties"]
        ref_path = Path(props["TargetRefPath"])
        if not ref_path.is_file() or ref_path.parent.name != "ref":
            sys.exit(f"FAIL: no reference assembly for {project.name} (expected {ref_path})")
        if b"ReferenceAssemblyAttribute" not in ref_path.read_bytes():
            sys.exit(f"FAIL: {ref_path} is not a reference assembly")
        shutil.copyfile(ref_path, refs / ref_path.name)
        exported.append((project, refs / ref_path.name))

    for project, dll in exported:
        listing = run("dotnet", "tool", "run", "ilspycmd", "--", str(dll), "-r", str(refs), "--disable-updatecheck")
        bad = logic_lines(listing)
        if bad:
            sys.exit(f"FAIL: the {dll.name} listing contains logic, not only stubs:\n  " + "\n  ".join(bad[:10]))
        check_friends(dll, listing, ac_name, project)
        listing = visible_members(public_only(listing))
        hidden = hidden_lines(listing)
        if hidden:
            sys.exit(f"FAIL: the {dll.name} listing still declares non-public members or types:\n  " + "\n  ".join(hidden[:10]))
        (refs / "api" / f"{dll.stem}.cs").write_text(listing, encoding="utf-8", newline="\n")
    return [dll for _, dll in exported]


def remove_refs(refs, name):
    """Remove refs after a failed export; returns a note for the user when that fails too, else None."""
    try:
        if refs.exists():
            shutil.rmtree(refs)
    except OSError as error:
        return f"Also: could not remove {name} ({error}); delete it before the ref-mode build."
    return None


def main():
    global ROOT
    ROOT = aclib.root(__file__)
    cfg = aclib.load_config(ROOT)
    ac_name = check_packages(cfg)
    refs = ROOT / cfg["refsDir"]
    shutil.rmtree(refs, ignore_errors=True)
    (refs / "api").mkdir(parents=True)
    try:
        exported = export(cfg, refs, ac_name)
    except BaseException as error:
        note = remove_refs(refs, cfg["refsDir"])
        if note and isinstance(error, SystemExit) and isinstance(error.code, str):
            raise SystemExit(f"{error.code}\n{note}") from None
        if note:
            print(note, file=sys.stderr)
        raise
    print("Exported: " + ", ".join(d.name for d in exported) + f" -> {cfg['refsDir']}")


if __name__ == "__main__":
    aclib.run_main(main)
