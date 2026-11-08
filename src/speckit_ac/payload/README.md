# `payload/` — the spec-kit extension `ac`

This folder **is** the spec-kit extension. `speckit-ac install` passes it to
`specify extension add --dev`, which copies it to `.specify/extensions/ac/` in the target project.
The Claude-side files that spec-kit does not know about (agents, guard registration, `CLAUDE.md`
block, real patched skills, `.workflow/deploy.json`) are deployed by `speckit-ac install` from the installed
copy (`src/speckit_ac/deploy.py`).

It is shipped as package data and is not a Python package (no `__init__.py`). The CLI imports only
`scripts/aclib.py` and `scripts/init_config.py` from it, with bytecode writing switched off;
`.extensionignore` keeps any `__pycache__` / `*.pyc` out of the installed copy anyway.
Scripts in it run later, inside the target project, with the Python command stored in
`.workflow/config.json` (`<python> .specify/extensions/ac/scripts/<name>.py`, path relative to the
session's working directory; see [docs/CONFIG.md](../../../docs/CONFIG.md)). They find the project root
from their own location (`.specify/extensions/ac/scripts/` → four levels up).

## Layout

| Path | Contents | Tracker step |
|---|---|---|
| `.extensionignore` | `__pycache__/`, `*.pyc`: never copied by `specify extension add` | 6 (done) |
| `extension.yml` | Extension manifest (id `ac`, five commands, optional hooks after clarify / plan / tasks / implement) | 4, 5 (done) |
| `commands/speckit.ac.*.md` | `init` (setup, verify, smoke), `translate`, `tests-write`, `tests-analyze`, `critic` | 4, 5 (done) |
| `agents/` | `ac-feature-translator`, `ac-test-writer`, `ac-test-fail-judge`; each defines its task message | 3 (done) |
| `hooks/guard.py` | Fail-closed `PreToolUse` guard; self-contained, imports no project code | 2 (done) |
| `scripts/aclib.py` | Shared helper of the scripts: root, config, feature resolution, active-run marker | 2 (done) |
| `scripts/ac_feature.py` | Prints a feature's paths and tag as JSON (for the commands' prompts); `--all` lists every feature | 2, 3 (done) |
| `scripts/ac_lock.py` | `lock` / `verify` / `unlock` / `confirm-spec` of a feature's `sources` or `features` | 2 (done) |
| `scripts/new_run.py`, `new_analyze.py` | Next run / analyze folder of a feature; write the active-run marker | 2 (done) |
| `scripts/task_message.py` | The exact task message of the active run's subagent, filled from its agent file; recorded in the marker for the guard | 4 (done) |
| `scripts/changed_files.py` | Content-hash snapshot and check of a subagent's writes; the check ends the run (deletes the marker) | 2, 4 (done) |
| `scripts/check_acceptance.py` | Checks a feature's `acceptance.md`: ids, references, coverage, golden samples | 4 (done) |
| `scripts/check_features.py` | Structural check of a feature's `.feature` files (`@FNNN`, `@AC-`) | 2 (done) |
| `scripts/clear_generated.py` | Deletes a feature's generated `.feature` files or step definitions | 2 (done) |
| `scripts/record_skips.py` | Records AC ids the user skipped after a translation | 2 (done) |
| `scripts/summarize_trx.py` | Cleaned AC results for the judge (feature column, current vs regression; `--only-current`) | 2, 4, 5 (done) |
| `scripts/export_refs.py` | Reference assemblies + public API listings of the AC surface | 2, 5 (done; the .NET path runs in `init_verify.py`) |
| `scripts/init_detect.py` | Detects environment, solution, projects, runner, central package management; proposals and blockers as JSON | 5 (done) |
| `scripts/init_config.py` | Writes `.workflow/config.json`; `RECIPES`, the verified framework × runner table | 5 (done) |
| `scripts/init_scaffold.py` | Creates the AC project, adds packages and `ilspycmd`, writes the `.gitignore` / `.gitattributes` blocks | 5 (done) |
| `scripts/init_verify.py` | Setup checks (CT doc §6 items 1, 3–7) with temporary files and a leftover check | 5 (done) |
| `scripts/smoke_test.py` | Live guard smoke test: smoke marker, `guard.log` comparison, isolation file | 5 (done; run live in step 7) |
| `scripts/extract_feedback.py` | Writer-feedback section of a judge report | 2 (done) |
| `templates/acceptance-template.md` | Format of a feature's `acceptance.md` | 4 (done) |
| `templates/ac-project/` | AC project csproj and `Directory.Build.props` templates, `reqnroll.json` | 5 (done) |
