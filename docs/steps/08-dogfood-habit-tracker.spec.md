# Step 8 — Dogfood in Habit Tracker

**Status:** done (2026-11-09; decisions 1–9 approved as drafted; deviations D1–D3 in the plan; results in [08-dogfood-habit-tracker.results.md](08-dogfood-habit-tracker.results.md); A08 met on Habit Tracker PR 16) · **Tracker row:** 8 · **Source of truth:** `docs/DESIGN.md`

## Goal

Install spec-kit-ac into its first real consumer, Habit Tracker
(`<habit-tracker>`), and leave that repository ready for its first
feature to go through the AC flow:

1. `speckit-ac install`, `/speckit-ac-init` and the live guard smoke test, in a real project that has
   its own hooks, plugins, worktrees and PR gates;
2. Habit Tracker's ADR for the AC surface and the AC test database;
3. Sonar exclusions for the AC project;
4. the step 7 follow-up in the commands: wait for each subagent's hand-back.

What the run shows goes into `docs/steps/08-dogfood-habit-tracker.results.md`.

Out of scope:

- a Habit Tracker feature through the flow (user, 2026-11-09: setup only; the first feature is normal
  course work);
- running the AC tests in Habit Tracker's CI (user, 2026-11-09: local only);
- the critic model choice at init (backlog);
- release (step 9).

## Context (inspected 2026-11-09)

- **Habit Tracker:** skeleton only.
  - Four projects (`HT.Domain`, `HT.Application`, `HT.Persistence`, `HT.Ui`), with no domain code yet.
  - `tests/HT.UnitTests` has no tests and no `IsTestProject`. `tests/HT.ArchitectureTests` uses
    ArchUnitNET. Both are xUnit 2.9.3 on VSTest (`xunit.runner.visualstudio` 3.1.4,
    `Microsoft.NET.Test.Sdk` 17.14.1).
  - The root `Directory.Build.props` sets `net10.0`, `Nullable`, `ImplicitUsings` and
    `TreatWarningsAsErrors`.
  - spec-kit 1.0.2 with `--script ps` and sequential numbering. No `specs/` folder yet.
- **Its Claude setup** (`.claude/settings.json`):
  - PreToolUse hooks `architecture-gate.ps1` on Bash and PowerShell (timeout 120 s) and
    `block-pr-review.ps1` on Skill;
  - a UserPromptExpansion hook;
  - permission denies, `skillOverrides`, and the `sdlc` plugin from a local marketplace;
  - git worktrees under `.claude/worktrees/` (git-ignored; the guard maps worktree paths, step 2).
- **Its rules** (its `CLAUDE.md`):
  - material architectural changes go in an ADR (`docs/adr/NNNN-*.md`; 0001 and 0002 exist);
  - ARCHITECTURE §9 leaves the integration-test database library deliberately open, and SQLite is
    ruled out;
  - one branch per task, PRs against `master`;
  - commits run the architecture tests through `.githooks/pre-commit`;
  - PR review goes through its `/process-pr-feedback` (SonarQube Cloud + CodeQL, then Copilot);
  - the user requests reviews and merges.
- **Branch:** `infra/ac-workflow-setup` exists, matches `master`, and has no commits. The untracked
  `GITHUB-SETUP.md` belongs to the user.
- **CI:**
  - `.github/workflows/sonar.yml` builds and tests `HabitTracker.slnx` on ubuntu, with
    `sonar.exclusions=".specify/**"`;
  - CodeQL runs as default setup, with no build (ADR 0001).
- **AC project placement:** init keeps the AC project outside the solution (CONFIG `acProjectDir`),
  so the solution build in CI never builds it.
- **Test database:** SQL Server 17.0 Developer, named instance `.\COLL1`, integrated security.
  - The user created `HT-AC` (empty) for the AC tests; `HT` is the app's own database.
  - `COLL1\theyur` is `db_owner` on both.
  - Probed with `sqlcmd -S .\COLL1 -E -C` on 2026-11-09; plain `COLL1` fails, because that names the
    default instance.
- **Open items carried into step 8** (tracker):
  - the commands should say "wait for the hand-back" (in step 7 every subagent ran in the background);
  - whether the `Agent` description reaches the subagent;
  - a hook timeout on a cold uv start.

## Decisions to approve

1. **Branch:** work on `infra/ac-workflow-setup` in Habit Tracker. `GITHUB-SETUP.md` stays untouched
   and is never staged.
2. **AC surface:** `HT.Application` (its use cases) and `HT.Persistence`. `HT.Persistence` is only
   for its public composition and database-reset entry points; `HT.Domain` comes in as a dependency
   (`export_refs.py` adds dependencies). `HT.Ui` is a host and stays out (WORKFLOW §0).
3. **AC test database (the ADR):**
   - **Where:** `HT-AC` on `.\COLL1`, never `HT`.
   - **Reset:** the schema is dropped and rebuilt by EF Core migrations at the start of every AC run.
   - **One run at a time:** the AC tests run sequentially, since they share one database.
   - **Connection:** the AC tests read it from the `HT_AC_CONNECTION` environment variable. When it is
     unset they use `Server=.\COLL1;Database=HT-AC;Integrated Security=True;TrustServerCertificate=True`.
     Integrated security means no secret is involved.
   - **What step definitions may use:** only use cases and those entry points. They never use the
     `DbContext` directly, for arranging or for asserting.
   - **First persistence feature:** it must add the public entry points (composition with a
     connection string, and the reset).
4. **Extra spec input:** the ADR (`docs/adr/0003-acceptance-tests.md`). Without it the isolated
   writer can't know how to build the system or reset the database. It describes the test
   environment, not the code.
5. **AC tests run locally only.** The main agent runs them through `/speckit-ac-tests-analyze`; CI
   does not.
6. **Sonar:** add the AC project folder (`tests/HT.AcceptanceTests/**`) to `sonar.exclusions`, with a
   comment explaining why.
   - Translator and writer own its files, and the main agent may not edit them (guard), so an issue
     there could not be fixed in the PR flow.
   - CI doesn't build the project today, so this is a safeguard; the PR's Sonar run shows whether
     anything from it is reported.
7. **Who does what** (as in step 7):
   - I run the CLI (`uv tool install`, `speckit-ac install` / `doctor`) and check the results from the
     files.
   - You run `/speckit-ac-init` and `/speckit-ac-init smoke` in new Claude Code sessions in Habit
     Tracker.
8. **Defects found on the way are fixed here**, in spec-kit-ac, with tests (step 7 decision 9).
   Habit-Tracker-only adjustments go on its branch.
9. **Commits:** spec-kit-ac commits only when you ask. In Habit Tracker, commits and the PR also wait
   for your request, then follow its rules: plain `git commit`, the pre-commit hook, `/process-pr-feedback`
   driven by you, and you merge.

## Requirements

### spec-kit-ac

- **S08-R01** The five commands that start a subagent say how to wait for its hand-back. The commands
  are `translate`, `tests-write`, `tests-analyze`, `critic` and `init` smoke. Each one says:
  - wait for the subagent's hand-back (its result) before any further step;
  - if the tool reports that the subagent runs in the background, make no other tool call until its
    result arrives;
  - never run `changed_files.py check` before then.

  A test in `test_commands.py` checks that each of these commands contains this text.
- **S08-R02** Before the install, reinstall the uv tool from the checkout at the current `HEAD`.
  `speckit-ac --version` and `doctor` run from the tool, not the checkout's `.venv`.
- **S08-R03** Every defect the run exposes in the package is fixed here, with a regression test.
  Every deviation is recorded in the plan.
- **S08-R04** `docs/steps/08-dogfood-habit-tracker.results.md` records:
  - the environment;
  - the outcome of each stage;
  - the open items above, answered or "not observed";
  - the guard log summary;
  - how our guard and Habit Tracker's hooks interact;
  - the fixes, findings and what was not covered.
- **S08-R05** Updates on completion:
  - tracker row 8 and notes;
  - a WORKFLOW §6 entry for any new known limit;
  - the README status line.

### Habit Tracker (`infra/ac-workflow-setup`)

- **S08-R06 Preflight:**
  - the branch is checked out and the tree is clean apart from `GITHUB-SETUP.md`;
  - the solution builds and its tests pass before anything changes, so later failures can be told
    apart.
- **S08-R07 Install:** `speckit-ac install` succeeds and `speckit-ac doctor` reports 0 FAIL. In
  `.claude/settings.json`:
  - every existing key and hook entry is kept;
  - the guard registration comes last.

  `CLAUDE.md` gets the marked block. The diff contains only what the deploy manifest lists.
- **S08-R08 ADR:** `docs/adr/0003-acceptance-tests.md` follows the format of ADR 0001 (Status,
  Context, Decision, Consequences). It records:
  - decisions 2–5;
  - which part of ARCHITECTURE §9 it settles: the AC test database, not the integration tests';
  - what the first persistence feature must provide.

  It is written before init, because init checks spec inputs.
- **S08-R09 Init** (you, live): `/speckit-ac-init` ends with every verification line passing, and the
  values match:
  - solution `HabitTracker.slnx`;
  - surface `HT.Application` and `HT.Persistence`;
  - unit-test projects as detected, both proposed;
  - `xunit2` on VSTest, `net10.0`;
  - AC project `tests/HT.AcceptanceTests`;
  - the default refs folder;
  - spec input: the ADR.

  The AC project builds with `TreatWarningsAsErrors` from the root props. The `.gitignore` and
  `.gitattributes` blocks are written.
- **S08-R10 Smoke** (you, live, in a new session): `/speckit-ac-init smoke` passes, including the
  three manual checks.
  - The guard log shows each AC role's expected decisions.
  - Habit Tracker's `architecture-gate.ps1` runs alongside the guard and blocks nothing in the smoke
    flow.
  - From the transcript, record: the hook latency of the first guard call, and whether the `Agent`
    description reaches the subagent.
- **S08-R11 Sonar:** `sonar.yml` gets the exclusion from decision 6 and nothing else. The existing
  exclusions and the coverage settings stay as they are.
- **S08-R12 Habit Tracker checks after the change:**
  - `dotnet build HabitTracker.slnx` and `dotnet test HabitTracker.slnx` pass (the AC project is not
    in them);
  - `pwsh tools/guard-oracle/oracle.ps1` and `tools/pr-gates/selftest.ps1` still print `PASSED`;
  - `git status` shows only the files from install, init, the ADR and `sonar.yml`.

## Acceptance checks

- **S08-A01** The S08-R01 text is in all five commands. `uv run pytest -q --tb=short` passes on
  CPython 3.14 and 3.11.
- **S08-A02** `speckit-ac doctor` in Habit Tracker: 0 FAIL. Every key `settings.json` had before is
  still there.
- **S08-A03** `/speckit-ac-init` passes verification with the values in S08-R09.
- **S08-A04** The live smoke test passes. No call outside the smoke flow is blocked by our guard or by
  Habit Tracker's hooks.
- **S08-A05** ADR 0003 exists, matches decisions 2–5, and is listed in the extra spec inputs of
  `.workflow/config.json`.
- **S08-A06** `sonar.yml` has the AC project exclusion. Habit Tracker's build, tests and self-tests
  pass (S08-R12).
- **S08-A07** The results file exists, and every open item is answered or marked "not observed".
- **S08-A08** The PR's Sonar and CodeQL results are recorded once you open the PR. Neither reports
  anything under the AC project or `.specify/extensions/ac/`. This check depends on your PR.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Habit Tracker's `architecture-gate.ps1` (pwsh, up to 120 s) blocks or slows a subagent's Bash call | Smoke test; record the interaction; adjust on the Habit Tracker side only with your OK |
| 2 | The `sdlc` plugin's agents or hooks interfere with the AC roles | Check what the plugin registers before the smoke test; record it |
| 3 | CodeQL default setup scans every `.cs` file, including step definitions, and can't be given path exclusions | Record what the first PR shows; out of scope to change (ADR 0001) |
| 4 | Detection proposes `HT.Ui` or misses `HT.Persistence` as a surface candidate | You choose in init (decision 2) |
