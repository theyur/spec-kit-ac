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
| 4 | Commands: `translate` (two phases), `tests-write`, `tests-analyze` (all / `--current`), `critic` (port + `ac`, `features` stages); `extension.yml` with optional hooks | done | [04-commands.spec.md](04-commands.spec.md) | [plan](../../.claude/plans/04-commands.plan.md) (critic: REVISE → APPROVE, 2 rounds; all findings accepted) | 2026-11-08: 397 tests pass (CPython 3.14 and 3.11.15). New `test_commands.py` (36): manifest (version = package, commands ↔ files, five optional hooks), command texts (scripts/subcommands/flags exist, subagent start order, step order, no path spec-kit would rewrite, critic hard rules word for word), walks of translate phase 2 / tests-write / tests-analyze through the real guard, and a real `specify init --script ps` + `extension add --dev` (four skills, bodies unchanged, hooks registered). `task_message.py`, `check_acceptance.py`, `--only-current`, marker deletion and guard launch tests (incl. the writer-launch regression). Mutation spot-check: dropping the launch exemption, the marker deletion or the FR coverage check, swapping two start steps, a bare `scripts/` path all fail tests. Not run: commands with a live model, dotnet steps (step 7) | |
| 5 | `/speckit-ac-init`: detection, questions, AC project scaffolding per framework/runner, config, automatable verification (CT doc §6 items 1, 3–7), smoke-test instructions | done | [05-init.spec.md](05-init.spec.md) | [plan](../../.claude/plans/05-init.plan.md) (critic: REVISE ×3, no BLOCKER; all 31 findings accepted) | 2026-11-08: 495 tests pass, 8 opt-in skipped (CPython 3.14 and 3.11.15). New `test_init.py` (92): detection (environment problems incl. timestamp option, msbuild evaluation of hand-written solutions without restore, test projects known by packages, CPM pins, blockers, several solutions), config per recipe and refusals, csproj/props rendering per recipe, package version rules, managed blocks, `init_verify` with stubbed dotnet (cleanup, leftovers, warnings-as-errors), smoke marker + every smoke action against the real guard. **Real matrix** (`test_init_e2e.py`, `SPECKIT_AC_DOTNET_E2E=1`, SDK 10.0.403, NuGet): 7 pairs pass every verification check (one with CPM, one with root `TreatWarningsAsErrors`); xUnit v2 on MTP refused. Mutation spot-check: 7 of 7 caught. Not run: the command with a live model, the live smoke test (step 7) | |
| 6 | CLI + deploy: `install` / `uninstall` / `upgrade` / `doctor`, settings.json merge, marked blocks, deploy manifest; install→uninstall round-trip leaves a temp project byte-identical | done | [06-cli-deploy.spec.md](06-cli-deploy.spec.md) | [plan](../../.claude/plans/06-cli-deploy.plan.md) (critic: REVISE → REVISE → APPROVE, 3 rounds; all 19 findings accepted) | 2026-11-08: 591 tests pass, 8 opt-in skipped (CPython 3.14 and 3.11.15). New `test_deploy.py` (92, fake spec-kit that mirrors the probed `add` / `remove`, incl. its `settings.json` rewrite): every prerequisite and refusal, rollback, skill patch, settings merge, `CLAUDE.md` block, uninstall order by state, kept agents, leftovers, re-run after a failure, upgrade, every doctor check, CLI root/ASCII. **Real spec-kit** (`test_deploy_real.py`, specify 1.0.2, uv, git): fresh and pre-populated projects round-trip byte-identical; planted `__pycache__`/`*.pyc` never installed; committed skills are mode 100644, a `core.symlinks=false` + `autocrlf=true` clone gets patched skills and `doctor` exits 0; upgrade re-patches; uninstall leaves no skill; the wheel ships `.extensionignore`. Mutation spot-check: 9 of 9 caught. Not run: install with a live Claude Code session (step 7) | |
| 7 | End-to-end sample in `tests/e2e/`: tiny .NET lib + spec-kit; one feature through the full flow with a planted implementation bug (→ `IMPLEMENTATION_FAULT`); a second, contradicting feature (→ `SUPERSEDED`); live guard smoke test (CT doc §6.8) | done | [07-e2e-sample.spec.md](07-e2e-sample.spec.md) | [plan](../../.claude/plans/07-e2e-sample.plan.md) (critic: REVISE ×3 → APPROVE, 4 rounds, the 4th requested by the user; all 26 findings accepted) | 2026-11-08, before the live run: 667 tests pass, 9 opt-in skipped (CPython 3.14 and 3.11.15). New `test_e2e_tools.py` (76): `stage.py`, `check_stage.py` (every stage's PASS and FAIL paths, tolerant judge-key parsing, fenced Gherkin tables, `--only-current`), `make_sample.py` (destination rules, payload comparison). Opt-in `test_e2e_sample.py` (`SPECKIT_AC_DOTNET_E2E=1`, 62 s): real `specify init` + `speckit-ac install`, init's scripts, reference AC: 001-buggy fails only F001/AC-001 (100.00), 001-fixed passes, 002 fails F001/AC-001 and AC-005 and passes F002; `check_stage analyze` right on fabricated judge reports. Mutation spot-check: 12 of 12 caught. **Live run 2026-11-08** ([results](07-e2e-sample.results.md); user-driven, Claude Code 2.1.318, Fable 5.1): smoke PASS (all three roles handed back; missing interpreter blocked every call); 001: the planted bug caught at exactly 100.00, judge `IMPLEMENTATION_FAULT` (high), fix → 17/17 pass; 002: 7 F001 examples in [100.00, 150.00) judged `SUPERSEDED` (high), F002 11/11 pass; doctor 0 FAIL; one guard denial in the flow (hand-back screen, retried). Four e2e-tooling fixes, no package defect; final suite 671 passed, 9 opt-in skipped (3.14 and 3.11.15) | | |
| 8 | Dogfood in Habit Tracker (`<habit-tracker>`, separate branch/PR there): install, `/speckit-ac-init`, its AC-surface + test-DB ADR, Sonar exclusions for step-definition folders | done | [08-dogfood-habit-tracker.spec.md](08-dogfood-habit-tracker.spec.md) · [results](08-dogfood-habit-tracker.results.md) | [plan](../../.claude/plans/08-dogfood-habit-tracker.plan.md) (critic: REVISE ×3, no BLOCKER; all 14 findings accepted, one in part) | 2026-11-09: 676 tests pass, 9 opt-in skipped (CPython 3.14 and 3.11). Commands wait for the hand-back (`test_waits_for_the_hand_back`). In HT: `doctor` 0 FAIL, every settings key and hook kept; `/speckit-ac-init` 17/17; live smoke PASS (3 roles + 3 manual checks); HT build, tests, `selftest.ps1`, `oracle.ps1` pass before and after. No package defect found | |
| 9 | Release: tag `v0.1.0`, GitHub repo, README install line | done (pending tag) | [09-release.spec.md](09-release.spec.md) | [plan](../../.claude/plans/09-release.plan.md) (critic: REVISE ×3 → APPROVE, 4 rounds, the 4th requested by the user; all findings accepted) | 2026-11-10: A01–A06 verified, A07–A08 pending the tag. History rewritten (15 commits, the check script passes) and `master` pushed; repo public; PR 1: `test (3.11)`, `test (3.14)`, `SonarCloud Code Analysis` (gate passed) and `CodeQL` green; ruleset `master protect` active with those four checks. 786 tests pass, 9 opt-in skipped (CPython 3.14 and 3.11); 10 of 10 mutations of the release files caught. Fixed on the PR: two Sonar S8786 regexes and S2083 (skill folder leading outside `.claude/skills`), each with a regression test | |

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
- Step 4 (2026-11-08): decisions 1–9 approved with the spec (DESIGN decision log). Spec amended during
  plan review: R08 (the marker is deleted only once the check ran; a usage error keeps it), R09 (an FR
  can't be "not testable"). The step 3 open items for step 4 are closed: the commands no longer copy
  templates — `task_message.py` fills them (deterministic joins, `FEATURE_LIST` lazy) and the guard
  enforces the exact message; tests-analyze runs `ac_feature.py --all` first; the marker ends at the
  check. Found while drafting: the guard's step-definition text rule blocked the main agent's launch
  of the writer (its message names `StepDefinitions/`); fixed by the launch rule. spec-kit 1.0.2 drops
  `argument-hint` on `--dev` installs (probe). Open items:
  - **Step 5:** `speckit.ac.init` into `extension.yml` and `NAMES` in `test_commands.py`;
    `acTestCommand` must write `{analyzeDir}/ac-results.trx` (logger option per runner).
  - **Step 6:** deploy may also patch `argument-hint` into the skills (cosmetic) along with
    `disable-model-invocation`.
  - **Step 7:** live: a model passes the multi-line `task_message.py` output unchanged (else the guard
    denies; retry behaviour); whether the `Agent` call's `description` reaches the subagent; Fable
    availability for `/speckit-ac-critic`; the dotnet steps of the commands (build, unit tests,
    `export_refs.py`, `acTestCommand`).
- Step 5 (2026-11-08): decisions 1–10 approved with the spec (DESIGN §9 changed: init writes the
  `.gitignore` / `.gitattributes` blocks; decision-log row). Deviations recorded in the plan: D1 the
  warnings-as-errors check uses CS0168 (not a nullable warning), only when the **evaluated** ref-mode
  `TreatWarningsAsErrors` is true; D2 `FrameworkReference`s rendered, scaffold re-evaluates projects;
  D3 surface package versions before the unit tests'; D4 test projects also known by framework packages
  (`IsTestProject` is empty before a restore). Found and fixed on the way:
  - `export_refs.py` never imported `json` (step 2); now covered by `init_verify.py` item [4] and a test.
  - `summarize_trx.py` matched TRX test names to scenario titles literally; NUnit names tests after the
    generated method (`UnboundStep`, `DoublingOtherNumbers("3",…)`), so NUnit results lost their tags or got
    the wrong ones. The match now ignores case, spaces and punctuation (step 2 code; new test).
  - The plain `xunit.v3` package fails under VSTest on the .NET 10 SDK; the recipe uses `xunit.v3.mtp-off`.
    NUnit on MTP needs `Microsoft.Testing.Extensions.TrxReport` for a TRX.
  - Script output must stay ASCII (Windows console code page); `__pycache__` next to the installed scripts
    is git-ignored by the managed block and skipped by the leftover check.
  - Confirmed: the TRX `className` carries the `F00N` namespace segment for all seven pairs (step 2 A2).
  Open items:
  - **Step 6:** `uninstall` removes the managed blocks with `aclib.remove_block`; `doctor` may re-run
    `init_verify.py`; deploy must exist before `/speckit-ac-init smoke` can pass (agents, guard registration).
  - **Step 7:** run `/speckit-ac-init` (setup, verify, smoke) with a live model; the smoke test live,
    including the manual checks; confirm the model passes the multi-line smoke prompt unchanged.
  - Known limit (WORKFLOW §6): a CRLF file locked before git normalises it does not verify in an LF
    checkout; normalising text in `ac_lock.py` is deferred.
- Step 6 (2026-11-08): decisions 1–8 approved with the spec (DESIGN §9 + decision log). Deviations recorded
  in the plan: D1 manifest / doctor hashes fold CRLF to LF (this machine's git has `core.autocrlf=true`, so a
  clone checks the LF files out as CRLF); D2 `preexisting` also covers `.specify/extensions/`, each agent file,
  `settingsCreatedKeys`; D3 `settingsNewline` (below). Found on the way:
  - spec-kit **rewrites an existing `.claude/settings.json`** on every `extension add` / `remove`
    (`specify_cli/events.py` `_safe_write_json`: `json.dumps(indent=2)` in text mode, so CRLF on Windows and
    non-ASCII escaped). The step 1 spike (3.5) missed it because its file was already in that form. Install
    records the file's line ending before spec-kit touches it, registers in that ending, and uninstall
    restores it after `remove`.
  - a fresh `specify init` has no `.specify/extensions/`; `extension add --force` leaves an empty `.backup/`;
    `extensions.yml` and `.registry` are written with CRLF.
  - spec-kit honours `.extensionignore`; the payload ships one, so a compiled wheel's bytecode never reaches
    a project.
  - DESIGN §9 verification done: git records the patched skills as regular files (mode 100644), a clone
    with symlinks off gets them intact, and `specify extension remove` deletes the real files.
  Open items:
  - **Step 7:** install into the e2e sample with the real CLI (`uv tool install` from the checkout), start a
    new session, run `/speckit-ac-init` and the live smoke test; confirm the hook command runs in Git Bash
    with `$CLAUDE_PROJECT_DIR` and the 30 s timeout.
  - Known limits (WORKFLOW §6): a `settings.json` not in 2-space style keeps its content but not its
    formatting; a `CLAUDE.md` / `.gitignore` without a final line break gets one back; a user's own
    `specify integration upgrade` reverts the skill patch until `speckit-ac upgrade`.
- Backlog (user, 2026-11-08): **critic model choice at `/speckit-ac-init`.** Offer two options and store the
  answer in `.workflow/config.json`: a custom model and effort for the critic sub-agent (default Fable / high,
  as now), or the same model as the main agent (no `model` / `effort` passed). `/speckit-ac-critic` reads it
  instead of the hard-coded Fable. Needs a DESIGN §6–7 / CONFIG.md change; not scheduled.
- Step 7 live-run finding (2026-11-08): Claude Code showed **every** AC subagent and critic as backgrounded,
  although the commands ask for `run_in_background: false` (the model passed the string `"false"`). The main
  agent waited each time, so nothing broke. Candidate follow-up: the commands state "wait for the subagent's
  result before the next step", since `changed_files.py check` deletes the marker.
- Step 7 (2026-11-08): decisions 1–10 approved with the spec; deviations D1–D4 recorded in the plan (base unit
  test only constructs; `stage.py commit`; 002 has FR-001 + FR-002; `check_stage analyze <expectation> <NNN>`).
  Live run results, every step 2–6 open item answered: [07-e2e-sample.results.md](07-e2e-sample.results.md).
  New WORKFLOW §6 limits: subagents run in the background; the hook command runs in Git Bash. Open items:
  - **Step 8:** the background-subagent follow-up above (command text: wait for the hand-back); the Agent
    `description` reaching the subagent and a hook timeout on a cold uv start are still unobserved.
- Step 8 (2026-11-09): decisions 1–9 approved with the spec. Deviations recorded in the plan:
  - D1: the wait sentence names each command's own next step;
  - D2: the tool was built from HEAD plus the uncommitted edits;
  - D3: the surface also lists `HT.Domain` (detection's proposal, user's choice).

  Habit Tracker changes are uncommitted on `infra/ac-workflow-setup`: install, init, ADR 0003 (AC surface;
  `HT-AC` on `.\COLL1`, rebuilt per run), the Sonar exclusion. Results:
  [08-dogfood-habit-tracker.results.md](08-dogfood-habit-tracker.results.md). Answered: the commands now wait
  (subagents still run in the background; the main agent waited); the `Agent` description appears only in Claude
  Code's subagent metadata. Open items:
  - **HT PR:** [theyur/agentic-engineering-course-exam#16](https://github.com/theyur/agentic-engineering-course-exam/pull/16) (commit `2752ce9`); S08-A08 met: Sonar and CodeQL green, 0 issues. The AC project holds no `.cs` yet, so whether
    CodeQL reports step definitions shows on the first feature's PR. Copilot review and merge: the user.
  - **Copilot review on PR 16:** 2 of 3 findings were valid and are fixed in the package, then deployed with
    `speckit-ac upgrade`:
    - the guard and the scripts now reject spec inputs that overlap implementation folders after hand edits;
    - the scaffold rollback also covers a pre-existing empty AC folder.

    The third finding, the root `dotnet-tools.json`, was a false positive: a fresh clone restores and runs ilspycmd.
    Details in the results file.
  - **Copilot re-review on PR 16:** 7 findings. Fixed in the package and deployed with `speckit-ac upgrade`:
    - the hand-back screen also catches qualified attributes and declarations;
    - `export_refs.py` matches only real `bin` / `obj` folders;
    - `refsDir` may not overlap source, the AC project or the spec-kit folders;
    - every project and solution path must be project-relative;
    - `smoke_test.py end` leaves a real run alone;
    - `/speckit-ac-tests-analyze` ends its run with the new `changed_files.py clear` when it stops before the judge.

    The xunit3/MTP TRX finding was a false positive: the opt-in end-to-end test passes. Details in the results file.
  - **Copilot third review on PR 16:** 2 still open, 11 new in unchanged code. The user chose to fix the 7 real ones:
    - an empty TRX fails the analysis;
    - the AC project folder, `acProject` and `acRefBuildCommand` are validated in aclib and the guard;
    - `@AC-` tags trace to `acceptance.md` items;
    - the `InternalsVisibleTo` scan compares extensions case-insensitively;
    - HT disables xUnit parallelization (`xunit.runner.json`).

    Not changed: the judge allowlist finding was a false positive, the main-agent Bash `/./` path is a documented
    limit.
  - **Decided (user, 2026-11-09): option B.** `new_run.py` / `new_analyze.py` refuse while another run's marker
    exists, instead of replacing it. The three commands stop and report. The user ends an interrupted run with
    `changed_files.py clear`. Recorded in WORKFLOW §3.9 and the DESIGN decision log. Deployed to HT `5203f29`.
  - **Two gaps found by HT's `/process-pr-feedback`, closed:**
    - an AC folder that is an existing project (overlaps `src/`, holds another `.csproj`, or `acProject` is a
      surface or unit-test project) is rejected;
    - the guard's shell rule normalises `./` and `\`, and catches `cd <ac> && cat StepDefinitions/…`.
  - **Copilot fifth review on PR 16:** two findings.
    - Paths outside the checkout: a false positive, already refused everywhere. Tests added.
    - `refsDir` on source: the loaders already refused it before `rmtree`. Init's writer did not, and it now
      validates against the project on disk too.
  - **Copilot sixth review on PR 16:** five findings in unchanged code. Fixed:
    - every acceptance item needs a scenario, an Issues row (`check_features.py`) and, at the lock, a
      recorded skip;
    - the scaffold writes `xunit.runner.json` (sequential collections) for xUnit;
    - the agent quotes the solution path.

    Declined: NETSDK1022 for `None` items (a scratch build shows no error).
  - **PR 16 merged by the user (2026-11-09)** after a final Copilot review with no new findings (head `9cf5d6e`).
  - **Review scope:** Copilot keeps finding issues in code unchanged since the first review. After this round,
    further package review belongs in spec-kit-ac's own repository (step 9), not the Habit Tracker PR.
  - **Candidate follow-up:** init's spec-input question steered toward `SPEC.md` and away from ADR 0003 (it says
    "describe the domain"). Name test-environment documents as allowed inputs (DESIGN §4 wording).
  - Not observed: a hook timeout on a cold uv start (the cache was warm; the guard took ≈ 0.1–0.3 s per call).
- Step 9 (2026-11-10): decisions 1–7 approved with the spec. Answers at the gates:
  - **Rewrite (decision 1, extended by the user at gate 3(b)):** §10 of the reference doc and **every local
    absolute path** were replaced by placeholders before the first push. These were the original project, the
    Habit Tracker, e2e-sample and course checkouts, `<projects>`, the user profile `~`, the NuGet cache and the
    scratchpad. `CLAUDE.local.md` (git-ignored) maps them on this machine.
  - **Rewrite result:** 15 commits with identical authors, dates and full messages, 21 files changed. The check
    script passed: no path, §10 token or secret-shaped string in any commit or message, and every blob is LF.
    Pytest gave 750 passed, 9 skipped on 3.14 and 3.11. The new HEAD (`1162c7e`) equals the dry run's.
  - **Hashes:** they changed. The two cited in the step 8 files are remapped (`9804ab8` → `88bad5b`,
    `a8986a9` → `65e3454`). Older specs and plans keep the pre-rewrite hashes as history.
  - **Version rule (accepted):** `.dev0` after a release, and the README pins the newest dated changelog
    version (DESIGN §9).
  - **Deviations (plan):**
    - D1: `setup-uv` is pinned to `v10.3.3`, because the action has no major tag;
    - D2: `sonar.sources=src,tools`;
    - D3: the release tests key off the newest released changelog version;
    - D4: the spec's "11 files" corrected to 9;
    - D5: the local paths were added to the rewrite.
  - **Plan critic:** REVISE ×3 → APPROVE in 4 rounds; the 4th was requested by the user, who also asked to
    stop on any round-3 MAJOR. All findings were accepted.
  - **Open item:** the post-release PR, with the A07/A08 results, the release URL, the `0.1.1.dev0` bump with an
    `[Unreleased]` section, and a changelog date fix if the tag falls on a later day than 2026-11-10.
  - **Standing OK (user, 2026-11-10):** follow-up fix commits on the release PR may be pushed without a new ask.
    Each push runs the leak scan first, and each fix is reported. CodeQL default setup is enabled by the agent
    once the repository is public.
  - **PR 1 gates:** the Sonar baseline (the user re-ran the automatic analysis of `master` once) showed two S8786
    regexes and an S5332 false positive (the TRX XML namespace URI), left for the user. The PR analysis then
    found S2083 in `patch_skills()`. All three real findings are fixed with tests. Ruleset `master protect` was
    created after all four checks reported.
