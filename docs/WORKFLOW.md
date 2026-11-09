# The AC workflow

> Describes the **target behaviour** of the `ac` extension. It is implemented across tracker steps
> 2–6 ([docs/steps/TRACKER.md](steps/TRACKER.md)); until then parts of it exist only on paper.
> Design decisions: [DESIGN.md](DESIGN.md). Origin of the method:
> [reference/WORKFLOW-SETUP-CT.md](reference/WORKFLOW-SETUP-CT.md) §0–2, §8.

## 0. What is tested

The question behind the workflow: **can acceptance tests be written from the spec alone, without
the test writer ever seeing the implementation?**

- Acceptance criteria (AC) are written for humans, per feature, in a Gherkin-like
  `specs/NNN-x/acceptance.md`, reviewed by a human, and then **locked** together with the golden
  sample files they use. Every value in them is a concrete literal.
- An isolated subagent (`ac-feature-translator`) turns each item into valid Gherkin in Reqnroll
  `.feature` files. `acceptance.md` is not guaranteed to be valid Gherkin, complete or consistent, so
  the translator never guesses: it reports every item it can't translate faithfully, with a suggested
  fix for `acceptance.md`. This happens **before implementation**, so AC problems surface before any
  code exists.
- The implementation is written normally (`/speckit-implement`), with its own unit tests.
- Another isolated subagent (`ac-test-writer`) binds the `.feature` files to step definitions. It sees
  **only** the spec inputs, the AC, the golden samples and the **public API** taken from reference
  assemblies. It never sees source code or unit tests, and it never runs tests.
- The main agent runs the AC tests. If tests fail, a third isolated subagent (`ac-test-fail-judge`),
  also blind to the implementation, classifies each failure.
- AC tests target the core library API (the "AC surface", chosen at init), not hosts such as a CLI,
  web API or UI. Hosts are thin wrappers and stay out of scope.

Isolation is enforced **technically** — a fail-closed `PreToolUse` guard, subagent tool lists, fixed
prompt templates, deterministic scripts as the only channel, content-hash change checks, subagents
that don't load `CLAUDE.md` — not only by instructions.

## 1. The flow

The user drives the flow. **After every step the agent reports and stops.** It never starts the next
step on its own.

### 1.1 Setup (once per project): `/speckit-ac-init`

The mode depends on the project's state:

- **Setup** (no `.workflow/config.json`):
  - `init_detect.py` reads the environment, the solution and every C# project in it (msbuild
    evaluation, no restore), the test runner (`global.json`) and central package management.
  - The command asks only what detection could not settle, and always asks for extra spec inputs
    (implementation folders are refused).
  - It shows one summary and waits for an explicit confirmation.
  - The scripts then write the config (`init_config.py`) and create the AC project (`init_scaffold.py`).
  - `init_verify.py` runs the checks of [CT doc](reference/WORKFLOW-SETUP-CT.md) §6 items 1 and 3–7
    with temporary files only (`specs/999-speckit-ac-check/`, the `F999` folders, `.workflow/init-check/`),
    and checks at the end that nothing is left over.
- **Verify** (the config exists): `init_verify.py` only. The configuration changes only by hand.
- **Smoke** (`/speckit-ac-init smoke`, in a **new session** after setup, and again in every new
  checkout or worktree):
  - `smoke_test.py start <role>` writes a temporary feature and a marker whose `taskMessage` is a fixed
    smoke prompt, so the guard lets the main agent start each AC subagent with that prompt.
  - `smoke_test.py end <role>` compares the new `guard.log` lines with the expected allow and deny
    decisions, then removes everything.
  - Three manual checks follow: the main agent's read of a step-definition file, an `Explore`
    subagent's read of it, and a hook pointed at a missing interpreter.

Supported test frameworks × runners (each verified by a real run): xUnit v2 on VSTest; xUnit v3, NUnit
and MSTest on VSTest and on Microsoft.Testing.Platform. xUnit v2 has no Microsoft.Testing.Platform
runner, so init refuses that pair. The commands per pair are in [CONFIG.md](CONFIG.md).

Init also writes managed blocks into `.gitignore` and `.gitattributes`. The `.gitattributes` block
pins LF line endings for every text file a lock hashes (`spec.md`, `acceptance.md`, `.feature`) and
marks the samples `binary`, so locks verify in every checkout.

```
/speckit-specify → /speckit-clarify → (/speckit-ac-critic spec)
→ /speckit-ac-translate   phase 1: draft acceptance.md (+ coverage table) → (/speckit-ac-critic ac) → user review → lock sources
→ /speckit-ac-translate   phase 2: isolated translator → skip/fix/stop → (/speckit-ac-critic features) → approve → lock features
→ /speckit-plan → /speckit-tasks → /speckit-implement
→ /speckit-ac-tests-write → /speckit-ac-tests-analyze
```

| # | Step | Started by | Done by | Main output |
|---|------|-----------|---------|-------------|
| 1 | Spec | `/speckit-specify`, `/speckit-clarify` | main agent + user | `specs/NNN-x/spec.md` |
| 2 | Draft AC, review, lock `sources` | `/speckit-ac-translate` (phase 1) | main agent drafts, user reviews | `specs/NNN-x/acceptance.md`, `Samples/F00N/**`, `specs/NNN-x/ac/sources.lock` |
| 3 | Translate, resolve issues, lock `features` | `/speckit-ac-translate` (phase 2) | `ac-feature-translator`, then the user | `Features/F00N/*.feature`, `translation-report.md`, `specs/NNN-x/ac/features.lock` |
| 4 | Plan, tasks, implementation + unit tests | `/speckit-plan`, `/speckit-tasks`, `/speckit-implement` | main agent | source code, unit tests (green) |
| 5 | Write AC step definitions | `/speckit-ac-tests-write` | `ac-test-writer` | `StepDefinitions/F00N/**`, `Support/**`, `writer-report.md` |
| 6 | Run AC tests and analyze | `/speckit-ac-tests-analyze` | main agent, plus `ac-test-fail-judge` on failures | `ac-results.md`, `judge-report.md` |

Critic reviews (`/speckit-ac-critic`) are optional at the marked points. Stage `ac` reviews
`acceptance.md` before `sources` is locked (normal revise loop, max 3 passes). Stage `features` is
**report-only**: nobody edits `.feature` files; findings go to the user, who approves, re-translates,
or fixes `acceptance.md`.

**Translation issues (step 3).** For each reported item the user chooses **skip** (no scenario; the
item stays untested and is recorded by a script) or **fix**, or a **full stop**. A fix always goes
back to `acceptance.md`: edit, review, unlock and re-lock `sources`, translate again. The translator
never applies fixes itself.

**After step 6** the user decides: fix the implementation (then analyze again), rewrite the tests with
the judge's feedback (`/speckit-ac-tests-write` again), re-translate (unlock `features`), or fix the
spec or the AC (review, unlock, edit, re-lock).

**Spec drift.** The `sources` lock also stores the hash of `spec.md`. If `spec.md` changes after
locking, later steps stop and ask the user to confirm the AC are still valid, or to unlock, edit and
re-lock.

**Coverage rule.** Every functional requirement (`FR-…`) has at least one AC item; every spec
scenario is covered or listed as "not testable through the API" with a reason. AC items carry IDs and
traceability, e.g. `AC-001 (FR-003; US1-AS2)`.

## 2. Spec inputs for the AC subagents

Per feature:

- **Always:** `specs/NNN-x/spec.md`, `.specify/memory/constitution.md`, `specs/NNN-x/acceptance.md`.
- **Optional:** extra project documents listed in `.workflow/config.json` (asked at init; the main
  agent never adds them on its own).
- **Never:** `plan.md`, `research.md`, `data-model.md`, `contracts/`, `tasks.md`, `CLAUDE.md`. They
  describe the solution, not the requirement.

Rules that live only in `CLAUDE.md` never reach the subagents. The AC draft phase flags them;
`/speckit-ac-init` offers a testability section through `/speckit-constitution` (it never edits the
constitution itself).

## 3. Isolation

### 3.1 Who can see what

"Main agent" here also means **every other subagent type** (Explore, general-purpose, Plan, …). Only
the three AC roles get their own rules; otherwise the main agent could ask another subagent to read
the step definitions for it.

Paths: `<ac>` = the AC project folder (outside the solution file), `F00N` = the feature tag,
`runs/` = `specs/NNN-x/ac/runs/`.

| Artifact | Main agent | ac-feature-translator | ac-test-writer | ac-test-fail-judge |
|---|---|---|---|---|
| `specs/NNN-x/spec.md`, constitution, configured spec inputs (§2) | read/write (spec steps) | read (current feature's spec only) | read (current feature's spec only) | read (every feature's spec) |
| `specs/NNN-x/acceptance.md` | read/write until `sources` locked, then read | read (current feature) | read (current feature) | read (every feature) |
| `<ac>/Samples/F00N/**` | read/write until that feature's `sources` locked, then read | read (current feature) | read | read |
| `<ac>/Features/F00N/*.feature` | read only (guard; no `.feature` anywhere in `<ac>`) | read/write `.feature` files only, current feature only, until `features` locked | read | read |
| `specs/NNN-x/ac/*.lock` | written only by the lock script (guard) | no | no | no |
| AC project files directly in `<ac>/` (`*.csproj`, `reqnroll.json`, `xunit.runner.json`, `Directory.Build.props`) | read/write | no | read | read |
| `<ac>/StepDefinitions/**`, `<ac>/Support/**` | **no** (guard) | **no** | read/write, never a `.feature` (see §4) | read |
| `<ac>/bin/`, `<ac>/obj/` (build output) | read/write | **no** | **no** | **no** |
| Implementation source | read/write | **no** | **no** | **no** |
| Unit test project(s) | read/write | **no** | **no** | **no** |
| Reference assemblies + API listings (`<refsDir>/**`, default `artifacts/refs/`; made by script) | read (guard blocks writes) | no | read | read |
| `runs/translate-NNN/translation-report.md` | read (guard blocks writes to `runs/`) | read/write (active run only) | no | no |
| `runs/run-NNN/input-feedback.md` | read | no | read (active run) | no |
| `runs/run-NNN/writer-report.md` | read | no | read/write (active run) | read (active run) |
| `runs/run-NNN/analyze-K/ac-results.trx` (raw) | read | **no** | **no** | **no** |
| `runs/run-NNN/analyze-K/ac-results.md` (cleaned) | read | **no** | **no** | read (active analyze) |
| `runs/run-NNN/analyze-K/judge-report.md` | read | no | no | write (active analyze, `Write` only) |
| `.workflow/active-run.json` | read (written only by the run scripts; guard) | no | no | no |
| `.workflow/config.json` | read/write (`/speckit-ac-init`) | no | no | no |
| Everything else in the repo | read/write | **no** | **no** | **no** |
| Bash | yes | **only one exact command**: the reference-mode build of the AC project | same | **none** |
| Skill | as usual, except `/speckit-ac-*` (started only by the user; guard) | **none** | **none** | **none** |
| Web, MCP, Agent tools | as usual | **none** | **none** | **none** |

"Current feature", "active run" and "active analyze" come from `.workflow/active-run.json`, which the
run scripts write right before each subagent starts ([CONFIG.md](CONFIG.md)). An AC subagent without
a matching marker is denied every call.

### 3.2 Principles

1. **Default deny for the AC roles.** The guard allows only what is listed above. Unknown tools
   (MCP tools included) and unknown paths are denied.
2. **The main agent never writes anything a subagent reads**, except the spec inputs, `acceptance.md`
   and golden samples (before they are locked) and project files. Everything else a subagent reads is
   produced by a **deterministic script** or by another AC subagent: API listings, cleaned test
   results, writer feedback, `.feature` files. Reason: the main agent knows the implementation and
   could leak details by accident. (The *content* of the writer feedback is written by the judge, who
   has seen test output — see §6.)
3. **Subagent prompts are fixed templates.** Commands invoke subagents with an exact prompt that
   contains only a run id and file paths (plus the test framework for the writer). Each agent file
   defines its template in `## Your task message`; `task_message.py` fills it in, records the result
   in the active-run marker and prints it, and the command passes that output unchanged. The **guard
   enforces it**: a main-agent `Agent` call that starts an AC role is denied unless its prompt equals
   the recorded message (line ends and trailing spaces aside) and it runs in the foreground. The main
   agent adds no explanations, hints, opinions or context. User decisions after a translation are
   recorded by a script that accepts only AC ids, never free text.
4. **Subagents don't load `CLAUDE.md`** (`omitClaudeMd: true`; Claude Code support to be verified in
   step 1), because `CLAUDE.md` may describe the implementation. Consequence: every domain rule the
   tests depend on must be in the spec inputs (§2).
5. **The test writer never sees test execution results.** It gets only the judge's feedback section,
   which must not contain values observed from the implementation.
6. **Expected values are literals.** Every expected value comes from the AC text or a golden sample
   file. Tests never compute expected values from spec data at run time; a misreading shared with the
   implementation would otherwise pass both.
7. **Translation changes form, never meaning.** The translator only normalises syntax. Anything that
   would change, add or choose a meaning is reported as an issue; fixes go back to `acceptance.md`.
8. **Hooks fail closed.** Inside the guard any error exits with code **2** (block); other non-zero
   exit codes do not block. If the guard **cannot be launched** (interpreter missing, timeout), the
   hook entry's `"onFailure": "block"` blocks the call (Claude Code support to be verified in step 1).
   The guard runs with the Python command stored in `.workflow/config.json`, never from the
   `speckit-ac` tool's own environment. A broken config blocks every call; a **missing** config (the
   extension is installed but `/speckit-ac-init` has not run) lets the main agent work and blocks the
   AC subagents.
9. **Every subagent works on one active run.** The run scripts record the feature, run and role in
   `.workflow/active-run.json` right before a subagent starts; the guard pins all of that role's paths
   to it and denies the role when the marker is missing, for another role or malformed. The run ends at
   `changed_files.py check`, which deletes the marker: afterwards nothing can start or act as an AC
   role until the next run script. `/speckit-ac-tests-analyze` ends a run that stops before its judge
   (build failure, no TRX, no results, every test passed) with `changed_files.py clear`. A marker can
   still outlive a command that is interrupted before its check:
   - after `new_analyze.py`: no task message yet, so no launch is possible;
   - between `task_message.py` and the check: the same launch stays possible.

   **A run script never replaces another run's marker** (step 8 decision). `new_run.py` and
   `new_analyze.py` refuse while one exists: subagents may run in the background, and re-pinning a
   still-working subagent to another run would break it without notice. The command stops and reports.
   Once no AC subagent is running any more, the user ends the old run with `changed_files.py clear`
   (`smoke_test.py end <role>` for a smoke-test marker) and starts again.
10. **The main agent never starts `/speckit-ac-*` itself.** The deploy step marks those skills
    human-only and the guard blocks a main-agent `Skill` call for them; users type the command.

## 4. Multi-feature model

- One AC project for all features, outside the solution file. Layout: `Features/F00N/`,
  `Samples/F00N/`, `StepDefinitions/F00N/`, `Support/F00N/`, `Support/Shared/`.
- Reference assemblies and API listings (`<refsDir>`, default `artifacts/refs/`, git-ignored) are
  one folder for all features: the API belongs to the solution. A script regenerates them at the
  start of translate and tests-write.
- Per-feature records: `specs/NNN-x/acceptance.md`, `specs/NNN-x/ac/{sources.lock,features.lock}`,
  `specs/NNN-x/ac/runs/{translate-NNN,run-NNN/analyze-K}/`.
- Tags: a feature tag `@F00N` (added by the translator, enforced by a check script) plus `@AC-NNN`,
  unique within a feature. Reports key on `F00N/AC-NNN`.
- The writer binds with `[Scope(Tag = "F00N")]` on every `[Binding]` class, writes no
  `[BeforeTestRun]`/`[AfterTestRun]` hooks (they can't be scoped), and keeps only plain helpers (no
  bindings) in `Support/Shared/`.
- After an API change the writer may make **minimal compile fixes** in other features' step
  definitions, and must list each one in its report ("Cross-feature changes"). A fix that would need
  a new value or a different assertion becomes a pending step `API-CHANGED: <reason>` instead.
- `/speckit-ac-tests-analyze` always runs **all features'** tests. Results are grouped "current
  feature" vs "regression". `--current` narrows what the judge sees and judges to the current
  feature: regressions are only counted and named by `F00N/AC-NNN` (a per-feature test filter would
  need the runner and its filter syntax; not in v1.0). A failed build reports only error counts and
  codes.
- Judge verdicts: `TRANSLATION_FAULT`, `TEST_FAULT`, `IMPLEMENTATION_FAULT`, `SPEC_AMBIGUITY`,
  `UNEXPRESSIBLE`, `INCONCLUSIVE`, and `SUPERSEDED` — for regression scenarios only: an earlier
  feature's AC conflicts with the current feature's `spec.md`. For that, the judge reads the failing
  scenario's feature spec and AC plus the current feature's spec. The judge's feedback to the writer
  holds only what the current feature's writer can fix (its own scenarios and its cross-feature
  changes).

## 5. Locks

- `sources` = `acceptance.md` + the feature's golden samples, plus the recorded hash of `spec.md`.
- `features` = the feature's `.feature` files.
- Locks are content hashes written and checked by a script (`ac_lock.py`). Later steps stop when a
  locked file changed; the user unlocks, edits and re-locks explicitly.
- Spec drift: `ac_lock.py verify sources` exits **3** when only `spec.md` changed since locking. The
  command then asks the user to confirm the AC still hold (`ac_lock.py confirm-spec sources` re-records
  the spec hash) or to unlock, edit and re-lock. Every command handles the exit codes the same way:
  0 go on, 1 stop (locks change only on the user's explicit request), 3 ask.
- `/speckit-ac-tests-analyze` also verifies the existing locks of every other feature: a changed lock
  stops it (those tests would run against unreviewed AC), spec drift there only warns.
- `sources` is locked only after the user approves and `check_acceptance.py` passes (ids,
  references, coverage of every `FR-NNN` and spec scenario, golden samples).

## 6. Known limits

- The guard works on tool calls. It reads a shell command as text and catches the plain forms:
  `<ac>/StepDefinitions/…` (also spelled with `./`, `//` or `\`), and a command that names the AC
  folder together with `StepDefinitions` or `Support/` (`cd <ac> && cat Support/…`). The main agent
  could still reach step definitions with a Bash command that doesn't name them (a variable, a glob,
  a recursive `grep` over the test folder), or change a
  `.feature` with Bash or an IDE edit tool. These stay soft rules in `CLAUDE.md`. A main-agent
  `Grep` over the whole repo is blocked only if its `path` points into the AC folders. Bash can also
  write the files the guard denies to the main agent's tools (locks, `runs/`, `<refsDir>`, the
  active-run marker). A marker forged that way also carries the `taskMessage` the launch rule
  compares with, so it would let the main agent start an AC role with any prompt; the launch rule
  closes only the tool-call routes.
- The guard checks an AC launch's `prompt` and `run_in_background`, not its `description` (a short
  label in the UI). In the live runs (steps 7–8) it appeared only in Claude Code's subagent metadata,
  never in the subagent's messages.
- The main agent can edit the guard, the scripts and the installed agent files themselves
  (`.specify/extensions/ac/`; `agents/*.md` are the source of every task message),
  `.claude/settings.json` (the guard registration) and `.workflow/config.json` (which shapes every
  guard rule; `/speckit-ac-init` must write it, so the guard cannot deny it). `speckit-ac doctor`
  checks the deployed files against the hashes in `.workflow/deploy.json` (CRLF folded to LF), the
  skills' `disable-model-invocation: true`, the guard registration and a guard self-test, and the
  config's Python command; it writes nothing and runs no dotnet (`/speckit-ac-init` verifies the .NET
  side).
- A user's own `specify integration upgrade` or `specify extension add --force` silently turns the
  `speckit-ac-*` skills back into model-invocable ones (the guard still blocks the call). `speckit-ac
  doctor` reports it; `speckit-ac upgrade` patches them again.
- `speckit-ac install` rewrites `.claude/settings.json` with 2-space JSON indentation (spec-kit's own
  style; spec-kit also rewrites the file on every `extension add` / `remove`). A file in that style
  comes back from `uninstall` byte for byte; any other style keeps its content but not its
  formatting. Uninstall also adds a final line break to a `CLAUDE.md` / `.gitignore` that had none.
- `git diff`, `git show`, `git log -p` and review tools (code-review skills, PR review bots) show step
  definitions to the main agent unless those folders are excluded. Soft rule in `CLAUDE.md`.
- API names and signatures are visible to the writer. That's by design: tests must use them.
  `const` values and default parameter values are visible in reference assemblies too.
- Exception messages from the implementation reach the judge through `ac-results.md`. They don't
  reach the writer only because the judge is told to keep observed values out of the feedback
  section. The script that extracts the feedback is deterministic; its content is not.
- The hand-back screen catches code by its markers only:
  - fences;
  - Reqnroll attributes, also qualified (`[Reqnroll.Binding]`);
  - C# declarations with an access modifier;
  - expression bodies.

  A subagent could still describe step-definition logic in prose in its final message; its prompt forbids
  it. A summary that happens to look like a declaration (`public API Total(…)`) is denied, and the
  subagent hands back again.
- The guard depends on the Python interpreter being found and on the folder being trusted.
  `onFailure: "block"` and the live guard smoke test (`/speckit-ac-init smoke`) cover this.
- Locks hash the bytes on disk. `.gitattributes` pins LF for the hashed text files, but a file saved
  with CRLF and locked **before** git normalised it has a different hash from the LF copy in another
  checkout, so `verify` fails there. Lock only files saved with LF.
- The smoke test compares (tool, decision) counts, because `guard.log` holds no paths. A wrongly
  allowed read shows up as a missing `deny`, not by its path.
- Claude Code may run every AC subagent (and the critic) in the background, even though the
  commands ask for the foreground. This happened in every launch of the step 7 and step 8 live runs.
  - The commands therefore tell the main agent to wait for the hand-back and make no other tool call
    before it. In step 8 it ended its turn and went on when the hand-back arrived.
  - This is a prompt rule. A main agent that went on early would run `changed_files.py check`, which
    deletes the marker, and the guard would then deny the subagent's next call.
- On Windows the hook command runs in Git Bash: a hand-edited command with backslashes in a path
  loses them (`C:\x\python.exe` becomes `C:xpython.exe`). The deployed command uses forward slashes.
- The critic's "no code reading" rule in stage `ac` is a prompt rule only: the critic runs with
  main-agent permissions, so the guard cannot enforce it.
- Golden samples are only as strong as their content. A sample that contains none of the inputs
  where alternatives differ passes for all of them.
- The translator decides what counts as "changing the meaning". The user sees every reported issue,
  the `features` critic stage compares scenarios with AC items, and the judge checks translation
  fidelity when a test fails — but a faithful-looking mistranslation of a passing scenario can still
  go unnoticed unless someone reads the features.
