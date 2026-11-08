# Step 7 live run — runbook

You drive interactive Claude Code sessions in the sample; scripts prepare each stage and check it from the files.
Headless `claude -p` is not supported (DESIGN §9), so none of this is automated.

## Before you start

- Claude Code 2.1.318 or later (desktop app, terminal or IDE), spec-kit 1.0.2, .NET SDK 10, uv, PowerShell 7.
- Two places:
  - **Terminal T** — any PowerShell 7 window. Paste once per window; the two functions work from any folder
    (they always use this checkout's scripts and Python, never the folder you are in):

    ```powershell
    $R = "<spec-kit-ac>"; $S = "<e2e-sample>"
    function check { uv run --project $R python "$R\tests\e2e\check_stage.py" --project $S @args }
    function stage { uv run --project $R python "$R\tests\e2e\stage.py" --project $S @args }
    ```

  - **Claude Code** — sessions whose working folder is `<e2e-sample>`. Trust the folder when asked.
    A "new session" below always means a fresh one in that folder: agents, hooks and skills load at session
    start.
- **Notes file:** `<e2e-notes>.md` — **outside** the sample (a file inside it would make
  the tree dirty and show up in the `written` check). For every command, note:
  - start and end time;
  - every guard denial or retry you see (the message, what the model did next);
  - anything unexpected, with the exact text.
  I read the run folders and `.workflow/guard.log` myself; the notes cover what only the screen shows.
- `.claude/settings.local.json` (written when you answer a permission prompt with "don't ask again") is
  git-ignored in the sample, so it never makes the tree dirty.
- The slash commands always stop after their step. Never let a command go on to the next one; you start each.
- Each `check_stage.py` call ends with `RESULT: PASS` or `RESULT: FAIL`. On FAIL (or anything odd), stop and
  tell me with the check's output; do not work around it.

Every `check …` and `stage …` below is typed as is in terminal T (the functions above), for example
`check init` or `stage commit init`.

## Stage 1 — make the sample (terminal T)

```powershell
uv run --project $R python "$R\tests\e2e\make_sample.py" --dest $S
```

It runs `specify init`, copies the sample, commits, installs `speckit-ac` as a uv tool from this checkout
(`uv tool install --reinstall`; undo later with `uv tool uninstall speckit-ac`), runs `speckit-ac install`, checks
the installed extension against the checkout and commits. Note how long it took. `--force` replaces a previous
sample.

## Stage 2 — session A: `/speckit-ac-init`

1. New session. Run `/speckit-ac-init`.
2. Expected detection: solution `Shop.slnx`; AC surface `src/Shop.Pricing/Shop.Pricing.csproj`; unit tests
   `tests/Shop.Pricing.Tests/Shop.Pricing.Tests.csproj`; xUnit v3 on VSTest; AC project `tests/Shop.AcceptanceTests`;
   refs `artifacts/refs`. No extra spec inputs. Confirm these; note any other question it asks.
3. It writes the config, scaffolds the AC project, runs the verification and reports. The constitution already
   has the testability section; decline the offer.
4. Terminal T: `check init`, then `stage commit init`.

## Stage 3 — session B: live smoke test

1. New session. Run `/speckit-ac-init smoke`.
2. It starts the three AC subagents with their smoke prompts. Note for each role: did the subagent hand back a
   report (a "can't report back" means the hand-back was denied)? Which actions were blocked?
3. Manual checks it walks you through:
   1. the main agent's own `Read` of the temporary file in `StepDefinitions/` must be blocked — note it (the
      guard log never records main-agent decisions);
   2. an `Explore` subagent asked to read that file must be blocked (the launch itself, or its read);
   3. missing interpreter: edit `.claude/settings.json` by hand and point the guard's command at a Python that
      does not exist (for example replace `uv run --no-project python -I` with `C:\nope\python.exe`). Start a
      **new session**, ask it to run any tool (e.g. "list the files here"): the call must be blocked. Note the
      message. Then restore the file from terminal T, byte for byte:

      ```powershell
      git -C $S checkout -- .claude/settings.json
      git -C $S status --short
      ```

      `git status` must print nothing.
4. Terminal T: `check smoke`, then `stage commit smoke`.

## Stage 4 — feature 001 (planted bug)

All Claude Code steps run in one **new session C** (the restore in stage 3 needs a fresh session).

1. Terminal T: `stage spec 001` (writes `specs/001-order-discount/spec.md` and makes it the current feature).
2. `/speckit-ac-translate` — phase 1 drafts `specs/001-order-discount/acceptance.md`.
   - **Review it.** It must have an item with a subtotal of **exactly 100.00** and a total of **90.00**: the
     planted bug is only caught there. If it has none, tell the session: "Add an item for a subtotal of exactly
     100.00." (A realistic review comment; note that you had to.)
   - Run `/speckit-ac-critic ac`. Note whether it ran on Fable or reported that Fable was unavailable. Act on
     findings you agree with; note the rest.
   - Approve: "The acceptance criteria are approved, lock them." It locks `sources` and stops.
   - Terminal T: `check ac 001`, then `stage commit translate-001-phase-1`.
3. `/speckit-ac-translate` — phase 2 starts the isolated translator.
   - Note the run id, the build result and the issues table. Decide each issue (skip / fix / stop) as you would
     for real; note the decisions.
   - Run `/speckit-ac-critic features`; note the findings.
   - Approve: "The features are approved, lock them."
   - Terminal T: `check features 001`, then `stage commit translate-001-phase-2`.
4. Terminal T: `stage implement 001-buggy` (in place of `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`;
   the implementation has the planted bug).
5. `/speckit-ac-tests-write` — the isolated writer writes the step definitions.
   - Note the run id, build status and the report (scenarios bound, interpretations, cross-feature changes).
   - Terminal T: `check written 001`, then `stage commit tests-write-001`.
6. `/speckit-ac-tests-analyze` — runs every AC test and starts the judge.
   - Expected: the 100.00 item fails and the judge says `IMPLEMENTATION_FAULT`.
   - Terminal T: `check analyze fault-001 001`, then `stage commit analyze-001-fault`.
7. Ask the session in plain words: "Fix the implementation as the judge report says." It may read and change
   `src/` (the main agent may; the AC subagents may not). Note what it changed.
   - Terminal T: `stage commit fix-001`. (If you would rather not use its fix: `git -C $S checkout -- src tests`,
     then `stage fix 001`.)
8. `/speckit-ac-tests-analyze` again. Expected: every result passed (no judge).
   - Terminal T: `check analyze pass 001`, then `stage commit analyze-001-pass`.

## Stage 5 — feature 002 (contradicts 001)

Same session C, or a new one.

1. Terminal T: `stage spec 002`.
2. `/speckit-ac-translate` (phase 1). Review `specs/002-raise-discount-threshold/acceptance.md` (no critic this
   time). Approve and lock. Terminal T: `check ac 002`, `stage commit translate-002-phase-1`.
3. `/speckit-ac-translate` (phase 2). Decide the issues, approve, lock. Terminal T: `check features 002`,
   `stage commit translate-002-phase-2`.
4. Terminal T: `stage implement 002`.
5. `/speckit-ac-tests-write`. Terminal T: `check written 002`, `stage commit tests-write-002`.
6. `/speckit-ac-tests-analyze` — **without `--current`** (with it, the judge would not see feature 001's
   failures). Expected: feature 001's items between 100.00 and 149.99 fail, every 002 result passes, and the
   judge says `SUPERSEDED` for each 001 failure.
   - Terminal T: `check analyze superseded-002 002`, then `stage commit analyze-002`.
7. Stop here: retiring or revising 001's acceptance criteria is not part of this run.

## Stage 6 — doctor

Terminal T:

```powershell
Push-Location $S; speckit-ac doctor; Pop-Location
```

Then `check init` once more. Tell me the run is done; I read the notes file, the run folders and `guard.log`,
and write `docs/steps/07-e2e-sample.results.md`.

## Redeploy a fix

When a stage fails because of a defect in spec-kit-ac, I fix it in the checkout (with a regression test). To
get the fix into the sample:

```powershell
uv tool install --reinstall --from $R speckit-ac
Push-Location $S; speckit-ac upgrade; Pop-Location
stage commit upgrade
```

Then start a **new** Claude Code session (agents, hooks and skills load at session start), re-run the failed
stage and its `check`, and run `check init` once (doctor).
