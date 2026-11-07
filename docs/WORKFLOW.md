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
| Spec inputs (§2) | read/write (spec steps) | read | read | read |
| `specs/NNN-x/acceptance.md`, `<ac>/Samples/F00N/**` | read/write until `sources` locked, then read | read | read | read |
| `<ac>/Features/F00N/*.feature` | read only (guard) | read/write, current feature only, until `features` locked | read | read |
| `specs/NNN-x/ac/*.lock` | written only by the lock script | no | no | no |
| AC project files (`*.csproj`, `reqnroll.json`, `Directory.Build.props`) | read/write | no | read | read |
| `<ac>/StepDefinitions/**`, `<ac>/Support/**` | **no** (guard) | **no** | read/write (see §4) | read |
| Implementation source | read/write | **no** | **no** | **no** |
| Unit test project(s) | read/write | **no** | **no** | **no** |
| Reference assemblies + API listings (`<refsDir>/**`, default `artifacts/refs/`; made by script) | read | no | read | read |
| `runs/translate-NNN/translation-report.md` | read | read/write | no | no |
| `runs/run-NNN/input-feedback.md` | read | no | read | no |
| `runs/run-NNN/writer-report.md` | read | no | read/write | read |
| `runs/run-NNN/analyze-K/ac-results.trx` (raw) | read | **no** | **no** | **no** |
| `runs/run-NNN/analyze-K/ac-results.md` (cleaned) | read | **no** | **no** | read |
| `runs/run-NNN/analyze-K/judge-report.md` | read | no | no | write |
| Everything else in the repo | read/write | **no** | **no** | **no** |
| Bash | yes | **only one exact command**: the reference-mode build of the AC project | same | **none** |
| Web, MCP, Skill, Agent tools | as usual | **none** | **none** | **none** |

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
   contains only a run id and file paths. The main agent adds no explanations, hints, opinions or
   context. User decisions after a translation are recorded by a script that accepts only AC ids,
   never free text.
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
   `speckit-ac` tool's own environment.

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
- The writer binds with `[Scope(Tag = "F00N")]`; shared helpers live only in `Support/Shared/`.
- After an API change the writer may make **minimal compile fixes** in other features' step
  definitions, and must list each one in its report.
- `/speckit-ac-tests-analyze` runs **all features** by default (`--current` narrows it). Results are
  grouped "current feature" vs "regression". A failed build reports only error counts and codes.
- Judge verdicts: `TRANSLATION_FAULT`, `TEST_FAULT`, `IMPLEMENTATION_FAULT`, `SPEC_AMBIGUITY`,
  `UNEXPRESSIBLE`, `INCONCLUSIVE`, and `SUPERSEDED` — an earlier feature's AC conflicts with a later
  feature's `spec.md`. For that, the judge reads the failing scenario's feature spec plus the current
  feature's spec.

## 5. Locks

- `sources` = `acceptance.md` + the feature's golden samples, plus the recorded hash of `spec.md`.
- `features` = the feature's `.feature` files.
- Locks are content hashes written and checked by a script. Later steps stop when a locked file
  changed; the user unlocks, edits and re-locks explicitly.

## 6. Known limits

- The guard works on tool calls. The main agent could still reach step definitions with a Bash
  command that doesn't name them (e.g. a recursive `grep` over the test folder), or change a
  `.feature` with Bash or an IDE edit tool. These stay soft rules in `CLAUDE.md`. A main-agent
  `Grep` over the whole repo is blocked only if its `path` points into the AC folders.
- `git diff`, `git show`, `git log -p` and review tools (code-review skills, PR review bots) show step
  definitions to the main agent unless those folders are excluded. Soft rule in `CLAUDE.md`.
- API names and signatures are visible to the writer. That's by design: tests must use them.
  `const` values and default parameter values are visible in reference assemblies too.
- Exception messages from the implementation reach the judge through `ac-results.md`. They don't
  reach the writer only because the judge is told to keep observed values out of the feedback
  section. The script that extracts the feedback is deterministic; its content is not.
- The hand-back screen catches code by its markers only. A subagent could still describe
  step-definition logic in prose in its final message; its prompt forbids it.
- The guard depends on the Python interpreter being found and on the folder being trusted.
  `onFailure: "block"` and a live guard smoke test cover this.
- The critic's "no code reading" rule in stage `ac` is a prompt rule only: the critic runs with
  main-agent permissions, so the guard cannot enforce it.
- Golden samples are only as strong as their content. A sample that contains none of the inputs
  where alternatives differ passes for all of them.
- The translator decides what counts as "changing the meaning". The user sees every reported issue,
  the `features` critic stage compares scenarios with AC items, and the judge checks translation
  fidelity when a test fails — but a faithful-looking mistranslation of a passing scenario can still
  go unnoticed unless someone reads the features.
