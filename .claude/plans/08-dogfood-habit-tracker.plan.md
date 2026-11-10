# Plan — Step 8: Dogfood in Habit Tracker

Spec: `docs/steps/08-dogfood-habit-tracker.spec.md` (approved 2026-11-09, decisions 1–9 as drafted).
Habit Tracker = `<habit-tracker>` (HT below). `$S8` = the session scratchpad
folder `s8/` (logs, snapshots; never in either repository).

## Facts (inspected 2026-11-09)

- **F1** `HT` is on branch `infra/ac-workflow-setup`, which equals `master` and has no own commits. `git status`
  shows only `?? GITHUB-SETUP.md`. Five git worktrees are under `.claude/worktrees/` (git-ignored); none is on
  `infra/ac-workflow-setup`.
- **F2** HT `.claude/settings.json` (CRLF in the working tree, `core.autocrlf`; content equals
  `json.dumps(indent=2)`, so spec-kit's rewrite (step 6 note) changes no content). It contains:
  - `permissions.deny`, `skillOverrides`, `extraKnownMarketplaces` (`sdlc`, a local directory) and `enabledPlugins`;
  - PreToolUse hooks: `architecture-gate.ps1` on Bash and PowerShell (timeout 120), `block-pr-review.ps1` on Skill;
  - a UserPromptExpansion hook (`pr-review`).
- **F3** The `sdlc` plugin (`<course-repo>\sdlc\plugin`) has `agents/` (11, among them
  `critic`, `explorer`, `test-author`) and `skills/`, and **no hooks**. To the guard its agents are non-AC agent
  types, so the main-agent rules apply.
- **F4** HT surface projects:
  - `HT.Domain` and `HT.Application` are empty; `HT.Persistence` holds one public `PersistenceAssemblyMarker`.
  - No packages, no `InternalsVisibleTo`.
  - `HT.Persistence → HT.Application → HT.Domain`, and `export_refs.py` `with_dependencies` follows
    `ProjectReference`s.
- **F5** HT test projects:
  - `HT.UnitTests` (xunit 2.9.3, VSTest, no tests, no `IsTestProject`);
  - `HT.ArchitectureTests` (xunit 2.9.3, ArchUnitNET, `IsTestProject`).
  - The root `Directory.Build.props` sets `net10.0` and `TreatWarningsAsErrors`. There is no
    `Directory.Packages.props` and no `global.json` (not seen at the root).
- **F6** HT `CLAUDE.md`, `.gitignore` are CRLF with a final line break; `.gitattributes` has one rule (`.githooks/*`).
- **F7** HT CI:
  - `sonar.yml` runs on ubuntu: `dotnet build HabitTracker.slnx`, then `dotnet test` under `dotnet-coverage`, with
    `/d:sonar.exclusions=".specify/**"`.
  - CodeQL is default setup (HT ADR 0001), with no build.
  - init never adds the AC project to the solution (`init_scaffold.py` docstring).
- **F8** HT self-tests: `pwsh tools/guard-oracle/oracle.ps1` and `pwsh -NoProfile -File tools/pr-gates/selftest.ps1`
  (HT `CLAUDE.md`).
- **F9** Commands that start a subagent, with the step after the `Agent` call:
  - `translate`, `tests-write`, `tests-analyze`: sub-step 4 is the `Agent` call, then 5 `changed_files.py check`;
  - `init` smoke: sub-step 2, then 3 `smoke_test.py end`;
  - `critic`: step 1 launches, then step 2 reads the report.
  - `test_commands.py::test_subagent_start_sequence` asserts the exact
    `` `subagent_type: <role>`, `run_in_background: false` `` text, and `test_init_rules` asserts the smoke wording.
- **F10** `init_detect.py` refuses to run unless it sits under `<project>/.specify/extensions/ac/scripts/`, so
  detection can't be probed before the install.
- **F11** The smoke test's translator and writer each run the `acRefBuildCommand` through Bash, expected `allow`
  (`smoke_test.py` cases). HT's `architecture-gate.ps1` runs on those same calls.
- **F12** The writer reports missing packages under `## Missing packages` instead of working around them
  (`ac-test-writer.md`). So a package that a future HT feature adds to `HT.Persistence` reaches the AC project
  through that report. The main agent may edit the AC `.csproj`; the guard isolates only `StepDefinitions/` and
  `Support/`.
- **F13** SQL Server `.\COLL1` (17.0 Developer) is reachable with integrated security. `HT-AC` is empty, and
  `COLL1\theyur` is `db_owner`. Probed with `sqlcmd -S .\COLL1 -E -C`.
- **F14** The uv tool `speckit-ac 0.1.0.dev0` is installed from the step 7 checkout; the reinstall command is the
  one `make_sample.py` uses (`uv tool install --reinstall --from <repo> speckit-ac`).
- **F15** Claude Code keeps each subagent's transcript in `<session>/subagents/agent-<id>.jsonl`, next to an
  `agent-<id>.meta.json`. The meta file holds `description`, `requestShape` (`"background"` in step 7) and the
  model. In step 7 (sample session `178bbc0a…`), the writer's transcript starts with exactly the prompt, with no
  description in it.
- **F16** `architecture-gate.ps1` exits 0 for any command that doesn't mention `git` or `commit`
  (`$command -replace '[''"\\`]','' -notmatch '(?i)git|commit'`). It costs one `pwsh -NoProfile` start per
  Bash/PowerShell call. This confirms A1.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| A1 | `architecture-gate.ps1` allows non-git Bash commands (it gates commit commands) | 0.95 (F16) | The smoke test's build call is blocked for the translator/writer; AC flow unusable in HT | Read (F16); the smoke test (step 9) |
| A2 | Detection lists `HT.Application`, `HT.Persistence` (and maybe `HT.Domain`, `HT.Ui`) as surface candidates and both test projects as unit tests | 0.7 | The user corrects it in init; recorded as a finding | init output (step 8) |
| A3 | An empty `HT.Application` / `HT.Persistence` still exports reference assemblies and the AC project builds in ref mode | 0.75 | init verify fails: a package defect to fix here (S08-R03) | `init_verify.py` (step 8) |
| A4 | `sdlc` plugin agents and skills do not interfere with the AC roles or the smoke test | 0.8 | Unexpected guard decisions | Smoke guard log (step 9) |
| A5 | The user runs init and smoke in a session on the **main checkout** (not a desktop-app worktree), where the uncommitted install lives | 0.9 once the runbook says so | In a worktree the scripts are missing and init writes into the wrong tree | Runbook states it (steps 8–9); I check the transcript's `cwd` is `<habit-tracker>` and `gitBranch` is `infra/ac-workflow-setup` |
| A6 | The ADR as an extra spec input passes init's refusal rules (`docs/adr/` is no implementation folder) | 0.85 | init refuses it; then decide with the user | init (step 8) |

No assumption is blocking (none below 0.7 with a high consequence). A1 is checked before the user starts.

## Steps

0. **Baseline (spec-kit-ac).**
   - `git status`: only the spec and the tracker changed.
   - `uv run pytest -q --tb=short`, logged to `$S8`.
   - Covers: none (guard rail).
1. **Command text: wait for the hand-back** (S08-R01, decision 8).
   - In each of the five commands, right after the `Agent` launch sub-step, add one sentence, worded for that
     command's next step: "Wait for the subagent's hand-back before anything else. If the tool says it runs in the
     background, make no other tool call until its result arrives; only then run <next step>."
     - `<next step>` is `changed_files.py check` for translate, tests-write and tests-analyze;
     - `smoke_test.py end` for init smoke;
     - "step 2" (read the report) for the critic, where the sentence says "the critic's result".
   - The first two sentences are the same in all five commands: "Wait for the subagent's hand-back (its result)
     before anything else." and "If the tool says it runs in the background, make no other tool call until its
     result arrives". New test `test_waits_for_the_hand_back(name)`, parametrized over `NAMES`, asserts both in the
     flattened text, after the `run_in_background: false` occurrence(s), and checks that the next step's name
     follows them.
   - Existing assertions stay (F9).
   - Covers: S08-R01, S08-A01.
2. **Suite and reinstall** (S08-R02).
   - `uv run pytest -q --tb=short` on CPython 3.14 and 3.11, with the same scratchpad venv method as before.
   - Then `uv tool install --reinstall --from <spec-kit-ac> speckit-ac`.
   - **Full-path rule:** every `speckit-ac` call in HT (`--version`, `install`, `doctor`, `upgrade`) runs as
     `<uv tool dir --bin>\speckit-ac.exe` by its full path, from HT, never through `uv run` or PATH. That way the
     checkout's `.venv` can't be picked up (step 7 fix 1).
   - Record in `$S8/tool-build.txt`: the checkout's `git rev-parse HEAD` and `git status --porcelain` at reinstall
     time (the step 1 edits are uncommitted, so the tool is HEAD plus that diff). Also record a hash of the
     installed payload against the checkout's, using `payload_mismatch` from `tests/e2e/make_sample.py`, which
     compares with CRLF folded.
   - Covers: S08-R02.
3. **HT preflight** (S08-R06, decision 1). In HT:
   - check the branch name, that `git status --porcelain` is exactly `?? GITHUB-SETUP.md`, and
     `git config core.hooksPath` = `.githooks`;
   - snapshot `.claude/settings.json` (parsed JSON) and the `git ls-files` list to `$S8`;
   - baseline `dotnet build HabitTracker.slnx`, `dotnet test HabitTracker.slnx`, `oracle.ps1`, `selftest.ps1`, each
     logged to `$S8` and reported as PASS/FAIL.
   - A failing baseline: stop and report; nothing is changed in HT.
   - Covers: S08-R06.
4. **ADR 0003** (S08-R08, decisions 2–5). Write `HT/docs/adr/0003-acceptance-tests.md` in ADR 0001's format:
   - **Status:** Accepted, 2026-11-09.
   - **Context:** spec-kit-ac; the isolated AC flow; ARCHITECTURE §9.
   - **Decision:**
     - surface = `HT.Application` use cases + `HT.Persistence`'s public composition and reset entry points, with
       `HT.Domain` as dependency; `HT.Ui` out;
     - the database is `HT-AC` on `.\COLL1`, never `HT`, with the schema dropped and rebuilt by EF Core migrations
       at the start of every AC run;
     - the AC tests run sequentially;
     - `HT_AC_CONNECTION` overrides the default connection string, with integrated security and no secret;
     - step definitions arrange and assert only through use cases and those entry points, never the `DbContext`;
     - local only, not in CI.
   - **Consequences:**
     - the first persistence feature must add the two public entry points (composition with a connection string;
       reset);
     - packages that feature adds to the surface are added to the AC project by the main agent when the test writer
       asks for them;
     - this settles the AC test database only, not the integration tests' (ARCHITECTURE §9 stays open for those);
     - one line saying Sonar excludes the AC project, and why. Kept although it's outside decisions 2–5: the
       exclusion is a consequence of the isolation this ADR records.
   - The ADR describes the environment and contracts, never code. It names no class or method beyond "a public
     composition entry point" and "a public reset entry point".
   - Covers: S08-R08, S08-A05 (part).
5. **`architecture-gate.ps1` pre-check: done during planning** (F16, A1). Its code allows any command without
   `git` or `commit` in it, and the smoke flow's Bash commands contain neither. Nothing to run; the step number stays
   so the references hold. Covers: S08-R10 (pre-check).
6. **Install** (S08-R07). In HT, run `speckit-ac install`, then `speckit-ac doctor`, both by full path (step 2
   rule); output to `$S8`. Afterwards, snapshot `.claude/settings.json` (raw bytes and parsed JSON) to
   `$S8/settings-post-install.*`.
   - **Checks:**
     - `doctor` 0 FAIL;
     - every key and every hook entry from the step 3 snapshot is still in `settings.json`, with our guard
       registration last;
     - `CLAUDE.md` has the marked block and its other lines are unchanged (`git diff` shows only the block);
     - `git status --porcelain -uall` lists exactly these paths:
       - **modified:** `.claude/settings.json`, `CLAUDE.md`;
       - **new, the files in `.workflow/deploy.json`'s list:** the agents, skills and extension files (kinds
         `agent`, `skill`, `extension`, `deploy.py:498-505`);
       - **new, not in the manifest:** `.workflow/deploy.json` itself, `.specify/extensions.yml`,
         `.specify/extensions/.registry`;
       - **from step 4 (not install):** `docs/adr/0003-acceptance-tests.md`;
       - **unchanged:** `?? GITHUB-SETUP.md`.

       I compute the set from the manifest by script and compare. Any extra or missing path is a finding, and the
       check is not adjusted at run time.
   - A difference is a finding: package defect → fix it through the fix loop (6a); otherwise record it.
   - Covers: S08-R07, S08-A02.

   6a. **Fix loop**, applies to any package defect found in steps 6–10 (S08-R03):
       1. Fix it in spec-kit-ac, with a regression test; record a deviation if it changes the plan.
       2. Run `uv run pytest`.
       3. `uv tool install --reinstall` (step 2), recording the build state again.
       4. In HT, by full path, depending on where the defect is:
          - **before init ran:** `speckit-ac uninstall` then `install`;
          - **after init, in code that init's verify mode or the smoke test re-runs** (`init_verify.py`,
            `export_refs.py`, the guard, `smoke_test.py`, agents, commands): `speckit-ac upgrade`. The user then runs
            `/speckit-ac-init`, which is in verify mode because the config exists, or the smoke test;
          - **after init, in code that only setup mode runs** (`init_detect.py`, `init_config.py`,
            `init_scaffold.py`, the AC project templates): `speckit-ac upgrade`, then reset init's output so that
            `/speckit-ac-init` starts in setup mode again.

            Delete:
            - `.workflow/config.json` and `.workflow/guard.log`;
            - `tests/HT.AcceptanceTests/`;
            - `.config/` and `artifacts/`, which didn't exist before init (checked 2026-11-09).

            Then restore `.gitignore` and `.gitattributes` with `git checkout --`: they are committed, and install
            doesn't touch them. Check that `git status` again shows step 6's set, plus
            `.github/workflows/sonar.yml` (step 7), and nothing else. Deleting the config alone isn't
            enough, because `init_detect` blocks on a non-empty `acProjectDir`.
       5. Run `speckit-ac doctor`: 0 FAIL.
       6. Re-take the post-install `settings.json` snapshot.
       7. The user re-runs the affected live stage (init or smoke) in a new main-checkout session.

       The results file lists every loop pass, with the tool build state each live stage ran on.
7. **Sonar** (S08-R11, decision 6).
   - In `HT/.github/workflows/sonar.yml`, change `/d:sonar.exclusions=".specify/**"` to
     `".specify/**,tests/HT.AcceptanceTests/**"`.
   - Add one comment line beside the existing `.specify/` comment: the AC project is written by isolated
     subagents and the main agent may not edit it, so Sonar issues there could not be fixed in the PR flow; CI
     doesn't build it (outside the solution).
   - Nothing else in the file changes (`git diff` = 2 lines).
   - Covers: S08-R11, S08-A06 (part).
8. **User runs `/speckit-ac-init`** (S08-R09, decision 7). Give the user a short runbook in chat:
   - open a **new** Claude Code session on the **main checkout** `<habit-tracker>`
     (in the desktop app: no worktree, i.e. don't let it create one), on branch `infra/ac-workflow-setup`, and run
     `/speckit-ac-init`;
   - expected answers:
     - surface `HT.Application` + `HT.Persistence` (not `HT.Domain`, which comes as a dependency; not `HT.Ui`);
     - unit tests as proposed;
     - extra spec input `docs/adr/0003-acceptance-tests.md`;
     - other values as detected;
   - confirm the summary; at the end, decline the constitution change for now (`/speckit-constitution` is the
     user's own, later);
   - tell me when it's done.

   **Then I check:**
   - the session transcript's `cwd` is `<habit-tracker>` and its `gitBranch` is
     `infra/ac-workflow-setup` (A5). Otherwise the run doesn't count: clean up what it wrote and repeat;
   - `.workflow/config.json` values against S08-R09;
   - `init_verify.py` passes when I run it again through the installed script. It is self-cleaning, not read-only:
     it builds, and it writes and removes a temporary `specs/999-speckit-ac-check/` with matching `F999` folders and
     `.workflow/init-check/`. Any such leftover after an interrupted run is the script's;
   - the `.gitignore` / `.gitattributes` blocks are there;
   - `dotnet build tests/HT.AcceptanceTests` succeeds under `TreatWarningsAsErrors`;
   - the transcript (`~/.claude/projects/E--Personal-agentic-engineering-course-exam/`) shows the detection output,
     for A2.

   Covers: S08-R09, S08-A03, S08-A05.
9. **User runs the smoke test** (S08-R10). Runbook:
   - open a new session on the main checkout (as in step 8) and run `/speckit-ac-init smoke`, including the three
     manual checks (as in step 7);
   - after manual check 3 (pointing the hook at a missing interpreter), restore `.claude/settings.json`. Use
     `Copy-Item` from my post-install snapshot, with the exact command given in the runbook, not a hand edit and not
     `git checkout`, because the installed file is uncommitted;
   - tell me when it's done.

   **Then I check:**
   - the transcript's `cwd` and `gitBranch` (A5);
   - the `smoke_test.py end` lines in the transcript, and `.workflow/guard.log`: each role's expected decisions;
   - that no call outside the expected denials was blocked, by our guard or by `architecture-gate.ps1` (transcript
     hook results);
   - from the transcript timestamps: the first guard call's hook latency (cold uv start);
   - Agent `description`, with the evidence source named (F15): each smoke subagent's `subagents/agent-<id>.jsonl`
     and `.meta.json`. The description reaches the subagent's conversation if its transcript contains the
     description text anywhere; it is only harness metadata if it appears in the `.meta.json` alone. The system
     prompt isn't in the transcript, so the result is stated as "not in the subagent's messages", not "never seen";
   - whether the subagents ran in the background (`requestShape` in each `.meta.json`), and whether the main agent
     now waited without other tool calls between the launch and the hand-back (S08-R01 effect).

   Covers: S08-R10, S08-A04.
10. **HT checks after the change** (S08-R12).
    - Re-run `dotnet build HabitTracker.slnx`, `dotnet test HabitTracker.slnx`, `oracle.ps1`, `selftest.ps1`.
    - Re-run `speckit-ac doctor` (full path): 0 FAIL. Compare `.claude/settings.json` byte for byte with
      `$S8/settings-post-install.*`. Any difference (quoting, `onFailure`, line ending) is restored from the snapshot
      and recorded.
    - `git status --porcelain`: every path is one of:
      - install's set (step 6);
      - init's set: `.workflow/config.json`, `.gitignore`, `.gitattributes`, `tests/HT.AcceptanceTests/**`,
        `.config/dotnet-tools.json` (ilspycmd);
      - the ADR;
      - `sonar.yml`;
      - `GITHUB-SETUP.md`.
    - `git check-ignore` confirms that `guard.log`, `active-run.json` and the refs folder are ignored.
    - Covers: S08-R12, S08-A06.
11. **Records** (S08-R04, S08-R05).
    - Write `docs/steps/08-dogfood-habit-tracker.results.md`:
      - the environment;
      - a stage table;
      - the open items (description, cold-start latency, background subagents);
      - the guard log summary;
      - how our guard and HT's hooks interact, and what the plugin registers;
      - fixes, findings, not covered;
      - A08 pending until the user's PR.
    - Update the tracker (row 8, notes), WORKFLOW §6 (any new limit) and the README status line.
    - Final `uv run pytest` on 3.14 and 3.11.
    - Covers: S08-R04, S08-R05, S08-A07.
12. **Stop.**
    - Report, and wait for the user's go-ahead to commit spec-kit-ac and to commit and open the PR in HT (decision 9).
    - On the PR: the user drives `/process-pr-feedback`; I record Sonar/CodeQL outcomes for A08 when the user tells
      me they're in.

## Deviations

- **D1** (S08-R01): the spec's third bullet, "never run `changed_files.py check` before then", applies literally to
  translate, tests-write and tests-analyze. Init smoke and the critic never run `changed_files.py check`, so their
  sentence names their own next step instead: `smoke_test.py end` for init smoke, reading the report (step 2) for the
  critic. The test checks the two shared sentences in all five commands, and the next-step name in each.
- **D2** (S08-R02): "at the current `HEAD`" is literally HEAD plus the uncommitted step 1 edits (and any fix-loop
  edits), because commits wait for the user (decision 9). `$S8/tool-build.txt` records HEAD, the dirty file list and
  the payload comparison for every reinstall, and the results file cites it per live stage.
- **D3** (S08-R09, decision 2): the AC surface is `HT.Application` + `HT.Domain` + `HT.Persistence`. This is
  detection's recommendation, accepted by the user in init on 2026-11-09. It is equivalent for the reference
  assemblies and the `InternalsVisibleTo` check, because `export_refs.py` follows `ProjectReference`s and checks
  every dependency. The scaffold also takes Domain's packages into account (`init_scaffold.py:91,157`). ADR 0003's
  surface list now names `HT.Domain` too.

## Review dispositions

### Round 1 (REVISE; 3 MAJOR, 3 MINOR)

1. MAJOR, session location: **ACCEPTED.**
   - A5 now names the main checkout.
   - The runbooks in steps 8–9 say "main checkout, no worktree, branch `infra/ac-workflow-setup`".
   - Steps 8–9 check the transcript's `cwd` and `gitBranch`; a wrong location doesn't count.
2. MAJOR, no path to get a fix into HT: **ACCEPTED.** New step 6a, the fix loop: test → reinstall → `uninstall` /
   `install` before init, `upgrade` after → `doctor` → the user re-runs the stage. The tool build state is recorded
   per live stage.
3. MAJOR, the hand restore after manual check 3: **ACCEPTED.**
   - Step 6 snapshots `settings.json` after install.
   - Step 9 restores it by copying the snapshot back, not by hand.
   - Step 10 re-runs `doctor` and compares byte for byte.
4. MINOR, wording deviation: **ACCEPTED.** Recorded as D1.
5. MINOR, full-path rule and build state: **ACCEPTED.**
   - The step 2 full-path rule covers every CLI call in HT; step 6 refers to it.
   - `$S8/tool-build.txt` records HEAD, the dirty files and the payload comparison.
6. MINOR, the Agent description's evidence source: **ACCEPTED.**
   - The evidence is the subagent's own transcript plus `.meta.json` (F15, probed in step 7's files).
   - The result is worded as "not in the subagent's messages", because the system prompt isn't visible.

### Round 2 (REVISE; 1 MAJOR, 3 MINOR; every round 1 finding confirmed resolved)

1. MAJOR, no way back into setup mode after a half-finished init: **ACCEPTED.** Step 6a.4 now has three branches:
   before init; after init with a fix in code that verify or smoke re-runs (`upgrade`, then init verify or smoke);
   after init with a fix in setup-only code (`upgrade`, then reset init's output with a fixed list, then setup mode).
2. MINOR, the test checks two of the three sentences: **ACCEPTED.** "Wait for the subagent's hand-back (its
   result) before anything else." is now a shared sentence that the test asserts too.
3. MINOR, HEAD plus diff not filed as a deviation: **ACCEPTED.** Filed as D2.
4. MINOR, step 6's expected path set misdescribed: **ACCEPTED.** Step 6 lists the exact set (modified, manifest
   files, non-manifest files, `GITHUB-SETUP.md`), and a script computes it from the manifest. Also fixed:
   `payload_mismatch` is in `make_sample.py`, not `e2elib`.

### Round 3 (REVISE; 1 MAJOR, 3 MINOR, no BLOCKER; every earlier finding confirmed resolved)

1. MAJOR, step 6's exact set misses the ADR from step 4: **ACCEPTED.** Step 6's set now includes
   `docs/adr/0003-acceptance-tests.md`, and the 6a.4 reset check includes `sonar.yml`. The order stays as it is (ADR
   before install), because the spec needs the ADR before init.
2. MINOR, step 5 is redundant: **ACCEPTED.** Step 5 now records that the pre-check was done in planning (F16), with
   nothing to run.
3. MINOR, the ADR's Consequences go beyond R08: **ACCEPTED in part.**
   - The packages sentence is now tool-neutral.
   - The Sonar line stays as one sentence: it follows from the isolation the ADR records, and HT's rules want
     material CI changes explained in an ADR.
4. MINOR, the `init_verify.py` label: **ACCEPTED.** Step 8 now calls it self-cleaning and lists what it writes.

After round 3 with no BLOCKER, implementation starts (spec-implement rule 7).

## Implementation notes

### Run log (2026-11-09, after the restart)

- **Suite and tool:**
  - `oracle.ps1 -Bash "C:\Program Files\Git\bin\bash.exe"` PASSED;
  - suite 676 passed, 9 skipped on 3.14 and 3.11;
  - tool reinstalled (`tool-build.txt`: HEAD `88bad5b` + the step 1 edits; payload match).
- **HT files:** ADR 0003 and `sonar.yml` (2 lines) written.
- **Install:** `doctor` 10 ok, 1 warn, 0 FAIL; settings keys and hooks kept, guard last; exact path set matched.
- **Init (user):** 17/17. Surface Application + Domain + Persistence (D3).
  - Init's spec-input recommendation was `SPEC.md`, not the ADR (results finding 1).
  - The user chose `SPEC.md` + ADR; I edited `specInputs`. My re-run of `init_verify.py` passed 17/17, and
    `doctor` reported 13 ok.
- **Smoke (user):** PASS for all three roles, plus the 3 manual checks; restored from the snapshot, byte-identical.
- **Post checks:** all pass (results file).
- **Correction to 6a.4:** the .NET 10 SDK put the tool manifest at `dotnet-tools.json` in the repository root, not in
  `.config/`. The reset list would need `dotnet-tools.json` instead of `.config/`. The fix loop was never needed.

### State at pause (2026-11-09, the user restarted the session)

**Done:**

- Plan reviewed in rounds 1–3. Round 3 ended REVISE with no BLOCKER, and every finding is dispositioned, so
  implementation started.
- **Step 0:** baseline `uv run pytest` passed (671 passed, 9 skipped; slow, 35 min, because critics ran alongside).
- **Step 1 (S08-R01), implemented:**
  - all five commands (`translate`, `tests-write`, `tests-analyze`, `critic`, `init` smoke) have the wait text;
  - new test `test_waits_for_the_hand_back` in `tests/test_commands.py`;
  - `tests/test_commands.py` passes (46 passed). The full suite has **not** been re-run after the step 1 edits.
- **Step 3 (HT preflight), partly done:**
  - branch `infra/ac-workflow-setup`; `git status` = `?? GITHUB-SETUP.md`; `core.hooksPath` = `.githooks`;
  - `settings-pre-install.json` and `ht-ls-files-pre.txt` (251 files) are in the session scratchpad `s8/`;
  - `dotnet build` PASS; `dotnet test` PASS (ArchitectureTests 1 passed; UnitTests has no tests);
  - `selftest.ps1` PASSED (175 cases).
  - **`oracle.ps1` failed before any change.** It couldn't start `C:\Program Files\Git\ucrt64\bin\bash.exe`
    (it locates Git Bash from `git` on PATH, which in this session resolves to the ucrt64 path). A re-run with
    `-Bash "C:\Program Files\Git\bin\bash.exe"` was stopped for the restart.
  - It left an untracked, git-ignored folder `.claude/worktrees/guard-oracle-sandbox`, which is not a registered
    worktree. Left in place; the oracle reuses or removes it.

**Next:**

1. Re-run `oracle.ps1` with `-Bash "C:\Program Files\Git\bin\bash.exe"` (in the background; it's slow). This
   settles whether the baseline passes. It's an environment issue of this session, not a change of ours.
2. Step 2: the full suite on 3.14 and 3.11 (run in the background), then reinstall the tool and record
   `tool-build.txt`.
3. Steps 4 (ADR), 6 (install), 7 (Sonar), then the runbook for the user (step 8).

The scratchpad from before the restart may be gone. If so, re-take the pre-install snapshots in step 3: nothing in
HT changed, so they are reproducible.
