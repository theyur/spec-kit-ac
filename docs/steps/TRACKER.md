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
| 2 | Port and adapt runtime: `guard.py` + all scripts from CT to the per-feature model (DESIGN §3, §8); `test_guard.py` → pytest with CT cases + per-feature / cross-feature cases | done | [02-runtime-port.spec.md](02-runtime-port.spec.md) · [CONFIG.md](../CONFIG.md) | [plan](../../.claude/plans/02-runtime-port.plan.md) (critic: REVISE → REVISE → REVISE, 3 rounds, no BLOCKER; all findings dispositioned) | 2026-11-07: 288 tests pass (CPython 3.14 and 3.11.15): every CT guard case ported + per-/cross-feature, marker, config-state, root-fallback cases; script tests incl. spec drift exit 3, ignored-folder breaches, `.feature` write rules. Payload grep: no CT strings. Mutation spot-check: dropping the `is_file` or timestamp-numbering rule fails tests. Not run: `export_refs.py` against .NET (step 7), live hooks (steps 7–8) | |
| 3 | Agents: translator (feature tag, one feature), writer (`[Scope]`, `Support/Shared`, cross-feature compile fixes, runner/framework aware), judge (`SUPERSEDED`) | done | [03-agents.spec.md](03-agents.spec.md) | [plan](../../.claude/plans/03-agents.plan.md) (critic: REVISE → APPROVE, 2 rounds; all findings accepted) | 2026-11-08: 328 tests pass (CPython 3.14 and 3.11.15). New `test_agents.py` (28): frontmatter, no CT strings or hard-coded paths, placeholders defined, templates filled mechanically from `ac_feature.py` + config and checked against the real guard with the marker the run scripts write (every input readable, every output writable, build allowed). `testFramework` and `ac_feature.py --all` tests. Mutation spot-check: dropping the enum check, renaming a `paths()` key, removing a judge search root, an undefined placeholder, a changed feedback marker all fail tests. Not run: the agents themselves (step 7) | |
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
- Step 2 (2026-11-07): decisions 1–8 approved with the spec (DESIGN §8 + decision log). Spec amended
  during plan review: R10/R11 (translator writes only `.feature`, writer never `.feature`), R16
  (tightened build-folder skip). Reqnroll 2.4.1/3.1.2 compile `**\*.feature`, hence the `.feature`
  rules for every role. Open items:
  - **Step 4:** commands call scripts by the cwd-relative path (CONFIG.md "Invoking the scripts");
    decide the marker's lifecycle (it stays after a subagent until the next run script); spec drift =
    `ac_lock.py verify sources` exit 3 → ask, `confirm-spec`; snapshot order per CONFIG.md.
  - **Step 5:** init writes `.workflow/config.json` schema 1 (CONFIG.md); spec inputs must not include
    implementation folders (`src/`); the guard only rejects overlaps with `specs/`, `.specify/`,
    `.workflow/`, the AC project and `refsDir`.
  - **Step 7:** confirm the TRX `className` carries the `F00N` namespace segment (assumption A2;
    `summarize_trx.py` falls back to scenario names); run `export_refs.py` for real.
  - v1.0 accepts only `specs/NNN-name` feature folders (timestamp/custom folders rejected); listed with
    the deferred portability issues in the user-level memory.
  - Possible follow-up: guard denial for main-agent writes to `.specify/extensions/ac/**` (now a known
    limit in WORKFLOW §6).
- Step 3 (2026-11-08): decisions 1–8 approved with the spec (DESIGN decision log). Spec amended during
  plan review: R04 (writer gets `Project file: <AC_PROJECT>`; placeholders are the UPPER_SNAKE form of
  their source key), R08 (an entry without an id is an issue, not ignored). Open items:
  - **Step 4:** copy each agent's `## Your task message` template verbatim into its command and test
    that they match; build `<FEATURE_LIST>` and `<SPEC_INPUTS>` with a deterministic join (or a text
    output flag), never by hand; `ac_feature.py --all` fails on any non-feature folder under `specs/`,
    so warn early; marker lifecycle: with a stale marker the main agent could start an AC agent itself
    with its own prompt (descriptions say "never invoke it any other way"; prompt rule only).
  - **Step 5:** init detects and writes `testFramework` (required by the guard and scripts now).
  - **Step 7:** confirm that a class-level `[Scope(Tag)]` scopes step definitions and hooks (Reqnroll
    3.3.4 strips a leading `@`, seen in the dll), that the multi-line task message arrives unchanged,
    and that the `tools:` whitelist keeps `SubagentHandback` (otherwise the hand-back screen never runs).
