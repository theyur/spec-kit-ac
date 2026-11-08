# Plan review — round 3 (plan-critic), step 7

Round 2 dispositions: all seven verified as applied (incl. `deploy.upgrade` at `deploy.py:733`,
`new_run.py:34-37`, `aclib.may_change` at `aclib.py:326-337`, F8 and F14 still hold).

## Findings

1. **[MAJOR]** Step 6.6 / A6: comparing every payload file with the installed copy fails on every run —
   `specify extension add` does not copy `.extensionignore` (`tests/test_deploy_real.py:67`,
   `tests/fakespecify.py:135`). Fix: expected set = payload minus `.extensionignore` and its patterns; test
   the skip.
2. **[MAJOR]** Steps 1 / 8: `.claude/settings.local.json` (written by Claude Code on "don't ask again") is not
   ignored in the sample; it dirties the tree (stage.py refuses) and `written` reports a false breach. Fix: add
   it to the sample's `.gitignore`; mention it in the runbook.
3. **[MINOR]** Step 8 `written`: the Scope check passes vacuously with no `.cs` under `StepDefinitions/F<NNN>/`.
   FAIL then; add the FAIL case to the tests.

## Verdict: REVISE (no BLOCKER)
