"""Runtime code must use the Python standard library only (CLAUDE.md, DESIGN §9)."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "src" / "speckit_ac"
# The payload scripts import each other (`aclib`, the shared helper; init_* and changed_files), each itself checked
# here.
SIBLINGS = {p.stem for p in (PACKAGE_DIR / "payload" / "scripts").glob("*.py")}
ALLOWED = set(sys.stdlib_module_names) | {"speckit_ac"} | SIBLINGS


def non_stdlib_imports(source: str, filename: str = "<string>") -> list[tuple[int, str]]:
    """Return (line, module) for every absolute import outside the allowed set."""
    found = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            if name.split(".")[0] not in ALLOWED:
                found.append((node.lineno, name))
    return found


def test_checker_flags_third_party_imports():
    source = "import os\nimport requests\nfrom yaml import safe_load\nfrom . import x\n"
    assert non_stdlib_imports(source) == [(2, "requests"), (3, "yaml")]


def test_runtime_code_imports_stdlib_only():
    files = sorted(PACKAGE_DIR.rglob("*.py"))
    assert files, f"no Python files found under {PACKAGE_DIR}"
    offenders = [
        f"{path.relative_to(ROOT)}:{line} {module}"
        for path in files
        for line, module in non_stdlib_imports(path.read_text(encoding="utf-8"), str(path))
    ]
    assert not offenders, "non-stdlib imports:\n" + "\n".join(offenders)
