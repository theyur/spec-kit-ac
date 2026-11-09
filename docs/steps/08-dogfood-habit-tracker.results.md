# Step 8 — dogfood in Habit Tracker: results

Spec: [08-dogfood-habit-tracker.spec.md](08-dogfood-habit-tracker.spec.md) · Plan:
[08-dogfood-habit-tracker.plan.md](../../.claude/plans/08-dogfood-habit-tracker.plan.md).

Run on 2026-11-09 in Habit Tracker (`<habit-tracker>`, branch `infra/ac-workflow-setup`).
The user drove the two live sessions. I checked them from the files, `.workflow/guard.log`, and the session and
subagent transcripts (`~/.claude/projects/E--Personal-agentic-engineering-course-exam/`).

## Environment

- **Tools:** Windows 11, Claude Code 2.1.319 (desktop app), spec-kit 1.0.2, .NET SDK 10.0.403, uv 0.11.26,
  PowerShell 7.6.9.
- **Model:** every session and subagent ran on `claude-fable-5-1`.
- **speckit-ac 0.1.0.dev0:** installed as a uv tool from the checkout. The build was HEAD `9804ab8` plus the
  uncommitted step 8 edits (the five commands and `tests/test_commands.py`; plan D2). Both the tool's payload and HT's
  `.specify/extensions/ac/` matched the checkout (CRLF folded). Every CLI call ran by the tool's full path.
- **Habit Tracker:**
  - a skeleton: four empty projects, xUnit 2.9.3 on VSTest, `TreatWarningsAsErrors`;
  - its own PreToolUse hooks: `architecture-gate.ps1` on Bash and PowerShell, `block-pr-review.ps1` on Skill;
  - the `sdlc` plugin (agents and skills, no hooks);
  - five desktop-app worktrees under `.claude/worktrees/`.

## Outcome per stage

| Stage | What ran | Outcome |
|---|---|---|
| Preflight | branch, clean tree, `core.hooksPath`; HT build, tests, `selftest.ps1`, `oracle.ps1` | all pass. `oracle.ps1` only passes with `-Bash "C:\Program Files\Git\bin\bash.exe"`: in this session `git` resolves to an MSYS `ucrt64` copy, and the oracle looks for Git Bash next to it. An environment quirk, not caused by this step |
| ADR, Sonar | `docs/adr/0003-acceptance-tests.md`; `sonar.yml` exclusion | written; the `sonar.yml` diff is 2 lines |
| Install | `speckit-ac install`, `doctor` | 10 ok, 1 warn (no config yet), 0 FAIL. Every `settings.json` key and hook kept, guard last, CRLF kept; `CLAUDE.md` only gained the block (26 lines); the changed paths are exactly the expected set (47 manifest files + `settings.json`, `CLAUDE.md`, `deploy.json`, `extensions.yml`, `.registry`) |
| Init (user, ≈ 11 min incl. questions) | `/speckit-ac-init` in a main-checkout session | 17 passed, 0 failed. Surface Application + Domain + Persistence (detection's proposal, plan D3); unit tests ArchitectureTests + UnitTests; xunit2 / VSTest; `tests/HT.AcceptanceTests`; `artifacts/refs`. Spec input: see finding 1 |
| Config fix | `specInputs` = `SPEC.md` + ADR 0003 (user's choice, edited by me); `init_verify.py` re-run | 17 passed; `doctor` 13 ok, 0 FAIL |
| Smoke (user, ≈ 2.5 min) | `/speckit-ac-init smoke` + 3 manual checks | all three roles PASS (expected guard decisions, each once) and handed back. Main-agent `Read` of the probe file denied; `Explore` launch denied (its prompt named `StepDefinitions/`). Missing interpreter (`C:/nope/python.exe`): Bash, PowerShell, Glob, Grep and Read all blocked (`onFailure: block`). `settings.json` restored from the snapshot, byte-identical |
| Post checks | HT build, tests, self-tests; `doctor`; `git status` | build and tests pass (the AC project isn't in the solution); `selftest.ps1` PASSED (175 cases); `oracle.ps1` PASSED (with `-Bash`); `doctor` 13 ok, 0 FAIL; `settings.json` byte-identical to the post-install snapshot. `git status`: 66 paths, being install's set, init's set (`.workflow/config.json`, `.gitignore`, `.gitattributes`, `dotnet-tools.json`, 7 files under `tests/HT.AcceptanceTests/`), the ADR, `sonar.yml` and the untouched `GITHUB-SETUP.md`. `guard.log`, `active-run.json` and `artifacts/refs/` are git-ignored |

Acceptance checks: S08-A01 (text and test, 676 passed on 3.14 and 3.11), A02, A03, A04, A05 (after the config
fix), A06 and A07 are met.

**A08 is met** on Habit Tracker PR 16 (head `2752ce9`, 2026-11-09):
- `/process-pr-feedback` reported SonarQube Cloud green and CodeQL green.
- Checked independently: Sonar has 0 open issues on the PR, and CodeQL's C#, JavaScript/TypeScript and Actions
  analyses report 0 results.
- Caveat: the AC project has no `.cs` files yet (only the `.csproj`, `reqnroll.json`, `Directory.Build.props` and
  `.gitkeep` files). So this doesn't yet show how CodeQL treats step definitions, or that the Sonar exclusion has an
  effect. The first feature's PR will show both.

## Open items carried into step 8

| Open item | Answer | Evidence |
|---|---|---|
| Commands should wait for the hand-back (step 7) | **done; it works.** All three smoke launches were backgrounded again. This time the model passed no `run_in_background` at all (step 7: the string `"false"`). The main agent made no tool call between each launch and its hand-back: it ended the turn (`pendingBackgroundAgentCount: 1`) and went on when the hand-back arrived | smoke session transcript; `requestShape: "background"` in each `.meta.json` |
| `Agent` description reaches the subagent (step 4) | **not in the subagent's messages.** The description ("Smoke test AC guard") appears only in Claude Code's `.meta.json`. The subagent transcript starts with exactly the prompt; step 7's files show the same. The system prompt is not visible, so this is "not in its messages", not "never seen" | `subagents/agent-*.jsonl` and `.meta.json` |
| Hook timeout on a cold uv start (steps 6–7) | **not hit; cold start not reproduced.** The guard took ≈ 0.1 s per Read/Write and ≈ 0.3 s per Bash (together with `architecture-gate.ps1`'s pwsh start); the ref-mode build took 1.4 s in total. The uv cache was warm from the install | subagent transcript timestamps |

## Guard log

15 lines, all from the smoke test: translator 6, writer 6, judge 3, each the expected decision once. No denial
outside the smoke cases. Main-agent decisions are never logged; the two main-agent denials are in the transcript.

## Our guard and Habit Tracker's hooks

- `architecture-gate.ps1` checks only commands that mention `git` or `commit`.
  - The smoke flow's Bash calls (`cd … && uv run … smoke_test.py`, `ls`, the `acRefBuildCommand`) passed straight
    through.
  - In the init session, the main agent's plain `git rev-parse … && git worktree list` was allowed by both hooks.
  - It blocked nothing in either session.
- Both PreToolUse hooks run on every Bash and PowerShell call. A deny from either blocks the call. No conflict
  showed.
- `block-pr-review.ps1` matches only `pr-review`.
- The `sdlc` plugin registers no hooks, and none of its agents took part.

## Findings

1. **Init's spec-input question steers away from test-environment documents.**
   - The question says the documents "must describe the domain, never the implementation". The model therefore
     recommended `SPEC.md`, and ADR 0003 was not offered.
   - The ADR is what tells the isolated writer how to build the system and reset `HT-AC`.
   - Fixed by hand in the config (user's choice: `SPEC.md` + ADR).
   - Candidate follow-up: the init command's question could name test-environment documents (how tests build and
     run the system) as allowed spec inputs. This is a wording change within DESIGN §4.
2. **Subagents always run in the background in this Claude Code version**, whatever the model passes. With the new
   command text the main agent waits correctly, so the WORKFLOW §6 limit stays as recorded.
3. **The .NET 10 SDK creates the tool manifest at the repository root** (`dotnet-tools.json`, not
   `.config/dotnet-tools.json`).
   - `init_scaffold.py` already watches both.
   - The plan's reset list (6a.4) had `.config/`; it is corrected in the plan notes. The reset was never needed.
4. **The proposed AC project folder follows the solution name** (`tests/HabitTracker.AcceptanceTests`). The user
   changed it to `tests/HT.AcceptanceTests` in the summary; this works as designed.
5. **CodeQL default setup scans every `.cs` file** and can't exclude paths (spec risk 3). PR 16 had no results, but
   it held no step definitions either; the first feature's PR will show the effect.

## Fixes made during the run

None during the live run: every defect check passed, so the fix loop (plan 6a) was not needed. The fixes below came
from the PR review.

## Copilot review on PR 16 (head `2752ce9`)

Three findings, all in spec-kit-ac code that install copied into HT. Fixed here and deployed to HT with
`speckit-ac upgrade`: `doctor` 0 FAIL, `settings.json` unchanged.

1. **High, valid: spec inputs were not checked against implementation folders after init.**
   - Init refuses `src/` and project folders when it asks, but the config is changed by hand afterwards. The guard
     (`load_config`) and `aclib.validate_config` checked only `specs/`, `.specify/`, `.workflow/`, the AC project and
     the refs folder.
   - **Fix:** both now reject a spec input that equals, contains or lies inside `src/` or a folder holding a
     `.csproj` (outside `bin/` / `obj/`). Checked on every load. New tests: 7 in `test_guard.py`, 3 in
     `test_scripts.py`. CONFIG.md updated.
2. **High, false positive: the tool manifest at the repository root.**
   - Copilot said discovery only finds `.config/dotnet-tools.json`. That is wrong: the SDK also finds a
     `dotnet-tools.json` in the folder itself.
   - **Evidence:**
     - a fresh clone of the PR branch (no `.config/`) runs `dotnet tool restore` and `dotnet tool run ilspycmd`;
     - `dotnet tool list` in HT names `E:\…\dotnet-tools.json` as the manifest;
     - init's check [4] (`dotnet tool restore`, `export_refs.py`) passed with it.
   - No change.
3. **Medium, valid: no rollback when the AC folder existed empty.** `init_scaffold.py` accepts an existing empty AC
   folder but removed it on failure only when it had created it, so a failed package install left a partial project
   behind, which the next init then refused.
   - **Fix:** on failure the folder is emptied again (or removed, when this run created it).
   - New test: `test_scaffold_failure_leaves_the_ac_folder_as_it_was`, for both cases.

Suite after the fixes: 688 passed, 9 skipped (CPython 3.14 and 3.11).

## Copilot re-review on PR 16 (head `2423ff8`)

Copilot marked the manifest and scaffold findings resolved. It raised 6 new findings and 1 it had missed before. Five
are fixed here and one in part; one is a false positive.

1. **High, valid: the hand-back screen missed qualified attributes and plain declarations.**
   - **Fix:** the guard's `CODE` pattern now also matches qualified Reqnroll attributes (`[Reqnroll.Binding]`,
     `[global::Reqnroll.ThenAttribute(…)]`, hook attributes, `Scope`), C# member and type declarations with an access
     modifier, and expression bodies (`) =>`).
   - Prose about code still passes (WORKFLOW §6, updated).
   - New guard cases: 5 denied, 1 allowed. The agents' final-message rules still pass the screen.
2. **High, valid: `export_refs.py` skipped every folder starting with `bin` / `obj`.** A folder such as `Bindings/`
   or `objectives/` escaped the `InternalsVisibleTo` check.
   - **Fix:** it now matches the build-folder names only (`bin`, `obj`, `obj-ref`, …), as `changed_files.py` does.
   - New test.
3. **High, false positive: the xUnit v3 / MTP recipe writes no TRX.** `--report-xunit-trx` writes a Visual Studio
   TRX file.
   - **Evidence:** the opt-in end-to-end test for xunit3/MTP (real packages) passes again: `acTestCommand` writes
     `ac-results.trx`, and `summarize_trx.py` reads its passed and pending results (verification line [7]).
   - Step 5 verified all seven pairs the same way. No change.
4. **High, valid: `refsDir` could point at source or the AC project**, and `export_refs.py` deletes it before every
   export.
   - **Fix:** the config validators (aclib and guard) reject a `refsDir` that overlaps `specs/`, `.specify/`,
     `.workflow/`, `.git/`, the AC project or an implementation folder. A `.csproj` at the repository root itself is
     allowed, for single-project repositories.
   - New tests.
5. **Medium, valid: the solution and project paths were not validated as project-relative.**
   - **Fix:** `solution`, `acProject`, `acSurfaceProjects` and `unitTestProjects` now pass the same check as the
     other paths: no absolute, drive-letter or `..` paths. They are normalised on load.
   - New tests.
6. **Medium, valid: `smoke_test.py end` deleted the temporary smoke feature even when a real run's marker was
   active.**
   - **Fix:** with a real marker it now leaves both the marker and `specs/999-speckit-ac-smoke` alone.
   - Test extended.
7. **Previously missed; valid in part: the judge marker stays after `/speckit-ac-tests-analyze` stops before the
   judge.**
   - It can't launch a judge: no task message exists before step 9, which WORKFLOW §3.9 already said. But it did
     make `/speckit-ac-init smoke` refuse to start after an all-pass run.
   - **Fix:** a new `changed_files.py clear` ends a run that never started its subagent; it refuses a smoke marker.
     tests-analyze runs it at all three stops before the judge (build failure, no TRX, every test passed).
   - New tests. WORKFLOW §3.9 and CONFIG.md updated.

The spec-input finding from the first review is listed as open again, with no new comment. The fix from round 1
stands, with its tests.

## Not covered

- A Habit Tracker feature through the flow (out of scope; the first feature is course work). In particular, the
  ADR's database rules (composition and reset entry points, `HT-AC`) are untested until a feature persists data.
- A cold-uv-start hook timing.
- Sonar and CodeQL on real step definitions (none exist yet; see A08).
