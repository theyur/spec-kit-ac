# Step 0 — Repo bootstrap

**Status:** done (2026-11-07; approved with decisions 1–4) · **Tracker row:** 0 · **Source of truth:** `docs/DESIGN.md`

## Goal

Turn the empty repo into an installable, testable Python package skeleton for the `speckit-ac` CLI,
with a place for the spec-kit extension payload, and write the generic workflow description that
later steps implement. No workflow logic yet: no guard, scripts, agents, commands or deploy code.

## Context

- DESIGN §9: distributed as a Python CLI `speckit-ac`, installed with
  `uv tool install speckit-ac --from git+https://github.com/<owner>/spec-kit-ac`; the CLI later runs
  `specify extension add --dev <bundled payload>` and a deploy step. So the extension folder must
  ship **inside** the Python package.
- DESIGN §9 / CLAUDE.md: runtime code is Python 3, standard library only; pytest is dev-only.
- spec-kit 1.0.2 extensions (checked in `specify_cli/core_pack/extensions/git/`) are a folder with
  `extension.yml`, `commands/speckit.<id>.<cmd>.md`, `scripts/…`, `README.md`. The real
  `extension.yml` is written in step 4, after the step 1 spike confirms the platform behaviour.
- Tooling on this machine: uv 0.11.26, CPython 3.14 (uv-managed), specify 1.0.2.

## Requirements

### Packaging

- **S00-R01** `pyproject.toml` defines the distribution `speckit-ac`, version `0.1.0.dev0`,
  `requires-python = ">=3.11"`, **no runtime dependencies**, build backend `uv_build`, and the console
  script `speckit-ac = "speckit_ac.cli:main"`.
- **S00-R02** pytest is declared only in a uv dependency group `dev` (`[dependency-groups]`), never in
  `[project.dependencies]`. pytest config lives in `pyproject.toml` (`testpaths = ["tests"]`).
- **S00-R03** `uv.lock` is generated and kept in the repo (not git-ignored).
- **S00-R04** The version has one source: `pyproject.toml`. Runtime code reads it with
  `importlib.metadata.version("speckit-ac")`; nothing else hard-codes it.

### Source layout

- **S00-R05** `src/speckit_ac/` package with:
  - `__init__.py`: exposes `__version__` (from S00-R04).
  - `__main__.py`: `python -m speckit_ac` runs the same entry point as the console script.
  - `cli.py`: `main(argv=None) -> int` built on `argparse`. Supports `--version`
    (prints `speckit-ac <version>`, exit 0) and `--help`. With no arguments it prints help and exits 0.
    No subcommands yet (install/uninstall/upgrade/doctor arrive in step 6).
  - `paths.py`: `payload_dir() -> pathlib.Path`, the absolute path of the bundled payload folder,
    resolved with `importlib.resources` so it works from an installed wheel.
- **S00-R06** `src/speckit_ac/payload/` = the spec-kit extension folder (copied later to
  `.specify/extensions/ac/` by `specify extension add --dev`). In this step it holds only
  `README.md`, which states the planned layout (`extension.yml`, `commands/`, `agents/`, `hooks/`,
  `scripts/`, `templates/`), which step fills each part, and that the payload is never imported as
  Python.
- **S00-R07** The built wheel contains every file under `payload/` (non-Python files included).

### Tests

- **S00-R08** `tests/` with pytest tests for: `--version` output and exit code (in-process via
  `main([...])` **and** via `python -m speckit_ac` in a subprocess); no-argument call prints help,
  exit 0; `__version__` equals the version in `pyproject.toml` (read with `tomllib`);
  `payload_dir()` exists and contains `README.md`.
- **S00-R09** A stdlib-only test: parses every `.py` file under `src/speckit_ac/` with `ast` and fails
  if any absolute import's top-level module is neither in `sys.stdlib_module_names` nor `speckit_ac`.
  This guards the CLAUDE.md rule for all later steps (the payload's future scripts included).

### Repo hygiene

- **S00-R10** `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `dist/`, `build/`,
  `*.egg-info/`. `.gitattributes`: `* text=auto eol=lf` (scripts and `.md` that ship into target
  repos keep stable hashes across OSes — the deploy manifest in step 6 relies on it).

### Documentation

- **S00-R11** `README.md` skeleton: one-paragraph purpose; status "pre-release, under construction";
  planned install line (`uv tool install speckit-ac --from git+https://github.com/<owner>/spec-kit-ac`,
  marked as not yet available); planned commands table (`/speckit-ac-init`, `-translate`,
  `-tests-write`, `-tests-analyze`, `-critic`, and CLI `install`/`uninstall`/`upgrade`/`doctor`), each
  marked "planned"; prerequisites (spec-kit, `CLAUDE.md`, .NET solution — DESIGN §2); development
  section (`uv sync`, `uv run pytest -q --tb=short`); links to `docs/DESIGN.md`, `docs/WORKFLOW.md`,
  `docs/steps/TRACKER.md`.
- **S00-R12** `docs/WORKFLOW.md`: the generic method, rewritten for the spec-kit per-feature model.
  Sources: CT doc §0 (what is tested), §1 (flow), §2 (isolation: who sees what + principles), §8
  (known limits), adapted to DESIGN §3–§8. Concretely:
  - Flow = DESIGN §5 (spec-kit commands and `/speckit-ac-*`), with "stop after every step".
  - Spec inputs = DESIGN §4 (`spec.md`, constitution, `acceptance.md`, configured extras; never
    `plan.md`, `research.md`, `data-model.md`, `contracts/`, `tasks.md`, `CLAUDE.md`).
  - Access table uses per-feature paths: `specs/NNN-x/acceptance.md`,
    `specs/NNN-x/ac/{sources.lock,features.lock}`, `specs/NNN-x/ac/runs/…`, and the AC project's
    `Features/F00N/`, `Samples/F00N/`, `StepDefinitions/F00N/`, `Support/F00N/`, `Support/Shared/`.
  - Judge verdicts include `SUPERSEDED`; `tests-analyze` default "all features".
  - Principles 1–8 of CT §2.2 kept in meaning; Claude Code version claims (`omitClaudeMd`,
    `onFailure: "block"`) marked "to be verified in step 1".
  - A header line: describes the target behaviour; implemented across tracker steps 2–6.
- **S00-R13** `docs/WORKFLOW.md` and `README.md` contain **no CT specifics**: no `docs/SPEC.md`,
  `docs/acceptance/`, `ARCHITECTURE.md`, `CONTEXT.md`, CT project names, or CT §10 content.

### Tracker

- **S00-R14** After implementation, `docs/steps/TRACKER.md` row 0 is updated (status `done`, spec and
  plan links, what was verified) per the tracker process. No commit unless the user asks.

## Acceptance checks

Run from the repo root.

| ID | Check | Covers |
|---|---|---|
| S00-A01 | `uv sync` succeeds; `uv.lock` exists | R01–R03 |
| S00-A02 | `uv run pytest -q --tb=short` → all pass | R04, R05, R08, R09 |
| S00-A03 | `uv run speckit-ac --version` prints exactly `speckit-ac 0.1.0.dev0`, exit 0 | R04, R05 |
| S00-A04 | `uv build` produces a wheel and an sdist in `dist/`; the wheel's file list includes `speckit_ac/payload/README.md` | R06, R07 |
| S00-A05 | `uvx --isolated --from . speckit-ac --version` prints the version (clean env, as a tool install would see it; does not touch the user's installed tools) | R01, R05, R07 |
| S00-A06 | `uv pip show` / wheel `METADATA` lists no `Requires-Dist` | R01, R02 |
| S00-A07 | `grep -nE 'SPEC\.md|docs/acceptance|ARCHITECTURE\.md|CONTEXT\.md|\bCT\b' README.md docs/WORKFLOW.md \| grep -v 'WORKFLOW-SETUP-CT\.md'` → no matches (a link to the reference doc is allowed) | R13 |
| S00-A08 | Manual read: `docs/WORKFLOW.md` covers flow, spec inputs, per-feature access table, principles, known limits as listed in R12 | R12 |
| S00-A09 | `git status` shows no `dist/`, `.venv/`, `__pycache__/` entries | R10 |

## Out of scope

- `extension.yml`, commands, agents, guard, scripts, templates (steps 2–4).
- CLI subcommands `install` / `uninstall` / `upgrade` / `doctor`, deploy logic (step 6).
- `/speckit-ac-init` and anything about target projects (step 5).
- Platform spike / any `specify init` run (step 1).
- CI workflow, LICENSE file, GitHub repo, tag, publishing (step 9).
- Linters/formatters (ruff etc.) — not requested; can be added later on request.
- Any edit under `<original project>\` (read-only source).

## Decisions taken in this spec (confirm on approval)

1. **Python floor 3.11** for all runtime code (CLI and, later, guard/scripts in target repos):
   gives `tomllib` and modern typing; 3.11 is from 2022. Step 5's init/doctor will check the
   target's Python command against it.
2. **Build backend `uv_build`** (uv's own, zero-dependency) rather than hatchling.
3. **`eol=lf` for everything** in this repo (stable hashes for shipped files).
4. **No LICENSE yet** — deferred to step 9 (spec-kit itself is MIT; `extension.yml` in step 4 will
   need a `license` value, so the choice is due by then).
