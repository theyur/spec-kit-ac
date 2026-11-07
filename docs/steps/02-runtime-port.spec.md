# Step 2 — Port the guard and scripts to the per-feature model

**Status:** done (2026-11-07; decisions 1–8 approved; R10/R11/R16 amended during plan review) · **Tracker row:** 2 · **Source of truth:** `docs/DESIGN.md`

## Goal

Port CT's fail-closed `PreToolUse` guard and its ten workflow scripts into the extension payload,
and adapt them from CT's single global AC set to spec-kit's per-feature model (DESIGN §3, §8). The
step 1 gate decisions are part of it: the guard blocks main-agent `Skill` calls for `speckit-ac-*` and
allows `SubagentHandback` for the AC roles after a content check. CT's table test becomes a pytest
suite with the CT cases plus per-feature and cross-feature cases, and every script gets its own tests.
No agents, commands, `extension.yml`, init, deploy or CLI work (steps 3–6).

## Context

- Sources (read only): `<original project>\.claude\hooks\guard.py` (271 lines), `hooks\test_guard.py`
  (CT-config driven, 105 cases + 2 input cases), `scripts\*.py` (10 scripts, ~620 lines). The CT
  scripts find the repo root as `Path(__file__).parents[2]`. They read `.workflow/config.json` with
  CT keys (`specFile`, `acSources`, `lockedPaths`, …) and keep everything under `.workflow/`: locks,
  `runs/translate-NNN`, `runs/run-NNN/analyze-K`.
- The per-feature model (DESIGN §3, §8; WORKFLOW §3.1, §4, §5):
  - AC and locks: `specs/NNN-x/acceptance.md`, `specs/NNN-x/ac/{sources,features}.lock`.
  - Runs: `specs/NNN-x/ac/runs/{translate-NNN,run-NNN/analyze-K}/`.
  - AC project folders: `Features/F00N/`, `Samples/F00N/`, `StepDefinitions/F00N/`, `Support/F00N/`,
    `Support/Shared/`.
  - Tags: `@F00N` plus `@AC-NNN`; the writer binds with `[Scope(Tag = "F00N")]`.
  - The `sources` lock stores the hash of `spec.md` (spec drift).
- spec-kit 1.0.2 facts (checked while drafting):
  - `.specify/feature.json` is `{"feature_directory": "specs/001-stub"}`; `/speckit-specify` writes it.
  - Feature folders are `specs/NNN-name` (sequential, ≥ 3 digits) by default. With
    `feature_numbering: "timestamp"` in `.specify/init-options.json` they are
    `specs/YYYYMMDD-HHMMSS-name`; a user can also set any `SPECIFY_FEATURE_DIRECTORY`.
- Installed layout: spec-kit copies the extension folder to `.specify/extensions/ac/` (step 1, 3.1).
  So the payload's `hooks/guard.py` runs as `.specify/extensions/ac/hooks/guard.py` and its scripts
  as `.specify/extensions/ac/scripts/*.py`.
- `python -I` (the v1.0 hook and script command is `uv run --no-project python -I`, DESIGN §2) does
  **not** put the script's own folder on `sys.path`, so a sibling helper module must be added to the
  path explicitly.
- Interactive Claude Code expands a user-typed `/skill` directly; it is not a `Skill` tool call, so
  the guard's `Skill` block does not stop users. The step 7–8 smoke test confirms this.

## Requirements

### Layout and conventions

- **S02-R01** New payload files:
  - `src/speckit_ac/payload/hooks/guard.py`;
  - `src/speckit_ac/payload/scripts/`: `aclib.py` (shared helper), `ac_feature.py` (new),
    `ac_lock.py`, `changed_files.py`, `check_features.py`, `clear_generated.py`, `export_refs.py`,
    `extract_feedback.py`, `new_analyze.py`, `new_run.py`, `record_skips.py`, `summarize_trx.py`.

  Rules:
  - Python ≥ 3.11, standard library only.
  - No CT specifics anywhere in the payload: no `SPEC.md`, `knowledge-base`, `CT.`, `.workflow/runs`,
    `experiment-log` and no `WORKFLOW-SETUP` section references.
  - The payload `README.md` layout table is updated.
- **S02-R02** Project root:
  - Scripts take it from their own location (`Path(__file__).resolve().parents[4]`) and fail with a
    clear message unless `parents[3]` is named `.specify`.
  - The guard uses `CLAUDE_PROJECT_DIR`, falling back to the same location rule, and keeps CT's
    worktree rule: a cwd under `<project>/.claude/worktrees/<name>/` that has its own
    `.workflow/config.json` becomes the root.
- **S02-R03** Shared code:
  - Scripts share `aclib.py`, which they load by putting their own folder on `sys.path` first.
  - The guard stays **one self-contained file**: it is the security boundary, and a broken helper must
    not change its decisions.
  - `tests/test_stdlib_only.py` allows the local module name `aclib`.
- **S02-R04** Config (`.workflow/config.json`, written by `/speckit-ac-init` in step 5):
  - Step 2 fixes the keys the runtime reads and documents them in a new `docs/CONFIG.md`:
    - `schemaVersion` (= 1), `python`, `solution`;
    - `specInputs`: extra project documents, files or folders, may be empty;
    - `acSurfaceProjects`, `unitTestProjects`, `acProjectDir`, `acProject`, `refsDir`;
    - `acRefBuildCommand`, `unitTestCommand`, `acTestCommand`.
  - CT's `specFile`, `acSources` and `lockedPaths` are dropped: the paths derive from the feature.
  - A missing key or a wrong `schemaVersion` is an error with a clear message: in the guard it exits 2,
    in scripts it exits 1.

### Features

- **S02-R05** A feature is a folder `specs/<N>-<name>` directly under `specs/`, where `<N>` is ≥ 3
  digits:
  - its tag is `F<N>` (`specs/001-login` → `F001`);
  - timestamp folders (`specs/YYYYMMDD-HHMMSS-*`), `feature_numbering: "timestamp"`, nested and
    custom folders are rejected with a message naming the v1.0 limit;
  - two folders with the same `<N>` are an error.
- **S02-R06** Scripts that act on one feature take an optional `--feature <specs/N-x | N-x | N | FN>`:
  - the default is `.specify/feature.json`;
  - they print the resolved folder and tag;
  - `ac_feature.py [--feature …]` prints one JSON object (feature dir, tag, `spec.md`,
    `acceptance.md`, `ac/` and `runs/` paths, the AC project's `Features/FN`, `Samples/FN`,
    `StepDefinitions/FN`, `Support/FN` folders) for the commands in step 4 to fill their prompt
    templates.

### Active run (new, the guard's view of "the current feature")

- **S02-R07** `new_run.py` and `new_analyze.py` write `.workflow/active-run.json`:
  - contents: `role`, `feature` (dir), `tag`, `run`, `analyze` (null except for the judge);
  - the role is `ac-feature-translator` for `new_run.py translate`, `ac-test-writer` for
    `new_run.py write`, and `ac-test-fail-judge` for `new_analyze.py`.
  - The guard reads it for every AC-role call and denies the call when the marker is:
    - missing or unreadable;
    - for a different role;
    - pointing at a feature folder that fails S02-R05 or contains `..`.
  - Every AC-role path rule (S02-R10–R12) is pinned to the marker's feature and run, not to `run-*`
    globs.

### Guard

- **S02-R08** CT behaviour kept:
  - `agent_type` picks the policy: the three AC roles get default-deny rules; the main agent and every
    other agent type get the main rules.
  - Block = reason on stderr + exit 2; allow = exit 0 with no output; any error = exit 2.
  - The AC-role deny suffix is kept.
  - `.workflow/guard.log` gets one line per subagent call (agent type, tool, decision).
  - Paths are normalised (realpath, case-folded, forward slashes).
  - Paths outside the project: the AC roles are denied; the main agent may write there.
  - The `PowerShell` tool is checked like `Bash` for the main agent and denied for the AC roles.
- **S02-R09** Config states:
  - **missing** `.workflow/config.json` (extension installed, init not run yet) → main-policy calls
    are allowed (except S02-R13's `Skill` rule) and AC-role calls are denied;
  - **present but invalid** → every call is blocked (exit 2).
- **S02-R10** Translator, active feature `S = specs/N-x`, tag `T`:
  - **reads:**
    - `S/spec.md`, `S/acceptance.md`, `.specify/memory/constitution.md`, config `specInputs`;
    - `<ac>/Samples/T/**`, `<ac>/Features/T/**`;
    - `S/ac/runs/<run>/translation-report.md`.
  - **writes:** `*.feature` files under `<ac>/Features/T/` (unless `S/ac/features.lock` exists) and that
    report (only `.feature` files: amended after plan review round 2).
  - **Bash:** exactly `acRefBuildCommand` (whitespace-normalised).
  - Everything else is denied, including other features' folders and `S/plan.md`, `tasks.md`,
    `research.md`, `data-model.md` and `contracts/`.
- **S02-R11** Writer:
  - **reads:**
    - `S/spec.md`, `S/acceptance.md`, constitution, `specInputs`;
    - `<ac>/Features/**`, `<ac>/Samples/**`, `<ac>/StepDefinitions/**`, `<ac>/Support/**`, files
      directly in `<ac>/`, `<refsDir>/**`;
    - `S/ac/runs/<run>/input-feedback.md` and `writer-report.md`.
  - **writes:**
    - `<ac>/StepDefinitions/**` and `<ac>/Support/**` (all features, for DESIGN §8's cross-feature
      compile fixes), except `*.feature` files (Reqnroll compiles every `.feature`, so a writer-made one
      would add unlocked scenarios; amended after plan review round 2);
    - `S/ac/runs/<run>/writer-report.md`.
  - **Bash:** exactly `acRefBuildCommand`.
- **S02-R12** Judge:
  - **reads:**
    - every feature's `spec.md` and `acceptance.md` (needed for `SUPERSEDED`), constitution,
      `specInputs`;
    - the same AC project folders and `refsDir` as the writer;
    - `S/ac/runs/<run>/writer-report.md` and `S/ac/runs/<run>/<analyze>/ac-results.md`.
  - **writes:** only `S/ac/runs/<run>/<analyze>/judge-report.md`, with `Write` only.
  - **Bash:** none.
  - **Grep/Glob for all three roles:**
    - an explicit `path` is required: a readable folder, or a file the role may read;
    - never the `<ac>` folder itself;
    - patterns must not contain `..` and must not be absolute.
  - **All three roles:** `SubagentHandback` passes only without code markers (CT's regex); every
    other tool is denied (Skill, Agent, Web, MCP, PowerShell, …).
- **S02-R13** Main policy (main agent and all other agent types):
  - **CT rules kept:**
    - G2: no tool call may name or root a search in `<ac>/StepDefinitions` or `<ac>/Support`,
      including bare names in shell commands run inside `<ac>`;
    - G3: `.feature` files are never written.
  - **Writes are denied for** (G1, per feature):
    - `specs/N-x/acceptance.md` and `<ac>/Samples/FN/**` while that feature's `sources.lock` exists;
    - any `specs/*/ac/*.lock`, at any time (only the lock script writes them);
    - anything under `specs/*/ac/runs/**`, `<refsDir>/**` and `.workflow/active-run.json` (scripts and
      subagents produce what subagents read; WORKFLOW §3.2 principle 2).
  - **New:** a `Skill` call whose `tool_input.skill` starts with `speckit-ac-` (leading `/` stripped,
    case-insensitive) is denied, with a message telling the agent to ask the user to type the
    command. Other skills are allowed.

### Scripts

- **S02-R14** `ac_lock.py lock | verify | unlock | confirm-spec  sources | features [--feature …]`:
  - The lock file is `S/ac/<group>.lock`, JSON: `group`, `feature`, `files` (path → SHA-256 of the
    bytes on disk) and, for `sources`, `spec` (path + SHA-256 of `spec.md`).
  - `sources` = `S/acceptance.md` (must exist) + `<ac>/Samples/T/**` (a missing folder adds no files).
  - `features` = `<ac>/Features/T/**`, at least one `.feature`.
  - `verify` exits 1 when files differ (added / removed / changed listed), and **3 on spec drift** when
    only `spec.md` changed.
  - `confirm-spec` re-records the `spec.md` hash only when the files still match (the user confirmed
    the AC are still valid).
- **S02-R15** `new_run.py translate | write [--feature …]` and `new_analyze.py [--feature …]`:
  - CT numbering (`translate-NNN`, `run-NNN`, `analyze-K`) inside `S/ac/runs/`;
  - a `write` run copies `writer-feedback.md` from the previous run's newest `analyze-*` to
    `input-feedback.md`;
  - `new_analyze.py` fails when the feature has no `run-*`;
  - both print the new folder and write the active-run marker (S02-R07).
- **S02-R16** `changed_files.py snapshot | check <role>`:
  - CT's content-hash snapshot (stored in the git dir);
  - also scans `.workflow/`, `<refsDir>` and every `specs/*/ac/`;
  - skips `.workflow/guard.log` and build-output segments: `bin`, `obj` and their `-`/`_`/`.`
    variants (`obj-ref`); CT's `bin*` also skipped folders such as `Bindings/` (amended after plan
    review round 1);
  - the allowlist comes from the active-run marker and matches S02-R10–R12's write rules;
  - `check` fails when the marker's role differs from the argument.
- **S02-R17** `check_features.py [--feature …]`:
  - CT's structural checks on `<ac>/Features/T/**/*.feature`;
  - every file's feature-level tags include `@T`, and no scenario carries another `@F<digits>` tag;
  - exactly one `@AC-` per scenario, unique within the feature;
  - zero feature files is a failure.
- **S02-R18** `clear_generated.py features | steps [--feature …]`:
  - `features` clears `<ac>/Features/T/` and is refused while `features.lock` exists;
  - `steps` clears `<ac>/StepDefinitions/T/` and `<ac>/Support/T/`, never `Support/Shared/` or other
    features;
  - `.gitkeep` is kept and file contents are never printed.
- **S02-R19** `record_skips.py <translate-run> <AC-id>… [--feature …]`: CT behaviour, using the
  feature's `runs/`.
- **S02-R20** `summarize_trx.py <trx> <out.md> [--current FN]`:
  - Tags come from every feature's `.feature` files.
  - A test's feature comes from an `F<digits>` namespace segment in the TRX `className` when there is
    one (assumed: Reqnroll derives namespaces from folders; to be confirmed in step 7). Otherwise it
    comes from the scenario name, and a name found in more than one feature is marked ambiguous.
  - The table has a feature column; failures are titled `FN/AC-NNN <name>`.
  - With `--current`: two sections, "Current feature" and "Regression".
  - The CT stack-frame filtering stays.
- **S02-R21** `export_refs.py` and `extract_feedback.py`: CT behaviour, with only the root/config
  adaptation.

### Tests and docs

- **S02-R22** `tests/test_guard.py` (pytest, parametrised) runs the payload guard as a subprocess
  (`sys.executable -I`) in a temp project, laid out as an install would leave it:
  - `.specify/extensions/ac/hooks/guard.py`, `.workflow/config.json` (a neutral sample config);
  - two features `specs/001-alpha`, `specs/002-beta`;
  - a worktree under `.claude/worktrees/`.

  Cases:
  - every CT case, re-expressed for per-feature paths;
  - new cases for R07, R09, R10–R13: other-feature reads/writes per role, a mismatched/missing/hostile
    marker, report paths of another run, per-feature locks, lock files, runs, refs, the marker file,
    `Skill` for `speckit-ac-*` vs other skills from the main agent and from `Explore`;
  - malformed and empty input.
- **S02-R23** `tests/test_scripts.py`: each script in a temp project. `export_refs.py` is covered
  through its pure functions (`public_only`, the logic and visibility checks); its dotnet/ilspycmd
  path waits for step 7. `changed_files.py` runs in a temp `git init` repo.
- **S02-R24** Docs: `docs/CONFIG.md` (R04); `docs/WORKFLOW.md` §3–5 updated for the active-run
  marker, the missing-config rule and the main-agent write denials; the payload README. With this
  spec's approval, DESIGN gets the decision-log rows from "Decisions" below and a §8 line on the
  active-run marker.
- **S02-R25** `uv run pytest -q --tb=short` passes; the tracker row 2 is updated. No commit unless the
  user asks.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S02-A01 | All payload files of R01 exist; `test_stdlib_only` passes with them; a grep of the payload for the CT strings in R01 finds nothing | R01, R03 |
| S02-A02 | Every CT guard case has a counterpart in `test_guard.py` (mapping table in the plan) and passes | R08, R22 |
| S02-A03 | Per-feature and cross-feature guard cases pass: translator denied on `F002`/`specs/002-*` while active on `F001`; writer allowed to edit `StepDefinitions/F002/**`, denied `specs/002-*/acceptance.md`; judge allowed `specs/002-*/spec.md`; all roles denied `plan.md` | R10–R12 |
| S02-A04 | Marker cases pass: missing, wrong role, `..` in the feature, report of another run → deny | R07 |
| S02-A05 | Main-policy cases pass: locked/unlocked per feature, lock files, runs, refs, marker, `Skill` `speckit-ac-*` denied (main and Explore), other skills allowed; missing config → main allowed / AC role denied; invalid config → deny | R09, R13 |
| S02-A06 | Script tests pass, including: spec drift → exit 3 and `confirm-spec`; two folders with one number → error; timestamp folder → error; `clear_generated steps` keeps `Support/Shared/` and other features; `summarize_trx --current` splits sections; `changed_files` flags a write outside the marker's allowlist | R05, R06, R14–R21, R23 |
| S02-A07 | `uv run pytest -q --tb=short` passes (count reported); optional: the same suite on CPython 3.11 from the scratchpad, as in step 0 | R25 |

## Out of scope

- Agents (step 3), commands, `extension.yml` and the hook prompts (step 4), the `acceptance.md` format.
- `/speckit-ac-init` writing the config, choosing the Python command, the AC project scaffolding
  (step 5).
- Guard registration in `settings.json`, the `disable-model-invocation` patch, deploy, CLI (step 6).
- Running `export_refs.py` against a real .NET solution, live guard smoke test (step 7).
- Timestamp/custom feature folders, other OSes (deferred; recorded as portability issues).

## Decisions taken in this spec (confirm on approval)

1. **Active-run marker** `.workflow/active-run.json` (R07). The guard sees only the tool call, not
   which feature a subagent works on. The run scripts already run right before each subagent, so they
   record feature + run + role. AC-role calls without a matching marker are denied, and report paths
   are pinned to the active run. Alternative: read `.specify/feature.json`. Rejected: it is spec-kit's
   file, it changes with the user's current feature, and it knows nothing about runs.
2. **Missing config is not an error for the main agent** (R09). Deploy (step 6) registers the guard
   before init writes the config, and blocking every call then would make `/speckit-ac-init`
   impossible. An invalid config still blocks everything.
3. **v1.0 supports only sequential feature folders** `specs/NNN-name` (R05). The `F<N>` tag needs a
   number. Timestamp and custom folders fail with a clear message; noted as a deferred portability
   issue.
4. **Visibility per role** (R10–R12):
   - the translator sees only its own feature;
   - the writer sees its own feature's spec and AC, but all AC project folders (for shared steps and
     cross-feature compile fixes);
   - the judge sees every feature's `spec.md` and `acceptance.md` (for `SUPERSEDED`).
   Spec-side files of other features carry no implementation, so this widens nothing that matters
   for isolation.
5. **New main-agent write denials** (R13): lock files, `runs/`, `refsDir`, the marker. These turn
   WORKFLOW §3.2 principle 2 and the §3.1 table ("read" only for the main agent) into guard rules;
   CT left them as prompt rules. Bash can still write them (known limit, WORKFLOW §6).
6. **Scripts share `aclib.py`; the guard stays standalone** (R03).
7. **Spec drift is exit code 3 plus `confirm-spec`** (R14). The commands in step 4 then ask the user
   to "confirm / unlock-edit-relock".
8. CT's `experiment-log.md` is dropped: it was CT-specific.
