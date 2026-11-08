# Plan review — round 1 (plan-critic), step 7

Spec: `docs/steps/07-e2e-sample.spec.md` · Plan: `.claude/plans/07-e2e-sample.plan.md`

## Requirement coverage

| Req | Plan step(s) | Status |
|---|---|---|
| R01 | 1 | covered, with an unrecorded deviation (base unit tests) |
| R02 | 2 | covered |
| R03 | 3 | covered (fixture tests add a negative case; harmless) |
| R04 | 6 | covered; adds `--cli tool|checkout` (needed by R08) |
| R05 | 7 | covered; adds a fourth action `commit <label>` |
| R06 | 8 | covered; `smoke` has a wrong check (BLOCKER); `written` uses git-since-HEAD instead of the non-existent saved `changed_files.py` output (F7 verified: `changed_files.py:54-74`) |
| R07 | 10 | covered; two runbook omissions |
| R08 | 9 (opt-in) | covered; missing an AC-project build before `acTestCommand` |
| R09 | 9 (non-opt-in) | covered |
| R10–R12 | 11, 12 | covered |

F2, F4, F5, F6, F7, F8 verified against source; F4 true but incomplete.

## Findings

1. **[BLOCKER]** Step 8 `smoke`: "a `main\tRead\tdeny` line exists" can never pass — the guard logs only when
   `agent_type` is non-empty (`guard.py:417-428`). Fix: drop it; record the main-agent block as a manual
   observation; keep the `Explore\tRead\tdeny` WARN.
2. **[MAJOR]** Step 10 item 7 puts `e2e-notes.md` inside the sample; `stage.py` refuses a dirty tree and
   `written` counts every changed file. Fix: keep notes outside the sample, or exclude the file.
3. **[MINOR]** Step 9 (opt-in): `acTestCommand` has `--no-build` (`init_config.py:103`); build the AC project
   first, after each `stage implement` too.
4. **[MINOR]** Step 8 `analyze`: the judge's first cell format is not fixed (`ac-test-fail-judge.md:106`);
   extract `F\d{3}` and `AC-\d{3}` tolerantly, FAIL with the raw row when missing; test it.
5. **[MINOR]** Step 10 stage 5: tests-analyze for 002 must run without `--current` (else the judge sees no
   F001 failures). State it in the runbook and the FAIL hint.
6. **[MINOR]** Step 10 stage 3, missing-interpreter check: needs a new session after the edit and another
   after the restore (`speckit.ac.init.md:109-112`).
7. **[MINOR]** Step 1 deviates from R01 (base unit test only constructs; `Total` throws) — right, but record
   it as a deviation.
8. **[MINOR]** Step 7's `commit <label>` action (variable message) is beyond R05's three actions — record it
   as a deviation; clean tree → message, exit 0.
9. **[MINOR]** Step 6.1: an existing empty `<dir>` goes to `specify init <dir>`, which may refuse an existing
   folder. Remove an empty dir first, or probe.
10. **[MINOR]** Step 5 `commit()`: also pass `-c commit.gpgsign=false`.

## Verdict: REVISE
