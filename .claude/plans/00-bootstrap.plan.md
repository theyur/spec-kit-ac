# Plan — Step 0: repo bootstrap

Spec: `docs/steps/00-bootstrap.spec.md` (approved by the user 2026-11-07, incl. decisions 1–4).

## Facts observed (probed 2026-11-07, scratchpad, outside the repo)

- `uv init --lib --build-backend uv` (uv 0.11.26) emits `requires = ["uv_build>=0.11.26,<0.12.0"]`,
  `build-backend = "uv_build"`, `src/<module>/` layout.
- A `uv_build` wheel includes non-Python files under the module folder, nested dirs included
  (`probe/payload/README.md`, `probe/payload/commands/a.md` were in the wheel). No extra config needed.
- uv_build derives the module name from the project name: `speckit-ac` → `speckit_ac`.
- Only CPython 3.14.6 (uv-managed) is installed; `python` is not on PATH, so every command goes
  through `uv run`.
- spec-kit 1.0.2 bundled extension layout: `extension.yml`, `commands/`, `scripts/{bash,powershell,python}/`,
  `README.md`, config templates.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| 1 | Installed wheels are unpacked on disk, so `importlib.resources.files("speckit_ac") / "payload"` is a real `pathlib.Path` (needed later to pass to `specify extension add --dev`) | 0.95 | step 6 cannot hand spec-kit a folder | `paths.payload_dir()` raises if the resource is not a real directory; S00-A05 runs from a real tool-style install |
| 2 | `version = "0.1.0.dev0"` is accepted by uv_build and reported unchanged by `importlib.metadata` | 0.9 | S00-A03 string differs (e.g. normalisation) | S00-A03 / test |
| 3 | Tests on 3.14 are representative for the 3.11 floor for this step's code (only argparse, importlib, pathlib, ast, tomllib, subprocess) | 0.85 | a 3.12+-only API slips in | optional run `uv run --python 3.11 pytest` if uv can fetch 3.11; otherwise reported as not verified |
| 4 | Reference assemblies + API listings stay at `artifacts/refs/` (CT default) in the per-feature model; DESIGN is silent | 0.6 | WORKFLOW.md names a wrong path (doc-only, low impact) | WORKFLOW.md marks it "location confirmed in step 2"; step 2 decides with the user |

No blocking assumptions (4 is low-confidence but low-impact: documentation only, explicitly marked).

## Steps

1. **`pyproject.toml`** (S00-R01, R02, R04): `[project]` name `speckit-ac`, version `0.1.0.dev0`,
   description, `readme = "README.md"`, `requires-python = ">=3.11"`, `dependencies = []`,
   `[project.scripts] speckit-ac = "speckit_ac.cli:main"`; `[build-system]` uv_build as probed;
   `[dependency-groups] dev = ["pytest>=8"]`; `[tool.pytest.ini_options] testpaths = ["tests"]`,
   `addopts = "-p no:cacheprovider"` is **not** added (keep defaults; `.pytest_cache/` is ignored).
   No `authors` with email (keep personal data out of package metadata unless the user wants it).
2. **Source** (S00-R04, R05):
   - `src/speckit_ac/__init__.py`: `__version__ = importlib.metadata.version("speckit-ac")`.
   - `src/speckit_ac/cli.py`: `build_parser()` (prog `speckit-ac`, description, `--version` via
     `action="version"`, version string `speckit-ac <__version__>`); `main(argv=None) -> int`: parse;
     no subcommands → print help to stdout, return 0. `argparse` exits via `SystemExit(0)` for
     `--version`/`--help`; `main` catches `SystemExit` and maps its code: `None` → 0, `int` → that
     int, anything else → print it to stderr and return 1. In-process callers get an int and the
     console script / `__main__` still exits with it.
   - `src/speckit_ac/__main__.py`: `raise SystemExit(main())`.
   - `src/speckit_ac/paths.py`: `payload_dir() -> Path`: `files("speckit_ac") / "payload"`,
     must be a real `pathlib.Path` (`isinstance` check first, so a zip-backed resource raises our
     `RuntimeError`, not a `TypeError`), then `.resolve()`; raise `RuntimeError` if not an existing
     directory.
   - No `py.typed` (not a typed library; nothing imports it).
3. **Payload placeholder** (S00-R06, R07): `src/speckit_ac/payload/README.md` — planned layout
   (`extension.yml` → step 4; `commands/speckit.ac.*.md` → step 4; `agents/` → step 3;
   `hooks/guard.py` → step 2; `scripts/` → step 2; `templates/` → steps 4–5), the note that it is
   copied to `.specify/extensions/ac/`, and "never imported as Python". No `__init__.py` in payload.
4. **Tests** (S00-R08, R09). All repo paths anchor on `ROOT = Path(__file__).resolve().parents[1]`
   (never cwd), so the suite runs from any directory:
   - `tests/test_cli.py`: in-process `main(["--version"])` → 0 and `capsys` stdout ==
     `speckit-ac <version>\n`; `main([])` → 0 and stdout contains `usage: speckit-ac`;
     subprocess `[sys.executable, "-m", "speckit_ac", "--version"]` → rc 0, same text.
   - `tests/test_package.py`: `__version__` == `tomllib` value from `pyproject.toml`;
     `payload_dir()` is a dir containing `README.md`.
   - `tests/test_stdlib_only.py`: walk `src/speckit_ac/**/*.py`, `ast.parse`, collect `Import`
     names and `ImportFrom` with `level == 0`; top-level name must be in
     `sys.stdlib_module_names | {"speckit_ac"}`; failure message lists `file:line module`. Plus a
     self-check: the checker function flags a synthetic `import requests` source (so the test can't
     silently pass on an empty walk), and assert the walk found ≥ 1 file.
5. **Hygiene** (S00-R10): `.gitignore` and `.gitattributes` exactly as the spec lists.
5a. **README.md** (S00-R11) as specified — written **before** `uv sync`, because `[project] readme`
   makes uv_build read it while building the editable install.
6. **`uv sync`** → creates `.venv/` and `uv.lock` (S00-R03).
7. (README moved to 5a.)
8. **docs/WORKFLOW.md** (S00-R12, R13): sections — header note (target behaviour, steps 2–6;
   source = method of the reference doc); 0 What is tested; 1 Flow (DESIGN §5 table, stop rule,
   translation issue handling skip/fix/stop, after-analyze options); 2 Spec inputs (DESIGN §4);
   3 Isolation: who sees what (per-feature paths, DESIGN §8 layout), principles 1–8 (CT §2.2 meaning,
   version claims marked "verify in step 1"; the reference-assembly / API-listing row keeps
   `artifacts/refs/**` marked "location confirmed in step 2" — DESIGN is silent, assumption 4);
   4 Multi-feature model (tags, scope, Shared, writer
   compile fixes, all-features analyze, verdicts incl. `SUPERSEDED`); 5 Locks (sources incl. spec.md
   hash, features); 6 Known limits (CT §8 generalised). No CT names/paths.
9. **Verification**: S00-A01…A09 (A04: `uv build` then list wheel with `zipfile`; A05:
   `uvx --isolated --from . speckit-ac --version`; A06: `Requires-Dist` absent in wheel METADATA;
   A07 grep; A08 manual read; A09 `git status --porcelain`). Remove `dist/` afterwards? No — it's
   git-ignored; leave it. Optional, only with the user's OK (needs a CPython 3.11 download):
   `uv run --isolated --python 3.11 --group dev pytest -q --tb=short` (assumption 3); otherwise
   reported as not verified.
10. **Tracker** (S00-R14): row 0 → `done`, plan link, verified list; notes for any open item
   (refs location, 3.11 check, LICENSE due by step 4). Spec header status → `done`.

## Review dispositions

### Round 1 (`00-bootstrap.review-1.md`, REVISE)

| # | Sev | Finding | Disposition |
|---|---|---|---|
| 1 | MAJOR | `readme` declared before README exists; `uv sync` (step 6) would fail | ACCEPTED — README moved to step 5a, before `uv sync` |
| 2 | MINOR | `SystemExit.code` mapping unstated | ACCEPTED — step 2 states `None` → 0, int → int, other → 1 (message printed to stderr) |
| 3 | MINOR | test paths cwd-relative | ACCEPTED — step 4 anchors on `ROOT = Path(__file__).resolve().parents[1]` |
| 4 | MINOR | refs/API-listing location undecided in DESIGN | ACCEPTED — step 8 keeps the row with the CT default `artifacts/refs/` marked "location confirmed in step 2"; added as assumption 4 |
| 5 | MINOR | optional 3.11 run would recreate `.venv` | ACCEPTED — step 9 uses `uv run --isolated --python 3.11`; and it requires a CPython 3.11 download, so it runs only if the user agrees |
| 6 | MINOR | spec header still says `spec-draft` | ACCEPTED — step 10 updates the spec's status line too |

### Round 2 (`00-bootstrap.review-2.md`, APPROVE)

| # | Sev | Finding | Disposition |
|---|---|---|---|
| 1 | MINOR | `payload_dir()` not `.resolve()`d | ACCEPTED — step 2 resolves the path |
| 2 | MINOR | zip-backed resource raises `TypeError` before the guard | ACCEPTED — step 2 checks `isinstance(..., Path)` first |
| 3 | MINOR | blank line splits assumptions table | ACCEPTED — removed |
