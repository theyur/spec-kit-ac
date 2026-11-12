---
description: "AC step 5: export the public API as reference assemblies and have the isolated ac-test-writer write the Reqnroll step definitions for a feature, without seeing the implementation. Started only by the user."
argument-hint: "[feature: NNN | FNNN | NNN-name] [fresh]"
---

# /speckit-ac-tests-write

## User input

```text
$ARGUMENTS
```

The input may name one feature (`NNN`, `FNNN`, `NNN-name` or `specs/NNN-name`) and may contain the
word `fresh` (delete this feature's step definitions and support code first). Anything else: stop and
ask the user.

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
    edits `acceptance.md`, locks it again and runs `/speckit-ac-translate` again.
- Starting the test writer, always in this order:
  1. `new_run.py write <feature-arg>` (prints the run folder; writes the active-run marker and copies
     the judge's last feedback, if any);
     It refuses while another AC run is active ("An AC run is still active"): stop and report its
     message. Never end that run yourself; the user does, once no AC subagent is running;
  2. `task_message.py <feature-arg>` — prints the task message;
  3. `changed_files.py snapshot`;
  4. the `Agent` tool with `subagent_type: ac-test-writer`, `run_in_background: false`, and
     `prompt` = the exact output of `task_message.py`. Add nothing, remove nothing, change nothing:
     no hints, no explanations, no context about the implementation. The guard denies any other
     prompt. Wait for the subagent's hand-back (its result) before anything else. If the tool says it
     runs in the background, make no other tool call until its result arrives; only then run
     `changed_files.py check`;
  5. `changed_files.py check ac-test-writer`. If it reports a file `OUTSIDE ALLOWLIST`, this is an
     **isolation breach**: report the file names and stop.
- Never read, search, show or summarise step definitions or `Support/` files, and never run the AC
  tests in this command.

## Steps

1. Read `.workflow/config.json`.
2. Run `ac_feature.py <feature-arg>` and show the user the feature folder and its tag.
3. Run `ac_lock.py verify sources <feature-arg>` and `ac_lock.py verify features <feature-arg>`
   (lock checks above). A missing lock means the feature is not translated yet: stop and point to
   `/speckit-ac-translate`.
4. Build the product: `dotnet build "<solution>" -nologo -v q` (`solution` from the config, quoted: it
   may contain spaces). Then run
   `unitTestCommand` once for each entry of `unitTestProjects` (`{project}` replaced). Never run the
   tests of the whole solution. If the build or any unit test run fails: stop and report. The
   implementation step is not finished.
5. Run `export_refs.py`. If it fails: stop and report the exact problem it prints.
6. If the input contains `fresh`: run `clear_generated.py steps <feature-arg>`. Do not read the
   files first.
7. Start the test writer (Rules, steps 1–5).
8. Read `writer-report.md` in the run folder. Report to the user: run id, build status, the created
   and changed file **names** (from the check in step 7), scenarios bound, unexpressible steps,
   interpretations and assumptions, cross-feature changes, missing packages. If the report lists
   missing packages: tell the user to add each one to the AC project
   (`dotnet add "<acProject>" package <id>`, `acProject` from the config; it goes into the shared
   ItemGroup, so both modes get it), then run `/speckit-ac-tests-write` again without `fresh`, so the
   bound step definitions are kept. Never add them yourself.

## Report and stop

Stop after step 8 (or at the first failure). The next step is `/speckit-ac-tests-analyze`, unless
step 8 named missing packages: then it is this command again, without `fresh`. Never
start it, or any other command, yourself.
