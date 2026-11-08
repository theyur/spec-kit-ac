# Plan review — round 4 (plan-critic, requested by the user), step 7

Round 3 dispositions verified as applied (plan text and `tests/e2e/sample/.gitignore:5`). Facts re-verified,
incl. `deploy.upgrade` (no same-version refusal, `deploy.py:733-783`) and `specify init` without `git init`.
Steps 1–5 files checked against the plan (fixtures, reference AC-005 fails under 002 as planned).

## Findings

1. **[MINOR]** Step 8 `smoke`: check that `<acProjectDir>/StepDefinitions/smoke-test.txt` is gone
   (`smoke_test.py:24,149-153`); add to step 9.
2. **[MINOR]** Step 8 `analyze pass`: `skipped` counts as passed; R06 says every result passed. Require
   `passed` for every row; parser test with a skipped row.
3. **[MINOR]** Step 8 `analyze`: a non-passed `ac-results.md` row without an `AC-` tag → FAIL with the raw row.
4. **[MINOR]** Unrecorded deviations: 002 spec has FR-001 and FR-002 (R02 lists one); `check_stage analyze`
   takes `<expectation> <NNN>` (R06: `<expectation>`). Record as D3/D4.
5. **[MINOR]** Dispositions not reflected in the steps: round 3 #1 test of the `.extensionignore` skip, #2
   runbook mention of `settings.local.json`, #3 test for "no `.cs`" FAIL. Add to steps 9 and 10.
6. **[MINOR]** Step 5 `python_cmd(project)` missing from `e2elib.py`.

## Verdict: APPROVE
