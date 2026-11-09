---
description: "AC step 2–3: draft a feature's acceptance.md for review and lock it, then have the isolated ac-feature-translator turn it into Reqnroll .feature files. Started only by the user."
argument-hint: "[feature: NNN | FNNN | NNN-name]"
---

# /speckit-ac-translate

## User input

```text
$ARGUMENTS
```

The input is empty or names one feature (`NNN`, `FNNN`, `NNN-name` or `specs/NNN-name`). Anything
else: stop and ask the user.

## Rules

Follow the steps exactly. Stop at the first failure and report it.

- `<python>` is the value of `python` in `.workflow/config.json`. Run every script from the current
  working directory as `<python> .specify/extensions/ac/scripts/<name>.py …`. Never use
  `$CLAUDE_PROJECT_DIR` in a script path.
- `<feature-arg>` is `--feature <the feature from the input>`, or nothing when the input names no
  feature (the scripts then use spec-kit's current feature, `.specify/feature.json`). Pass it to every
  script that accepts `--feature`.
- If `.workflow/config.json` does not exist: stop and tell the user to run `/speckit-ac-init` first.
- Lock checks. `ac_lock.py verify <group> <feature-arg>` exits with:
  - **0** — go on;
  - **1** — stop and show the script's message. Locks change only when the user explicitly asks for
    `ac_lock.py unlock <group>` / `ac_lock.py lock <group>`;
  - **3** (spec drift, `sources` only) — `spec.md` changed after the AC were locked. Show the
    message and ask the user whether the acceptance criteria are still valid. Yes:
    `ac_lock.py confirm-spec sources <feature-arg>` and go on. No: stop; the user unlocks `sources`,
    edits `acceptance.md`, locks it again and runs this command again.
- Starting the translator, always in this order:
  1. `new_run.py translate <feature-arg>` (prints the run folder; writes the active-run marker);
  2. `task_message.py <feature-arg>` — prints the task message;
  3. `changed_files.py snapshot`;
  4. the `Agent` tool with `subagent_type: ac-feature-translator`, `run_in_background: false`, and
     `prompt` = the exact output of `task_message.py`. Add nothing, remove nothing, change nothing:
     no hints, no explanations, no opinions about the acceptance criteria. The guard denies any other
     prompt. Wait for the subagent's hand-back (its result) before anything else. If the tool says it
     runs in the background, make no other tool call until its result arrives; only then run
     `changed_files.py check`;
  5. `changed_files.py check ac-feature-translator`. If it reports a file `OUTSIDE ALLOWLIST`, this is
     an **isolation breach**: report the file names and stop.
- Never edit a `.feature` file, never read or show step definitions or `Support/` files.

## Steps

1. Read `.workflow/config.json`.
2. Run `ac_feature.py <feature-arg>` and show the user the feature folder and its tag. All paths
   below come from its output (`spec`, `acceptance`, `samplesDir`, `featuresDir`, `sourcesLock`,
   `featuresLock`, `runsDir`).
3. If `featuresLock` exists: stop. The feature files of this feature are locked; unlock them
   (`ac_lock.py unlock features <feature-arg>`) only if the user explicitly asks, then run this command
   again.
4. If `sourcesLock` does not exist: **phase 1** (steps 5–10). Otherwise run
   `ac_lock.py verify sources <feature-arg>` (lock checks above) and go to **phase 2** (step 11).

### Phase 1 — draft, review, lock `sources`

5. Read the feature's `spec.md`, `.specify/memory/constitution.md`, every entry of `specInputs` in
   the config, and `.specify/extensions/ac/templates/acceptance-template.md`. These are the only
   sources of AC content. Never use `plan.md`, `research.md`, `data-model.md`, `contracts/`,
   `tasks.md`, source code, tests or `CLAUDE.md` as a source.
6. Write `acceptance.md` (path `acceptance`) in the template's format. If it already exists, show the
   user that you will revise it and ask before replacing content they wrote.
   - One item per behaviour: `### AC-NNN (<refs>) <title>`, refs = `FR-NNN` or `US<N>-AS<M>` (user
     story N, acceptance scenario M of `spec.md`), then `Given` / `When` / `Then` lines with concrete
     literal values only.
   - Fill the Coverage table: every `FR-NNN` has at least one item; every spec scenario has an item
     or the reason it is not testable through the public API.
   - Golden samples (input or expected files too large for a line) go in `samplesDir`; items name them
     by file name.
   - Delete the template's instruction comment.
7. Tell the user about every rule the acceptance criteria depend on that you know only from
   `CLAUDE.md` (or another file outside the sources of step 5). Do not put it into `acceptance.md`:
   the AC subagents never see `CLAUDE.md`. The user moves it into the spec or the constitution
   (`/speckit-constitution`), then you include it.
8. Run `check_acceptance.py <feature-arg>`. Fix every finding it reports and run it again until it
   passes.
9. Report: the number of items, the coverage summary from the check, the golden samples, the rules of
   step 7. Suggest `/speckit-ac-critic ac` for an independent review, and ask the user to review
   `acceptance.md` and the samples. Wait.
10. Lock only after the user explicitly approves and `check_acceptance.py <feature-arg>` passes:
    `ac_lock.py lock sources <feature-arg>`. Then stop: the next step is `/speckit-ac-translate`
    again (phase 2).

### Phase 2 — translate, resolve issues, lock `features`

11. Run `export_refs.py` (the translator's build compiles the AC project against the reference
    assemblies). If it fails: stop and report its message.
12. Run `clear_generated.py features <feature-arg>`.
13. Start the translator (Rules, steps 1–5).
14. Run `check_features.py <feature-arg>` and note the result.
15. Read `translation-report.md` in the run folder. Report to the user: run id, build status, the
    feature check result, items translated, and the full Issues table (AC id, kind, problem,
    suggested fix for `acceptance.md`, scope).
    If the build failed or the feature check failed: stop. The user runs `/speckit-ac-translate`
    again; you send the translator no message of your own.
16. If there are issues, ask the user to decide per item: **skip** (no scenario; the item stays
    untested), **fix**, or a **full stop**. Wait.
    - Any **fix** or a **full stop**: stop and lock nothing. The fix goes into `acceptance.md` (the
      suggested fixes are a starting point): the user asks for `ac_lock.py unlock sources`, the file
      is edited and reviewed, `ac_lock.py lock sources`, then `/speckit-ac-translate` again.
    - **Skip** for every remaining issue: run
      `record_skips.py <run id> <AC ids> <feature-arg>`.
17. Show the generated feature file names and the number of scenarios. You may read the feature files
    to answer questions; never edit them. Suggest `/speckit-ac-critic features` for an independent
    comparison with `acceptance.md`, and ask the user to approve the features. Wait.
18. Only after an explicit approval: `ac_lock.py lock features <feature-arg>`.

## Report and stop

Stop after step 10 or step 18 (or at the first failure). The next step after phase 2 is
`/speckit-plan`. Never start it, or any other command, yourself.
