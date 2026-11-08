# Plan — step 7: end-to-end sample and live run

Spec: `docs/steps/07-e2e-sample.spec.md` (approved 2026-11-08, decisions 1–10 as drafted).

## Facts (observed, 2026-11-08)

- F1 `specify init <dir> --integration claude --script ps --non-interactive` (specify 1.0.2) takes < 1 s,
  creates `.claude/skills/speckit-*` and `.specify/` (incl. `.specify/.gitignore`, which ignores
  `feature.json`), a template `constitution.md`, `init-options.json` with `"integration": "claude"`,
  `"script": "ps"`, `"feature_numbering": "sequential"`. No `.git`, no `CLAUDE.md`.
- F2 spec-kit writes `.specify/feature.json` as `{"feature_directory":"specs/NNN-name"}` (relative,
  `common.ps1` `Save-FeatureJson`); `aclib.resolve_feature` reads `feature_directory`.
- F3 `check_acceptance.py` reads FRs as `- **FR-NNN**` lines and scenarios as numbered lines under
  `### User Story N` (spec-kit's template shape).
- F4 `guard.log` lines are `<agent_type>\t<tool>\t<decision>` (`guard.py:406`); it is git-ignored by
  init's block (`init_scaffold.gitignore_lines`), as is `.workflow/active-run.json`.
- F5 `smoke_test.py end` already compares the log per role, expects `SubagentHandback allow` for all
  three roles, and removes the marker and `specs/999-speckit-ac-smoke/`.
- F6 `ac-results.md` (summarize_trx `section`) has rows `| Feature | Scenario | Tags | Outcome |
  Duration |`, tags include `@AC-NNN`; outcomes passed / failed / pending / skipped. Judge report:
  `## Summary` table `| Feature/AC | Scope | Verdict | Confidence | reason |` (judge agent file).
- F7 `changed_files.py check` prints its result and saves nothing; the marker is deleted after it.
- F8 Config has no runner key; VSTest shows as `acTestCommand` without `--project` and with
  `--logger "trx;…"` (`init_config.build`).
- F9 `speckit-ac` takes the project root from the cwd; prerequisites: Windows, uv, pwsh, specify ≥ 1.0.2,
  `init-options.json` with ps + claude, `CLAUDE.md`, a root `.sln`/`.slnx`, a git work tree
  (`deploy.prerequisites`).
- F10 NuGet cache (`<nuget-packages>`) has xunit.v3.mtp-off 4.0.2, xunit.runner.visualstudio 4.0.1,
  Microsoft.NET.Test.Sdk 18.11.0, Reqnroll / Reqnroll.xunit.v3 3.3.4.
- F11 `uv tool dir --bin` = `~\.local\bin`, which is on PATH.
- F12 No `CLAUDE.md` or `.claude/` in `<projects>` or `E:\`; `<e2e-sample>` does not
  exist.
- F14 `specify init <dir>` refuses an existing (even empty) folder without `--force`: "Directory already
  exists" (probed 2026-11-08). The guard logs only calls with a non-empty `agent_type`
  (`guard.py:417-428`): main-agent decisions never reach `guard.log`.
- F15 Init's detection on a scratch copy of the sample (step 1 content, probed 2026-11-08): surface
  `src/Shop.Pricing/Shop.Pricing.csproj`, unit tests `tests/Shop.Pricing.Tests/…`, xunit3, vstest,
  `acProjectDir` `tests/Shop.AcceptanceTests`, no blockers (A2 confirmed). The pinned packages build and
  their tests pass (A1 confirmed).
- F13 pytest `testpaths = ["tests"]`; `test_stdlib_only.py` scans only `src/speckit_ac`.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| A1 | The three pinned package versions (F10) restore and build together on SDK 10.0.403 | 0.85 | sample doesn't build | step 1 builds it; the opt-in test (step 9) repeats it |
| A2 | init's detection picks `src/Shop.Pricing` as the surface and `tests/Shop.Pricing.Tests` as unit tests, xunit3 / vstest, no blockers | 0.85 | runbook answers differ | opt-in test runs `init_detect.py` and asserts the proposal |
| A3 | A base stub `Total` that throws `NotImplementedException` is enough for `/speckit-ac-init` (export_refs needs a public type) | 0.8 | init verify fails | opt-in test runs `init_verify.py` on the base sample |
| A4 | A model's AC draft for 001 includes an item at exactly 100.00 most of the time; the review asks for it otherwise | 0.7 | planted bug not caught | `check_stage ac 001` WARN + runbook review step |
| A5 | The judge recognises the 002 change as intentional (`SUPERSEDED`), given "(previously 100.00, feature 001)" | 0.65 | A05 fails | live; recorded either way (spec A05 note) — not blocking, the spec defines the outcome handling |
| A6 | `uv tool install --reinstall --from <repo> speckit-ac` builds from the working tree (uncommitted changes included) | 0.8 | the live run uses stale code | after `install`, `make_sample` compares every file under `src/speckit_ac/payload/` (sha256, CRLF folded, `__pycache__` skipped) with its copy under `<dir>/.specify/extensions/ac/` and fails on the first mismatch (doctor can't: it checks against the manifest the same tool wrote) |

None is blocking (A5 < 0.7 but its consequence is handled by the spec's A05 rule, not by the code).

## Steps

0. **Layout.** `tests/e2e/` with `README.md`, `RUNBOOK.md`, `make_sample.py`, `stage.py`,
   `check_stage.py`, `e2elib.py` (shared: run, git, paths, fixture table), `sample/`, `specs/`,
   `fixtures/`, `reference/`. Scripts: Python 3.11+, stdlib only, ASCII output, run as
   `uv run python tests/e2e/<script>.py …` from the checkout. (R04–R07, R12)

1. **Base sample** `tests/e2e/sample/` (R01):
   - `Shop.slnx` with both projects; `.gitignore` (`bin/`, `obj/`, `TestResults/`,
     `.claude/settings.local.json` — Claude Code writes it on "don't ask again");
     `CLAUDE.md` (short project text: what the library is, build/test commands);
     `.specify/memory/constitution.md` (filled: library-first, public API documented, the testability
     section from `/speckit-ac-init`'s offer, no `InternalsVisibleTo`).
   - `src/Shop.Pricing/Shop.Pricing.csproj` (net10.0, nullable, `GenerateDocumentationFile`),
     `DiscountCalculator.cs`: public sealed class, XML doc, `public decimal Total(decimal subtotal)`
     throwing `NotImplementedException` (A3).
   - `tests/Shop.Pricing.Tests/Shop.Pricing.Tests.csproj` with the xunit3/vstest recipe packages
     pinned (F10) and `OutputType Exe`; `DiscountCalculatorTests.cs` with one `Fact` that constructs
     the calculator. **Deviation D1** from R01: the base has no implementation (R01), so its unit test
     only constructs the calculator; the 50.00 / 200.00 tests come with each fixture (step 3).
   - Build it once in the scratchpad (A1) before writing anything else on top.

2. **Feature specs** `tests/e2e/specs/001-order-discount/spec.md`,
   `tests/e2e/specs/002-raise-discount-threshold/spec.md` in spec-kit's template shape (F3): user
   stories with numbered acceptance scenarios, `- **FR-NNN**` lines, edge cases, assumptions; no
   `[NEEDS CLARIFICATION]`. Content per R02 (**Deviation D3**: 002's rule is split into FR-001 "150.00 or
   more → 10 % off" and FR-002 "below 150.00 → unchanged", so `check_acceptance.py` coverage is per rule); 002 says "previously 100.00, feature 001" (decision 4)
   and "all other rules of feature 001 are unchanged". (R02)

3. **Implementation fixtures** `tests/e2e/fixtures/<name>/` mirroring the sample paths (R03):
   `001-buggy` (`subtotal > 100m`, rounding `Math.Round(x, 2, MidpointRounding.AwayFromZero)`,
   negative → `ArgumentOutOfRangeException`; unit tests at 50.00 and 200.00 only, per R01),
   `001-fixed` (`>=`), `002` (`>= 150m`; unit tests at 50.00 and 200.00). Each fixture holds
   only the two files it replaces (`DiscountCalculator.cs`, `DiscountCalculatorTests.cs`).

4. **Reference AC** `tests/e2e/reference/` (R08, decision 7), used only by the opt-in test:
   - `001/acceptance.md`, `002/acceptance.md` in the template format (pass `check_acceptance.py`):
     001: AC-001 (FR-001; US1-AS1) 100.00 → 90.00; AC-002 (FR-001) 200.00 → 180.00; AC-003 (FR-002;
     US1-AS2) 99.99 → 99.99; AC-004 (FR-003; US2-AS1) -0.01 → rejected; AC-005 (FR-004; US1-AS3)
     123.45 → 111.11. 002: AC-001 150.00 → 135.00; AC-002 149.99 → 149.99; AC-003 100.00 → 100.00.
   - `Features/F001/OrderDiscount.feature`, `Features/F002/DiscountThreshold.feature` (`@F00N`,
     `@AC-NNN`; pass `check_features.py`).
   - `StepDefinitions/F001/DiscountSteps.cs`, `StepDefinitions/F002/ThresholdSteps.cs` with
     `[Binding, Scope(Tag = "F00N")]`, literal expected values from the Gherkin.
   - Expected outcomes: 001-buggy → only F001 AC-001 fails; 001-fixed → all pass; 002 → F001 AC-001
     and AC-005 fail, the rest passes.

5. **`e2elib.py`**: `REPO`, `E2E` paths; `run(args, cwd, check)` (utf-8, captured, ASCII-safe
   printing); `git(project, *args)`; `dirty(project)` (`git status --porcelain`, untracked included,
   ignored excluded); `commit(project, message)` (`git add -A` + commit with a fixed identity
   `speckit-ac e2e <e2e@localhost>` and `commit.gpgsign=false` via `-c`, so the user's config is not
   needed or changed);
   `FIXTURES`, `SPECS` tables; `load_config(project)`; `python_cmd(project)` (config's `python`,
   split). (R04–R06)

6. **`make_sample.py --dest <dir> [--force] [--cli tool|checkout]`** (R04):
   1. resolve `<dir>`; refuse if it is inside this repo (would inherit `CLAUDE.md`) or is a drive
      root; if it exists and is not empty: refuse without `--force`; with `--force`, refuse unless it
      contains `.workflow/` or `.specify/` (a previous sample), then delete only `<dir>` (handle
      read-only files under `.git`); an existing **empty** `<dir>` is removed first (F14);
   2. `specify init <dir> --integration claude --script ps --non-interactive`;
   3. copy `sample/` over it (overwrites `constitution.md`);
   4. `git init -q -b main`, commit "e2e: sample";
   5. CLI: `tool` (default) → `uv tool install --reinstall --from <REPO> speckit-ac`, then the exe
      from `uv tool dir --bin` (F11); `checkout` → `uv run --project <REPO> speckit-ac` (used by the
      opt-in test; no global change);
   6. `<cli> --version`, `<cli> install` (cwd = `<dir>`); compare the payload with the installed copy
      (A6; expected set = payload files minus `.extensionignore` itself and its patterns, since spec-kit
      copies neither; first mismatch or missing file → error); commit "e2e: speckit-ac install";
   7. print the next runbook stage (RUNBOOK §2) and the CLI used.

7. **`stage.py --project <dir> <action> [arg]`** (R05):
   - common: project must contain `.specify/` and `.git`; refuse when dirty, except for `commit`;
   - `spec <001|002>`: copy `specs/NNN-name/spec.md` to `<dir>/specs/NNN-name/spec.md`, write
     `.specify/feature.json` (F2), commit "e2e: spec NNN";
   - `implement <001-buggy|001-fixed|002>`: copy the fixture's files, commit "e2e: implement <name>";
   - `fix 001` = `implement 001-fixed` with message "e2e: fix 001 (fallback)";
   - `commit <label>`: `git add -A`, commit "e2e: after <label>" (nothing to commit → says so, exit
     0). Needed because the slash commands leave changes (acceptance.md, locks, features, runs) and
     every other action refuses a dirty tree (decision 6). **Deviation D2** from R05: a fourth action,
     with a message that names the stage;
   - prints every file written; unknown action / fixture / feature → usage error, exit 2.

8. **`check_stage.py --project <dir> [--cli …] <stage> [arg]`** (R06): reads files and runs the
   sample's own scripts (`<python> .specify/extensions/ac/scripts/<x>.py`), `dotnet build`, `git`,
   and `<cli> doctor`; never a model; prints `PASS|FAIL|WARN <check>: <detail>`, exit 1 on any FAIL.
   External commands go through an injectable runner so unit tests can stub them.
   - `init`: config exists and validates (`testFramework == xunit3`, acTestCommand is VSTest per F8);
     `dotnet build <acProject> -nologo -v q` exits 0; `<cli> doctor` exits 0.
   - `smoke`: for each of `ac-feature-translator`, `ac-test-writer`, `ac-test-fail-judge`, guard.log has
     at least one line of that agent_type and a `SubagentHandback\tallow` line (F4, F5); WARN if no
     `Explore\tRead\tdeny` line (manual check 2; a denied `Explore` launch is a main-agent decision and
     leaves no line); no marker, no `specs/999-speckit-ac-smoke/`, no
     `<acProjectDir>/StepDefinitions/smoke-test.txt` (manual checks' file). Main-agent decisions are never logged
     (F14), so the main agent's blocked read and the missing-interpreter check are manual observations
     for the results file, not checks here.
   - `ac <NNN>`: `check_acceptance.py --feature NNN` exit 0; `ac_lock.py verify sources --feature NNN`
     exit 0; for 001: an item block (heading to next heading) contains `100.00` and `90.00`, else WARN.
   - `features <NNN>`: `check_features.py --feature NNN` exit 0; `ac_lock.py verify features` exit 0;
     every `.feature` under `Features/F<NNN>/` has `@F<NNN>`.
   - `written <NNN>`: the latest `run-NNN` has `writer-report.md`; at least one `.cs` exists
     under `StepDefinitions/F<NNN>/` (FAIL otherwise) and every one declares `Scope(Tag = "F<NNN>")` (regex allowing spacing / `@`); the
     files changed since `HEAD` (git, incl. untracked) are all allowed for the writer
     (`StepDefinitions/**`, `Support/**` except `.feature`, `specs/NNN-*/ac/runs/<run>/writer-report.md`),
     the same rule as `aclib.may_change` (F7: the command's own check output is not saved), plus
     `specs/NNN-*/ac/runs/<run>/input-feedback.md`, which `new_run.py write` copies in (not the writer).
     Precondition: the runbook commits before tests-write.
   - `analyze <fault-001|pass|superseded-002> <NNN>` (**Deviation D4**: R06 names only the expectation; the
     feature number says which feature's latest run to read): latest `run-NNN/analyze-K` of feature NNN;
     parse `ac-results.md` rows (F6) → per key (`F00N/AC-NNN`) worst outcome; parse the judge
     report's Summary rows → key → verdict: the key comes from the first cell(s) through tolerant
     regexes (`F\d{3,}` and `AC-\d{3,}`, so `F001 / AC-001`, `@AC-001` or trailing text work); a row
     with a verdict word but no extractable key → FAIL with the raw row; likewise a non-passed
     `ac-results.md` row without an `AC-` id. Print both tables. Then:
     - `fault-001`: ≥ 1 F001 failure; each failing F001 key's acceptance item mentions `100.00`; each
       failing key has `IMPLEMENTATION_FAULT`;
     - `pass`: total > 0 and every row `passed` (skipped counts as not passed); no judge report needed;
     - `superseded-002`: no F002 failure; ≥ 1 F001 failure; each failing F001 key has `SUPERSEDED`.
       If `ac-results.md` has the `--only-current` line (F001 not detailed), FAIL with the hint that
       tests-analyze for 002 must run without `--current`.
     Missing ac-results.md / judge report when needed → FAIL with the path.

9. **Tests.**
   - `tests/test_e2e_tools.py` (non-opt-in, R09): fabricated project trees in `tmp_path` (git init,
     a minimal config, acceptance.md, feature files, run folders, ac-results.md, judge-report.md,
     guard.log) and a stub runner. Covers: stage refusals (no `.specify`, dirty tree, unknown
     action/fixture), files written and commits made per action, `commit` with nothing to commit;
     make_sample's destination refusals (inside the repo, non-empty without `--force`, `--force` on a
     folder that is not a sample) without running specify; the payload comparison skips
     `.extensionignore` and its patterns and reports a changed or missing file; every check_stage
     stage's PASS and each FAIL path (missing handback for one role, leftover marker, leftover
     `smoke-test.txt`, missing boundary item → WARN, bad Scope, no `.cs` under
     `StepDefinitions/F<NNN>/`, writer file outside the allowlist, wrong verdict, F002 failure in
     superseded-002, no judge report, a skipped row in `pass`, a results row or judge row without a
     key); judge/results parsers on real-shaped text.
   - `tests/test_e2e_sample.py` (opt-in `SPECKIT_AC_DOTNET_E2E=1`, R08): `make_sample.py --cli
     checkout` into `tmp_path`; run init's scripts as `test_init_e2e.py` does and assert the proposal
     (A2); `init_verify.py` passes (A3); `check_stage init` PASS; `stage spec 001` → copy the
     reference acceptance/features/steps into place → `stage implement 001-buggy` → solution builds,
     unit tests pass → `dotnet build <acProject> -nologo -v q` (acTestCommand has `--no-build`; the
     build is repeated after every `stage implement`) → run `acTestCommand` + `summarize_trx.py --current F001` into
     `specs/001-*/ac/runs/run-001/analyze-1/` → expected outcomes (step 4) → fabricated judge report:
     right verdicts → `check_stage analyze fault-001 001` PASS, a wrong verdict → FAIL; then
     `001-fixed` → `analyze pass 001` PASS; then `spec 002`, reference F002, `implement 002` →
     outcomes per step 4 → fabricated SUPERSEDED → `analyze superseded-002 002` PASS.
     The tree is committed (`stage.py commit <label>`) after the init scripts, after each reference
     copy and after each AC run, since every other `stage.py` action refuses a dirty tree. After
     **every** `stage implement` (001-buggy, 001-fixed, 002) the test runs `dotnet build <solution>` and
     `unitTestCommand` for the unit test project and asserts both pass.
   - Full suite with `uv run pytest -q --tb=short`; the opt-in test once with the env var; both on 3.14
     and the 3.11 venv for the non-opt-in suite.

10. **RUNBOOK.md** (R07): prerequisites (Claude Code 2.1.318+, trust the folder, a terminal in this
    checkout); one section per stage: commands (terminal / Claude Code), decisions, the `check_stage`
    call, `stage.py commit` after it, what to note (denials and retries from `guard.log`, time per
    command, anything unexpected). Stages: 1 make; 2 session A `/speckit-ac-init` (expected answers
    from A2); 3 session B `/speckit-ac-init smoke` + the three manual checks (missing interpreter: edit
    `settings.json` by hand to a bogus interpreter, start a **new session**, try a tool, restore from a
    terminal with `git checkout -- .claude/settings.json` (byte-identical, so doctor's registration
    check holds), `git status` clean, start another **new session** before stage 4; the main-agent read block and the missing-interpreter
    block are noted by the user, since `guard.log` never shows them, F14); 4 feature 001 (spec,
    translate ×2 with `/speckit-ac-critic ac` and `features`, the boundary review, implement buggy,
    tests-write, tests-analyze → fault-001, ask the main agent to fix, re-analyze → pass); 5 feature
    002 (no critics, implement 002, tests-write 002, `/speckit-ac-tests-analyze` **without `--current`** → superseded-002);
    6 `speckit-ac doctor`; 7 how to hand the notes back: a notes file **outside** the sample,
    `<e2e-notes>.md` (inside, it would dirty the tree and show up in `written`),
    which I read. "What to note" also says that `.claude/settings.local.json` (Claude Code's "don't ask
    again" file) is git-ignored in the sample, so an unexpected dirty-tree refusal points elsewhere. Plus a section **"Redeploy a fix"** (R10): when I fix a package defect found live —
    (1) `uv tool install --reinstall --from <repo> speckit-ac`; (2) `speckit-ac upgrade` in the sample
    (re-add `--force` + redeploy, DESIGN §9); (3) `stage.py commit upgrade` (upgrade rewrites tracked
    files); (4) a **new** Claude Code session (agents, hooks and skills load at session start); (5)
    re-run the failed stage and its `check_stage` call, plus `check_stage init` (doctor) once.

11. **Docs** (R12): `tests/e2e/README.md`; tracker row 7 → `implementing`, then after the live run
    `done` + notes; README status line after the live run; WORKFLOW known limits only if the run shows
    new ones.

12. **Hand over and live run** (R10, R11): stop and give the user the runbook; after each reported
    stage, run `check_stage.py` myself and read the run folders; fix package defects found (with a
    regression test; DESIGN changes → ask); then write `docs/steps/07-e2e-sample.results.md`
    (environment, model(s), per-stage table, every open item answered, denials/retries, times, fixes,
    findings) and update the tracker.

## Gaps known up front

- The live run can't be automated (DESIGN §9); A03–A05 depend on the user's session and the model.
- `check_stage written` relies on a commit right before tests-write; if the user skips it, the check
  reports the translate outputs as writer changes (FAIL with a hint to commit first and re-run
  tests-write isn't needed: the hint says to compare by hand).

## Review dispositions

### Round 1 (`07-e2e-sample.review-1.md`, REVISE)

1. BLOCKER `main` Read deny is never logged — ACCEPTED: verified `guard.py:417-428` (F14). Step 8 `smoke`
   drops it; the main-agent block becomes a manual observation (runbook, results); the `Explore` WARN stays.
2. MAJOR notes file inside the sample — ACCEPTED: step 10 item 7 moves it to
   `<e2e-notes>.md`.
3. MINOR AC build before `acTestCommand` — ACCEPTED: step 9 builds the AC project before every run.
4. MINOR tolerant judge key parsing — ACCEPTED: step 8 `analyze`; the step 9 parser tests cover the variants
   and the no-key FAIL.
5. MINOR 002 analyze without `--current` — ACCEPTED: runbook stage 5 and a FAIL hint in step 8.
6. MINOR new sessions around the missing-interpreter check — ACCEPTED: runbook stage 3.
7. MINOR base unit test deviation — ACCEPTED: recorded as D1 (step 1); tracker notes on completion.
8. MINOR `commit` action — ACCEPTED: recorded as D2 (step 7); clean tree → message, exit 0.
9. MINOR empty destination — ACCEPTED: probed (F14: specify refuses any existing folder); step 6.1 removes an
   empty `<dir>` first.
10. MINOR `commit.gpgsign` — ACCEPTED: step 5 passes `-c commit.gpgsign=false`.

### Round 2 (`07-e2e-sample.review-2.md`, REVISE)

1. MAJOR opt-in sequence blocked by the dirty-tree refusal — ACCEPTED: step 9 commits after the init scripts,
   each reference copy and each AC run.
2. MAJOR no way to get a live fix into the sample — ACCEPTED: step 10 adds the "Redeploy a fix" runbook section
   (reinstall tool, `speckit-ac upgrade`, commit, new session, re-run + checks).
3. MINOR `input-feedback.md` missing from the `written` allowlist — ACCEPTED: step 8.
4. MINOR settings restore by hand may not be byte-identical — ACCEPTED: runbook stage 3 restores with
   `git checkout -- .claude/settings.json` and requires a clean `git status`.
5. MINOR A6 validation wrong — ACCEPTED: `make_sample` compares the payload with the installed copy (step 6.6,
   A6 row).
6. MINOR fixtures' negative unit test beyond R01 — ACCEPTED: dropped; fixture unit tests are 50.00 and 200.00
   only (step 3).
7. MINOR build + unit tests after every fixture — ACCEPTED: step 9 asserts both after every `stage implement`.

### Round 3 (`07-e2e-sample.review-3.md`, REVISE, no BLOCKER → implement)

1. MAJOR payload comparison fails on `.extensionignore` — ACCEPTED: step 6.6 excludes `.extensionignore` and its
   patterns from the expected set; a non-opt-in test covers the skip.
2. MAJOR `.claude/settings.local.json` dirties the sample — ACCEPTED: the sample's `.gitignore` (step 1); the
   runbook mentions it.
3. MINOR vacuous Scope check — ACCEPTED: `written` FAILs with no `.cs` under `StepDefinitions/F<NNN>/`; test case
   added in step 9.

Scratchpad validation during round 3 (not repository code): init_config + init_scaffold on a copy of the
sample, the planned F001 reference feature and steps, the buggy implementation → build passes, only AC-001
fails, `summarize_trx --current F001` keys it `F001/AC-001`. `ac-results.md` repeats the table header in the
regression section (the parser must allow that).

### Round 4 (`07-e2e-sample.review-4.md`, APPROVE; requested by the user)

1. MINOR leftover `smoke-test.txt` — ACCEPTED: step 8 `smoke` FAILs on it; step 9 test.
2. MINOR `pass` ignores `skipped` — ACCEPTED: every row must be `passed`; step 9 test with a skipped row.
3. MINOR results row without an `AC-` id — ACCEPTED: FAIL with the raw row (step 8); step 9 test.
4. MINOR unrecorded deviations — ACCEPTED: D3 (002 FR split, step 2) and D4 (`analyze … <NNN>`, step 8).
5. MINOR dispositions not in the steps — ACCEPTED: step 9 lists the `.extensionignore` skip and the "no `.cs`"
   FAIL; step 10 mentions `settings.local.json`.
6. MINOR `python_cmd` missing in `e2elib.py` — ACCEPTED: added with step 8.

## Implementation notes

- Steps 0–10 done (2026-11-08); step 11 partly (tracker row, `tests/e2e/README.md`); step 12 (live run, results
  file, README status line, WORKFLOW limits) waits for the user's run of `tests/e2e/RUNBOOK.md`.
- Deviations: D1 base unit test only constructs (step 1); D2 `stage.py commit` (step 7); D3 002 has FR-001 +
  FR-002 (step 2); D4 `check_stage analyze <expectation> <NNN>` (step 8). Also `check_stage --cli tool|checkout`
  (for `doctor` in the opt-in test, mirrors `make_sample --cli`).
- Tests: `tests/test_e2e_tools.py` (76), `tests/test_e2e_sample.py` (opt-in, 62 s). Full suite 667 passed,
  9 skipped on 3.14 and 3.11.15.
- Mutation spot-check (scratchpad `s7/mutate7.py`): 12 of 12 caught — smoke ignoring the hand-back or the
  isolation-file leftover, `written` allowing `.feature`, `pass` accepting `skipped`, no boundary check, fenced
  tables read as results, no `--only-current` check, strict verdict cell, stage ignoring a dirty tree, no CRLF
  folding, no `.extensionignore` skip, a destination inside the repo.

## Live run log (for the results file)

- Stage 1 (2026-11-08 17:26, run by me at the user's request): `make_sample.py --dest <e2e-sample>`
  took 4 s. **Defect found:** `e2elib.cli_command("tool")` looked `speckit-ac` up on PATH first; under
  `uv run` the checkout's `.venv\Scripts\speckit-ac.EXE` (editable dev entry point) comes first, so install
  ran from the checkout, not the uv tool. Fixed: tool mode uses `uv tool dir --bin` only; regression test
  `test_tool_cli_is_the_uv_tool_not_the_checkout_venv`. Re-run with `--force` (17:27, 4 s): CLI
  `~\.local\bin\speckit-ac.exe`; payload comparison passed; tree clean (2 commits);
  `speckit-ac doctor`: 10 ok, 1 warn (no config yet), 0 FAIL.
- Stage 2 (user): `/speckit-ac-init` done; `check init` PASS (run by me after the user's attempt failed).
  **Runbook defect:** the commands assumed terminal T's cwd is the checkout; run from the sample folder,
  `uv run python tests/e2e/...` found no file and fell back to the user's Anaconda Python. Fixed: the runbook
  defines `$R`, `$S` and two PowerShell functions `check` / `stage` (`uv run --project $R python
  "$R\tests\e2e\…" --project $S @args`) that work from any folder; verified from the sample folder.
- Stage 3 (user): `/speckit-ac-init smoke` + the manual checks; `check smoke` PASS (WARN: no `Explore Read deny`
  line, so the guard likely denied the Explore launch itself; see the user's notes). guard.log has exactly the
  expected decisions, each once (no retries): translator Read deny / Write deny / Bash deny / Read allow /
  Bash allow (build) / SubagentHandback allow; writer Read deny / Bash deny / Glob deny / Read allow / Bash
  allow / SubagentHandback allow; judge Read deny / Read allow / SubagentHandback allow. **Hand-back confirmed
  interactively for all three roles** (step 1 risk 4 was PARTIAL headless). Missing-interpreter check done by
  the user; settings restored with git (tree clean, doctor 13 ok, 0 warn, 0 FAIL).
- Stage 4 steps 1–3 (user): `check ac 001` PASS (boundary item: AC-001 is an outline whose Examples include
  100.00 -> 90.00); `check features 001` PASS. acceptance.md: 4 items (AC-001..AC-004; FR-001..FR-004 covered,
  scope note on sub-threshold rounding). Critic `ac`: pass 1 REVISE (1 MAJOR: rounding examples did not
  discriminate away-from-zero from round-up; 4 MINOR), pass 2 APPROVE; critic `features`: pass 1 APPROVE
  (1 MINOR: When step drops `DiscountCalculator.Total`). The critics run as `general-purpose` subagents
  (3 hand-backs, guard role main: 12 Read, 8 Bash, 2 Write allowed, no deny). Translator translate-001: build
  success first attempt, 4 items translated, no issues; guard: 3 Read, 2 Glob, 2 Write, 1 Bash allowed,
  SubagentHandback allowed, **no deny, no retry** (the multi-line task message passed unchanged).
  Fable availability for the critic: see the user's notes.
- Stage 4 steps 4–8 (user): `check written 001` PASS (OrderDiscountSteps.cs scoped F001; changes within the
  allowlist). analyze-1: 17 results (outlines), 16 passed, 1 failed = F001/AC-001 example 100.00 -> 90.00;
  judge `IMPLEMENTATION_FAULT`, high confidence, judge key cell `F001/AC-001 (row subtotal 100.00 / total
  90.00)` (the tolerant parser was needed). `check --analyze analyze-1 analyze fault-001 001` PASS (A04 part 1).
  Main agent's fix: `>` -> `>=` plus 6 lines of unit tests. analyze-2: 17/17 passed, `check analyze pass 001`
  PASS (A04 part 2). **Tooling gap fixed:** `check_stage analyze` read only the latest analyze, so `fault-001`
  could not be re-checked after the fix; new `--analyze analyze-K` option + 2 tests (79 pass).
- From the sample session transcripts (`~/.claude/projects/E--Personal-speckit-ac-e2e/*.jsonl`): every Agent call
  passed `run_in_background` as the **string** `"false"`, not a boolean; the user saw the critic "Backgrounded"
  and the main agent waited for its notification. The critic calls carried `model: "fable"`, `effort: "high"`
  and were accepted (Fable available). The AC agents' calls carried a `description` ("AC translator run
  translate-001", …). No guard denial in any AC run, so the main agent never checked changes before a
  subagent finished. Ask the user whether the AC subagents were also shown as backgrounded.
- User (2026-11-08): **all** Agent calls were shown as backgrounded (translator, writer, judge, critic), despite
  `run_in_background: "false"`. The main agent waited for each completion notification before the next
  script, so nothing broke (no denials). Finding for the results: the commands rely on the main agent waiting;
  a command that went on early would run `changed_files.py check` mid-run (marker deleted → the subagent's
  next call denied). Candidate follow-up: command text says "wait for the subagent's result (it may run in
  the background) before step 5".
