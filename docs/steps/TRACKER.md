# Implementation tracker

Every step goes through `/spec-implement <step spec>`:

1. Draft the step spec `docs/steps/NN-<name>.spec.md` from `docs/DESIGN.md` and this tracker
   (numbered requirement IDs, e.g. `S02-R01`, acceptance checks, out-of-scope list).
2. Show the spec to the user and wait for approval.
3. Run `/spec-implement docs/steps/NN-<name>.spec.md` (plan in `.claude/plans/`, plan-critic loop,
   implementation, verification).
4. Update this tracker: status, links, verification result, decisions, open items.
5. Stop. The user starts the next step. Commit only when the user asks.

Status values: `todo` · `spec-draft` · `spec-approved` · `planning` · `implementing` · `done` · `blocked`.

| # | Step | Status | Spec | Plan | Verified | Commit |
|---|------|--------|------|------|----------|--------|
| 0 | Repo bootstrap: `pyproject.toml` (uv, console script `speckit-ac`), `src/speckit_ac/` layout with `payload/` = the extension, pytest setup, README skeleton, generic `docs/WORKFLOW.md` (from CT doc §0–2, §8) | done | [00-bootstrap.spec.md](00-bootstrap.spec.md) | [plan](../../.claude/plans/00-bootstrap.plan.md) (critic: REVISE → APPROVE, 2 rounds) | 2026-11-07: S00-A01–A09 pass (10 tests; wheel ships `payload/README.md`; no `Requires-Dist`; `uvx --isolated` prints version; `payload_dir()` resolves from a non-editable wheel). Python 3.11 floor not run (see notes) | |
| 1 | Platform spike (gate): throwaway `specify init` project + one-command test extension; verify the DESIGN §10 risks. Stop and decide with the user if anything fails | done | [01-platform-spike.spec.md](01-platform-spike.spec.md) · [results](01-platform-spike.results.md) | [plan](../../.claude/plans/01-platform-spike.plan.md) (critic: REVISE → REVISE → APPROVE, 3 rounds) | 2026-11-07: spike run (11 headless runs, $0.037). Risk 1 FAIL (flag dropped; patch and guard-deny both work), risk 2 PASS, risk 3 PASS, risk 4 PARTIAL (no hand-back tool seen headless). New: N1 skills symlinked by `--dev`, N2 spec-kit scripts need PATH Python once an extension is installed. pytest 10 pass; no `src/`/`tests/` change | |
| 2 | Port and adapt runtime: `guard.py` + all scripts from CT to the per-feature model (DESIGN §3, §8); `test_guard.py` → pytest with CT cases + per-feature / cross-feature cases | todo | | | | |
| 3 | Agents: translator (feature tag, one feature), writer (`[Scope]`, `Support/Shared`, cross-feature compile fixes, runner/framework aware), judge (`SUPERSEDED`) | todo | | | | |
| 4 | Commands: `translate` (two phases), `tests-write`, `tests-analyze` (all / `--current`), `critic` (port + `ac`, `features` stages); `extension.yml` with optional hooks | todo | | | | |
| 5 | `/speckit-ac-init`: detection, questions, AC project scaffolding per framework/runner, config, automatable verification (CT doc §6 items 1, 3–7), smoke-test instructions | todo | | | | |
| 6 | CLI + deploy: `install` / `uninstall` / `upgrade` / `doctor`, settings.json merge, marked blocks, deploy manifest; install→uninstall round-trip leaves a temp project byte-identical | todo | | | | |
| 7 | End-to-end sample in `tests/e2e/`: tiny .NET lib + spec-kit; one feature through the full flow with a planted implementation bug (→ `IMPLEMENTATION_FAULT`); a second, contradicting feature (→ `SUPERSEDED`); live guard smoke test (CT doc §6.8) | todo | | | | |
| 8 | Dogfood in Habit Tracker (`<habit-tracker>`, separate branch/PR there): install, `/speckit-ac-init`, its AC-surface + test-DB ADR, Sonar exclusions for step-definition folders | todo | | | | |
| 9 | Release: tag `v0.1.0`, GitHub repo, README install line | todo | | | | |

## Notes and open items

- Step 0 decisions (approved with the spec): Python floor **3.11** for all runtime code; build
  backend `uv_build`; `eol=lf` for every file.
- License: **MIT** (user, 2026-11-07; DESIGN decision log). `LICENSE` + `license = "MIT"` added after
  step 0; wheel metadata shows `License-Expression: MIT`.
- 2026-11-07: suite also passes on CPython 3.11.15 (10 tests), run with uv-managed Python and venv
  both inside the session scratchpad (`UV_PYTHON_INSTALL_DIR`, `UV_PROJECT_ENVIRONMENT`); nothing
  installed globally, the repo's `.venv` (3.14) untouched.
- Refs location decided (user, 2026-11-07; DESIGN §8 + decision log): one shared `refsDir`
  (default `artifacts/refs/`, git-ignored, configurable), regenerated at the start of translate and
  tests-write, as in the original project. `docs/WORKFLOW.md` §3.1 and §4 updated. The `.gitignore`
  entry is for step 5 (init) / step 6 (deploy) to add.
- Step 1 gate (2026-11-07), see
  [results § Decisions needed](01-platform-spike.results.md#decisions-needed-gate-r12).
  **Decided:** risk 1 → option C (deploy patches the flag + guard blocks `Skill` for
  `speckit-ac-*`; DESIGN §9 + decision log; work for steps 2 and 6); N1 → option A (deploy turns the
  symlinked skills into real patched files; verified in step 6); N2 → v1.0 environment fixed to
  Windows + uv + pwsh with spec-kit `--script ps` (DESIGN §2), so no PATH Python is needed;
  hand-back → option A (interactive Claude Code only, guard allows `SubagentHandback`; DESIGN §9).
  All gate decisions made; step 1 closed. Carried into later steps: guard blocks `Skill` for
  `speckit-ac-*` and allows `SubagentHandback` (step 2); deploy patches the flag and materialises
  the symlinked skills, `doctor`/`upgrade` re-check (step 6); init/doctor check the v1.0 environment
  (steps 5/6); interactive smoke test re-confirms the headless results (steps 7–8). DESIGN.md unchanged until agreed. Spike files remain only in the session scratchpad;
  N3 lists the user-level files Claude Code wrote.
