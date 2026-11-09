---
description: "AC step 6: run every feature's acceptance tests against the real implementation and, if any fail, have the isolated ac-test-fail-judge decide whether the implementation, the test, the translation or an outdated acceptance criterion is at fault. Started only by the user."
argument-hint: "[feature: NNN | FNNN | NNN-name] [--current]"
---

# /speckit-ac-tests-analyze

## User input

```text
$ARGUMENTS
```

The input may name one feature (`NNN`, `FNNN`, `NNN-name` or `specs/NNN-name`), the **current
feature** whose tests were written last, and may contain `--current` (the judge then looks only at
the current feature's results). Anything else: stop and ask the user.

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
- Starting the judge, always in this order:
  1. `new_analyze.py <feature-arg>` (prints the analyze folder; writes the active-run marker);
     It refuses while another AC run is active ("An AC run is still active"): stop and report its
     message. Never end that run yourself; the user does, once no AC subagent is running;
  2. `task_message.py <feature-arg>` — prints the task message;
  3. `changed_files.py snapshot`;
  4. the `Agent` tool with `subagent_type: ac-test-fail-judge`, `run_in_background: false`, and
     `prompt` = the exact output of `task_message.py`. Add nothing, remove nothing, change nothing:
     no hints, no explanations, no opinions about the failures. The guard denies any other prompt.
     Wait for the subagent's hand-back (its result) before anything else. If the tool says it runs in
     the background, make no other tool call until its result arrives; only then run
     `changed_files.py check`;
  5. `changed_files.py check ac-test-fail-judge`. If it reports a file `OUTSIDE ALLOWLIST`, this is
     an **isolation breach**: report the file names and stop.
- Never read, search, show or summarise step definitions or `Support/` files. If the build fails,
  report only the number of errors and their error codes: no file contents, no message text that
  quotes step-definition code.

## Steps

1. Read `.workflow/config.json`.
2. Run `ac_feature.py --all`. If it fails (a folder under `specs/` that is not a feature folder):
   stop and report its message. Then run `ac_feature.py <feature-arg>` and show the user the current
   feature and its tag.
3. Run `ac_lock.py verify sources <feature-arg>` and `ac_lock.py verify features <feature-arg>`
   (lock checks above). Then, for every **other** feature of step 2: run
   `ac_feature.py --feature <its tag>`; for each of its `sourcesLock` and `featuresLock` **that
   exists**, run `ac_lock.py verify <group> --feature <its tag>` (a group without a lock file is not
   verified: `verify` would report it as not locked). Exit 1 → stop and report (that feature's tests
   would run against changed AC or features); exit 3 → only warn the user (that feature's `spec.md`
   changed after its AC were locked) and go on.
4. Check that the current feature's latest `run-NNN` folder (in `runsDir`; not `translate-NNN`) has
   `writer-report.md`. If not: stop and point to `/speckit-ac-tests-write`.
5. Run `new_analyze.py <feature-arg>` and note the analyze folder (`<analyze>`). This is step 1 of
   starting the judge; continue with step 2 there only in step 9. From here on, **every stop before
   step 9 first runs `changed_files.py clear`**: it ends the run, so no judge can start later with this
   run's task message.
6. Build the AC project normally: `dotnet build <acProject> -nologo -v q` (`acProject` from the
   config; no `AcRefMode`; the AC project is not in the solution, so build it by path). If it does not
   compile: the public API probably changed after the reference assemblies were exported. Run
   `changed_files.py clear`, report only the number of errors and their codes and point to
   `/speckit-ac-tests-write`. Stop.
7. Run `acTestCommand` from the config with `{acProject}` and `{analyzeDir}` (= `<analyze>`) filled
   in. It writes `<analyze>/ac-results.trx`. A non-zero exit code only means that tests failed; go on.
   If `<analyze>/ac-results.trx` does not exist: run `changed_files.py clear`, then stop and report.
8. Run `summarize_trx.py <analyze>/ac-results.trx <analyze>/ac-results.md --current <tag>`, and add
   `--only-current` when the input contains `--current`. Note the counts it prints.
   If it fails because no test result exists (none at all, or none of the current feature): run
   `changed_files.py clear`, then stop and report it. No test ran, which is never a pass.
   If every result passed (pending counts as failed): run `changed_files.py clear`, report the totals
   and the AC ids skipped at translation (`skipped.json` in the current feature's latest
   `translate-NNN` folder, if any), then stop.
9. Start the judge (Rules, steps 2–5; step 1 ran in step 5).
10. Run `extract_feedback.py <analyze>/judge-report.md <analyze>/writer-feedback.md`.
11. Report to the user:
    - totals per scope (current feature / regression) from `ac-results.md`, and the AC ids skipped at
      translation;
    - the judge's Summary table from `judge-report.md`;
    - next actions grouped by verdict:
      - `TRANSLATION_FAULT` — the feature file does not match the reviewed acceptance criteria: ask
        for `ac_lock.py unlock features`, then `/speckit-ac-translate` and
        `/speckit-ac-tests-write` again;
      - `IMPLEMENTATION_FAULT` — ask me to fix the implementation, then run
        `/speckit-ac-tests-analyze` again;
      - `TEST_FAULT` — current feature (or its listed cross-feature changes): run
        `/speckit-ac-tests-write`; the judge's feedback goes to the writer. Another feature's
        test: run `/speckit-ac-tests-write <its tag>`;
      - `SPEC_AMBIGUITY` — decide the intended behaviour; changing `spec.md` or `acceptance.md`
        needs a review, an unlock and `/speckit-ac-translate` again;
      - `UNEXPRESSIBLE` — the public API needs a way to perform or observe this: ask me to change
        the implementation, then run `/speckit-ac-tests-write`;
      - `SUPERSEDED` — an earlier feature's acceptance criteria conflict with the current feature's
        spec: revise or retire that feature's AC (unlock its `sources`, edit, lock, then
        `/speckit-ac-translate <its tag>` and `/speckit-ac-tests-write <its tag>`);
      - `INCONCLUSIVE` — show the judge's reasoning.

## Report and stop

Stop after step 8 (all passed) or step 11 (or at the first failure). The user decides what comes
next. Never start another command yourself.
