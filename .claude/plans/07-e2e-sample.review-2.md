# Plan review — round 2 (plan-critic), step 7

Round 1 dispositions: all ten verified as applied. Facts F2–F8, F13, F14 verified against source.

## Findings

1. **[MAJOR]** Step 9 (opt-in, R08): init's scripts and the reference copies dirty the tree, and every
   `stage.py` action but `commit` refuses a dirty tree, so the sequence cannot run. Fix: commit after the init
   scripts, after each reference copy and after each AC run (or call `e2elib.commit()`); say so in step 9.
2. **[MAJOR]** Steps 10/12 (R10): no procedure for getting a package fix into the live sample (installed uv
   tool, deployed copies). Fix: a "redeploy a fix" runbook section — reinstall the tool, `speckit-ac upgrade`,
   `stage.py commit upgrade`, a new Claude Code session, re-run the stage and its check.
3. **[MINOR]** Step 8 `written`: allowlist omits `run-NNN/input-feedback.md` (`new_run.py:34-37`), which a
   tests-write re-run after an analyze creates. Add it.
4. **[MINOR]** Step 10 stage 3: restoring `settings.json` by hand may leave it not byte-identical (dirty tree,
   doctor registration FAIL, `deploy.py:889-891`). Restore with `git checkout -- .claude/settings.json`; `git
   status` clean before stage 4.
5. **[MINOR]** A6's validation is wrong: doctor compares with the manifest the same tool wrote
   (`deploy.py:836-851`). Drop it, or have `make_sample` compare the payload files with the installed copy.
6. **[MINOR]** Step 3: the fixtures' negative unit test is beyond "50.00 and 200.00 only" (R01) — drop it or
   record a deviation.
7. **[MINOR]** Step 9: build + unit tests must run and be asserted after every `stage implement`, not only
   001-buggy.

## Verdict: REVISE
