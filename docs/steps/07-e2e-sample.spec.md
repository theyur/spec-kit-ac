# Step 7 — End-to-end sample and live run

**Status:** done (2026-11-08; decisions 1–10 approved as drafted; deviations D1–D4 recorded in the plan; live run in [07-e2e-sample.results.md](07-e2e-sample.results.md)) · **Tracker row:** 7 · **Source of truth:** `docs/DESIGN.md`

## Goal

Run the whole AC flow once, for real, in a small .NET project built from `tests/e2e/`, with a live
model in an interactive Claude Code session:

1. `speckit-ac install`, `/speckit-ac-init`, and the live guard smoke test (CT doc §6 item 8).
2. Feature 001 through translate → tests-write → tests-analyze. A planted implementation bug must
   come back as `IMPLEMENTATION_FAULT`. After the fix, everything passes.
3. Feature 002, whose spec intentionally changes 001's behaviour. Feature 001's now-outdated scenarios
   must come back as `SUPERSEDED`.

On the way, close the "Step 7" open items in the tracker, and record what the live run showed in
`docs/steps/07-e2e-sample.results.md`.

Out of scope:

- dogfooding in a real project (step 8);
- release (step 9);
- the spec-kit commands that are not ours (`/speckit-specify`, `clarify`, `plan`, `tasks`,
  `implement`), which the sample replaces with seeded files (decision 1).

## Context

- **DESIGN §9, supported host:** interactive Claude Code only. Headless `claude -p` has no
  `SubagentHandback`, which the smoke test needs. So the user drives the live sessions with a runbook;
  scripts prepare every stage and check its result from the files (user, 2026-11-08).
- **Sample location:** `<e2e-sample>`. It is its own git repository, outside this one,
  so this repo's `CLAUDE.md` and `.claude/` never reach its sessions (user, 2026-11-08).
- **Environment (probed 2026-11-08):** Claude Code 2.1.318, specify 1.0.2, .NET SDK 10.0.403,
  uv 0.11.26, PowerShell 7.6.9.
- **Open items carried into step 7** (tracker notes, steps 2–6):
  - the TRX `className` carries `F00N` (already confirmed in step 5);
  - `export_refs.py` against a real project;
  - a class-level `[Scope(Tag = "F00N")]` scopes step definitions and hooks;
  - the model passes the multi-line `task_message.py` output unchanged (otherwise the guard denies),
    and how it retries if denied;
  - the `tools:` whitelist keeps `SubagentHandback`, and the hand-back screen runs;
  - whether the `Agent` call's `description` reaches the subagent;
  - whether Fable is available for `/speckit-ac-critic`;
  - the dotnet steps of the commands;
  - the hook command runs in Git Bash with `$CLAUDE_PROJECT_DIR` within the 30 s timeout;
  - `/speckit-ac-init` setup, verify and smoke with a live model;
  - the model passes the multi-line smoke prompt unchanged.

## Requirements

### The sample (`tests/e2e/sample/`)

- **S07-R01** A tiny .NET solution, `Shop.slnx`:
  - `src/Shop.Pricing/` — class library, `net10.0`, with one public class
    `DiscountCalculator` and the method `decimal Total(decimal subtotal)`;
  - `tests/Shop.Pricing.Tests/` — xUnit v3 unit tests on VSTest (a recipe verified in step 5), which
    cover subtotals of 50.00 and 200.00 only;
  - `CLAUDE.md` with a short project description;
  - a filled-in `.specify/memory/constitution.md` that includes the testability section offered by
    `/speckit-ac-init`.

  The sample contains no feature implementation: each feature's implementation is a fixture
  (S07-R03).
- **S07-R02** Feature specs, written as spec-kit `spec.md` files (user stories with acceptance
  scenarios, `FR-NNN`), seeded instead of running `/speckit-specify`:
  - **001-order-discount:**
    - FR-001: a subtotal of 100.00 or more gets 10 % off;
    - FR-002: a subtotal below 100.00 gets no discount;
    - FR-003: a negative subtotal is rejected (`ArgumentOutOfRangeException`);
    - FR-004: the total is rounded to 2 decimals, midpoint away from zero.
  - **002-raise-discount-threshold:**
    - FR-001: the discount threshold is 150.00 (previously 100.00, feature 001): a subtotal of
      150.00 or more gets 10 % off, a subtotal below 150.00 gets none;
    - all other rules unchanged.
- **S07-R03** Implementation fixtures (copied in place of `/speckit-implement`), each with unit tests
  that pass:
  - **001-buggy:** uses `subtotal > 100m` instead of `>=` (the planted bug). The unit tests at 50 and
    200 pass; only an AC item at exactly 100.00 catches it;
  - **001-fixed:** `>=`;
  - **002:** threshold 150.00, `>=`.

### Stage tooling (`tests/e2e/`, run from this checkout)

- **S07-R04** `make_sample.py --dest <dir> [--force]`:
  1. refuses an existing non-empty `<dir>` unless `--force` is given, and never deletes anything
     outside `<dir>`;
  2. runs `specify init <dir> --integration claude --script ps --non-interactive`, then copies the
     sample over it;
  3. runs `git init`, then commits;
  4. installs the CLI as a uv tool from this checkout:
     `uv tool install --reinstall --from <repo> speckit-ac` (decision 5);
  5. runs `speckit-ac install` in `<dir>`, then commits;
  6. prints the runbook's first stage.
- **S07-R05** `stage.py --project <dir> <action>`. It is the only way the runbook changes the sample
  outside the slash commands. Each action:
  - `spec <NNN>`: writes `specs/NNN-name/spec.md` and points `.specify/feature.json` at it;
  - `implement <fixture>`: copies the implementation fixture over `src/` and `tests/`;
  - `fix 001`: copies 001-fixed (fallback if the model's own fix is not wanted, decision 10).

  After writing, each action commits with a fixed message (decision 6). It refuses to run when the
  sample has uncommitted changes, and prints what it changed.
- **S07-R06** `check_stage.py --project <dir> <stage>`. It reads only files and prints one PASS / FAIL
  line per check, then exits 0 or 1. It never calls a model. Checks per stage:
  - **`init`**:
    - `.workflow/config.json` exists, with `testFramework` `xunit3` and the runner `vstest`;
    - the AC project builds;
    - `speckit-ac doctor` exits 0.
  - **`smoke`**:
    - `guard.log` shows all three `agent_type` values;
    - `guard.log` shows `SubagentHandback allow` for the translator and the writer;
    - no smoke marker or temporary feature is left behind.
  - **`ac <NNN>`**:
    - `check_acceptance.py` passes;
    - `ac_lock.py verify sources` exits 0;
    - for 001, an item has the boundary input 100.00 with the expected total 90.00 (a WARN, not a
      FAIL, when it is missing; see R07).
  - **`features <NNN>`**:
    - `check_features.py` passes;
    - `ac_lock.py verify features` exits 0;
    - every scenario carries `@F<NNN>`.
  - **`written <NNN>`**:
    - the latest run has `writer-report.md`;
    - the step definitions of `F<NNN>` carry `[Scope(Tag = "F<NNN>")]`;
    - nothing outside the allowlist changed (`changed_files.py` output saved by the command, if
      present).
  - **`analyze <expectation>`**: the latest `judge-report.md` (or the `ac-results.md` totals when all
    passed) matches the expectation:
    - `fault-001`: every failing F001 item is a boundary item with the verdict
      `IMPLEMENTATION_FAULT`;
    - `pass`: every result passed;
    - `superseded-002`: every F001 failure is `SUPERSEDED` and every F002 result passed.

    The real verdict table is always printed.
- **S07-R07** `tests/e2e/RUNBOOK.md`: the stages in order, each with three parts — the commands to run
  (terminal / Claude Code), the human decisions to make (approve, skip/fix), and the `check_stage.py`
  call.
  - Approvals follow the commands' own rules: the user reviews `acceptance.md` and the features
    before locking.
  - For 001, the review asks for an item at exactly 100.00 if the draft has none, which is the
    realistic human check that the planted bug depends on.
  - The stages:
    1. make;
    2. session A: `/speckit-ac-init`;
    3. session B: `/speckit-ac-init smoke` plus the manual checks;
    4. 001: `spec`, translate phase 1, `/speckit-ac-critic ac`, lock, phase 2,
       `/speckit-ac-critic features`, lock, `implement 001-buggy`, tests-write, tests-analyze (→
       fault-001), fix, tests-analyze (→ pass);
    5. 002: the same without the critics, `implement 002`, tests-write, tests-analyze (→
       superseded-002);
    6. `speckit-ac doctor`.
  - Each stage says what to note for the results file: denials and retries, the time per command,
    anything unexpected.

### Verification without a model

- **S07-R08** Opt-in `tests/test_e2e_sample.py` (`SPECKIT_AC_DOTNET_E2E=1`; needs dotnet, specify, uv,
  git, NuGet). It builds the sample in `tmp_path` with `make_sample.py` (with a flag that uses
  `uv run speckit-ac` from the checkout instead of the uv tool install) and checks:
  - the solution builds;
  - the unit tests pass with 001-buggy, 001-fixed and 002;
  - **the sample discriminates:** hand-written reference AC files (`tests/e2e/reference/`: F001 and F002
    features plus step definitions, used only by this test and never copied by `make_sample.py`), run
    with the config's `acTestCommand`, show:
    - 001-buggy → only the F001 100.00 scenario fails;
    - 001-fixed → all pass;
    - 002 → the F001 scenarios in [100.00, 150.00) fail and F002 passes;
  - `check_stage.py` returns the expected PASS / FAIL on those runs, with a fabricated
    `judge-report.md` for each `analyze` expectation.
- **S07-R09** Non-opt-in unit tests for `stage.py` and `check_stage.py`, run on fabricated project
  trees: the refusals, the files written, and every check's PASS and FAIL path.

### Live run and results

- **S07-R10** The user runs the runbook. I check every stage with `check_stage.py` and with the run
  folders (reports, `guard.log`).
  - A failure in this package (a script, a command text, the guard, deploy) is fixed in this step,
    with a regression test, and the stage is re-run. If the fix needs a change to `docs/DESIGN.md`,
    stop and ask first.
  - A model's wrong judgement (for example a wrong verdict) is recorded, not "fixed" by loosening a
    check. It goes into the results with the judge's reasoning.
- **S07-R11** `docs/steps/07-e2e-sample.results.md` records:
  - the environment and the model(s);
  - a per-stage outcome table;
  - each step 7 open item with its answer (confirmed / refuted / not observed);
  - denials and retries seen in `guard.log`;
  - the time per command;
  - fixes made, and new findings.
- **S07-R12** Docs:
  - the tracker (row 7, notes);
  - WORKFLOW known limits, if the run shows new ones;
  - README status line;
  - `tests/e2e/README.md` (what is here, how to start).

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S07-A01 | `uv run pytest -q --tb=short` passes (non-opt-in suite incl. R09) | R05, R06, R09 |
| S07-A02 | With `SPECKIT_AC_DOTNET_E2E=1`, `test_e2e_sample.py` passes: the sample builds, the unit tests pass for all three fixtures, and the reference AC show the expected failures | R01–R04, R08 |
| S07-A03 | Live: `check_stage.py init` and `smoke` PASS. All three roles hand back, and the manual checks (main-agent read, `Explore` read, missing interpreter) block | R10 |
| S07-A04 | Live: 001 ends with `analyze fault-001` PASS, then `analyze pass` PASS after the fix | R10 |
| S07-A05 | Live: 002 ends with `analyze superseded-002` PASS | R10 |
| S07-A06 | The results file answers every step 7 open item; the tracker is updated | R11, R12 |

A04 and A05 depend on the model's judgement. If the judge picks a different verdict, the check prints
it and fails. Then the step is not "done": the user decides what to do (re-run, change a prompt
through a separate change, or accept with the finding recorded).

## Out of scope

- spec-kit's own `/speckit-specify`, `clarify`, `plan`, `tasks`, `implement` (seeded; decision 1);
- frameworks and runners other than xUnit v3 on VSTest (the matrix was step 5);
- `TRANSLATION_FAULT`, `TEST_FAULT`, `SPEC_AMBIGUITY`, `UNEXPRESSIBLE` and the writer's feedback
  loop: not planted. If they happen, they are recorded;
- the optional `extensions.yml` hooks (checked in step 1);
- uninstall from the sample (round trip covered in step 6);
- a CI job for the opt-in tests.

## Decisions taken in this spec (confirm on approval)

1. **Seed spec-kit's own steps.** `spec.md` and `feature.json` are written by `stage.py`, and the
   implementation comes from fixtures. Only our commands run live, which keeps the planted bug and
   the cost under control. The sample stays on one branch (no spec-kit feature branches).
2. **Sample:** `Shop.Pricing` with `DiscountCalculator.Total`, on xUnit v3 with VSTest.
3. **Planted bug:** `>` instead of `>=` at 100.00. It is only caught if the AC have the boundary
   item; the runbook's review asks for it if it is missing (R07).
4. **Feature 002 states the change:** "(previously 100.00, feature 001)". This is a realistic change
   request, and it gives the judge what `SUPERSEDED` needs.
5. **The CLI is installed as a real uv tool** from this checkout (`uv tool install --reinstall`, in
   the user's tool directory), as a user would install it; step 8 needs it too. To undo it:
   `uv tool uninstall speckit-ac`.
6. **Stage commits.** `stage.py` and `make_sample.py` commit in the sample repo (a throwaway repo
   outside this one), so each stage starts from a clean tree and `changed_files.py` sees only the
   command's own changes.
7. **Reference AC files** prove that the sample can discriminate, before any money is spent on a live
   run. They live only in `tests/e2e/reference/` and are never copied into the live sample.
8. **Model:** the user's session default for the main agent. The agents' own `model:` keys apply, and
   the critic asks for Fable. Their availability is recorded, not enforced.
9. **Fixes found by the live run** are made in this step, if they need no DESIGN change (R10).
10. **The fix after `IMPLEMENTATION_FAULT`:** the user asks the main agent in plain words to fix the
    implementation, as the command suggests. `stage.py fix 001` is the fallback.
