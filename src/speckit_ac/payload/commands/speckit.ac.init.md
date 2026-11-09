---
description: "AC setup, once per project: detect the .NET solution and test setup, ask what can't be detected, write .workflow/config.json, create the Reqnroll acceptance-test project and verify the setup; `smoke` runs the live guard smoke test. Started only by the user."
argument-hint: "[smoke]"
---

# /speckit-ac-init

## User input

```text
$ARGUMENTS
```

The input is empty or the word `smoke`. Anything else: stop and ask the user.

## Rules

Follow the steps exactly. Stop at the first failure and report it.

- Run every script from the current working directory as
  `<python> .specify/extensions/ac/scripts/<name>.py …`. Never use `$CLAUDE_PROJECT_DIR` in a script
  path. Before `.workflow/config.json` exists, `<python>` is `uv run --no-project python -I`; after
  that it is the value of `python` in the config.
- The scripts write every file. The **only** file you edit yourself is the `<NoWarn>` property of the
  AC project file (setup step 7). Never edit `.workflow/config.json`, the solution, the product's
  projects or the constitution.
- Never read, search or show anything under the AC project's `StepDefinitions/` or `Support/`.
- Never start another command; name the next step and stop.

## Mode

- Input `smoke` → **smoke** mode (the steps under "Smoke").
- No `.workflow/config.json` → **setup** mode (the steps under "Setup").
- `.workflow/config.json` exists → **verify** mode (the steps under "Verify"). The configuration is
  changed only by hand: the user edits the config and runs `/speckit-ac-init` again.

## Setup

1. Run `init_detect.py` and read its JSON.
   - `environment` not empty: show every problem and stop (spec-kit-ac v1.0 needs Windows, uv, pwsh,
     dotnet, git, `CLAUDE.md` and spec-kit initialised with `--script ps` and sequential feature
     numbers).
   - `solution` is null: ask the user which of `solutions` is the product solution, then run
     `init_detect.py --solution <answer>` and continue with that output.
   - `blockers` not empty: show them and stop, or ask (an `InternalsVisibleTo` blocker: remove it — the
     user's change — or leave that project out of the surface).
2. Ask the user only what detection did not settle, one question at a time:
   - **AC surface** (`proposal.acSurfaceProjects`): the projects whose public API the acceptance tests
     use. Ask when there is more than one candidate; a single candidate is only shown in the summary.
     A chosen project with `internalsVisibleTo` entries: stop and ask (remove it, or leave the project
     out).
   - **Test framework**: ask when `proposal.testFramework` is null (`testFrameworkReason` says why);
     default `xunit3`. Then run `init_detect.py --framework <answer>` (with `--solution` if you used
     it) and use its `supported`.
   - `supported.supported` is false: show `supported.reason` and `supported.supportedPairs`, stop and
     ask the user how to proceed (another framework, or another runner in `global.json`).
   - **Target framework**: ask when `proposal.targetFramework` is null (`targetFrameworkReason`).
   - **Extra spec inputs**: always ask; default none. Explain that the AC subagents read these
     documents besides each feature's `spec.md`, `acceptance.md` and the constitution, so they must
     describe the domain, never the implementation. Refuse any answer that equals, contains or lies
     inside one of `implementationFolders` (the code), or `specs/`, `.specify/`, `.workflow/`, the AC
     project or the refs folder, say why, and ask again.
3. Show **one summary** of every value about to be written: solution, AC surface projects, unit test
   projects, test framework and runner, target framework, AC project folder, refs folder, spec inputs,
   whether central package management is on. Mark which values were detected and which are defaults.
   Wait for an explicit confirmation. Any change: update the value and show the summary again.
4. `init_config.py --solution <solution> --surface <project> … --unit-tests <project> …
   --ac-project-dir <folder> --refs-dir <folder> --spec-input <path> … --framework <framework>
   --runner <runner>` (one `--surface` / `--unit-tests` / `--spec-input` per value; `<runner>` is the
   detected `runner`; quote a path that contains spaces, such as the solution). It writes
   `.workflow/config.json` and prints it.
5. `init_scaffold.py --target-framework <the confirmed target framework>`. It creates the AC project,
   adds the packages and the local tool `ilspycmd`, and writes the managed blocks in `.gitignore` and
   `.gitattributes`. If it fails: show its output, and tell the user to delete
   `.workflow/config.json` and review the files it lists before running `/speckit-ac-init` again.
6. `init_verify.py`. It prints one line per check and a total.
7. If a build check FAILs and the lines under it are warnings treated as errors (`CSnnnn`, `RQnnnn`)
   in **generated** files (`*.feature.cs` under `obj/` or `obj-ref/`): add exactly those codes to
   `<NoWarn>` in the AC project file (`<NoWarn>$(NoWarn);CS1234</NoWarn>` in its first
   `PropertyGroup`), tell the user which codes and why, and run `init_verify.py` once more. Any other
   failure: stop and report it.
8. Report (see "Report"), then stop.

## Verify

1. Read `.workflow/config.json` and show it.
2. `init_verify.py`; then setup step 7 if it applies.
3. Report the verification lines and the total. Stop.

## Smoke

Run this in a **new session** started after `/speckit-ac-init`: agents and hooks are loaded when a
session starts, and workspace trust is per folder. Run it again in every new checkout or worktree.

1. Read `.workflow/config.json`. Missing: stop and point to `/speckit-ac-init`.
2. For each role in this order — `ac-feature-translator`, `ac-test-writer`, `ac-test-fail-judge`:
   1. `smoke_test.py start <role>` — prints the smoke prompt;
   2. the `Agent` tool with `subagent_type: <role>`, `run_in_background: false`, and `prompt` = the
      exact output of `smoke_test.py start`. Add nothing, remove nothing, change nothing. The guard
      denies any other prompt. Wait for the subagent's hand-back (its result) before anything else. If
      the tool says it runs in the background, make no other tool call until its result arrives; only
      then run `smoke_test.py end`;
   3. `smoke_test.py end <role>` — compares the guard's log with the expected decisions and removes the
      temporary files. Show its output.
3. Manual checks, one at a time; report each result:
   1. `smoke_test.py isolation-file create` prints a path. Try to `Read` that file yourself: the guard
      must block it.
   2. Start an `Explore` subagent and ask it to read the same file and report its first line. Pass:
      the guard denies the launch (its prompt names the folder), or the subagent reports that its read
      was blocked. Fail: the subagent shows the file's content. Then `smoke_test.py isolation-file
      delete`.
   3. Ask the user to point the hook command for `.specify/extensions/ac/hooks/guard.py` in
      `.claude/settings.json` at a Python interpreter that does not exist, start a new session, and
      run any tool there: it must be blocked (`onFailure: block`). The user restores the command **by
      hand**, because the blocked guard also blocks your edit.
4. Report every result. If any check did not block as expected: stop and tell the user. Likely causes:
   the folder is not trusted, the Python command is wrong, the hook is not registered, or
   `onFailure` is not supported.

## Report

- The config values, the files created or changed (from `init_scaffold.py`), every verification line
  and the total, and any deviation with its reason (for example `NoWarn` codes you added).
- Offer a testability section for the constitution, as text the user may pass to
  `/speckit-constitution` (never edit the constitution yourself):
  - time comes from `TimeProvider`, never `DateTime.Now`;
  - external effects (email, HTTP, files, …) go through public interfaces;
  - errors are observable (exception types or result types), never silent;
  - the AC surface has a public way to build the system with test doubles;
  - no `InternalsVisibleTo` in AC surface projects (it leaks internals into the reference
    assemblies the test writer sees).
- Next: start a **new session** in this folder and run `/speckit-ac-init smoke`; repeat it in every
  new checkout or worktree. Then the first feature: `/speckit-specify`.
