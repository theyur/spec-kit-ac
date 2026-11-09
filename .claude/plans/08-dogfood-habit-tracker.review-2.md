# Plan review — round 2 (plan-critic)

Spec: `docs/steps/08-dogfood-habit-tracker.spec.md` · Plan: `.claude/plans/08-dogfood-habit-tracker.plan.md`

## Requirement coverage

| Req | Plan step(s) | Status |
|---|---|---|
| S08-R01 | 1, D1 | mapped; the test misses one of the three sentences (MINOR 2) |
| S08-R02 | 2 (full-path rule), 6, 6a.3 | mapped; the dirty-tree deviation isn't under "Deviations" (MINOR 3) |
| S08-R03 | 6a, Deviations | mapped; no reset path for a half-done init (MAJOR 1) |
| S08-R04 | 11 | mapped |
| S08-R05 | 11 | mapped |
| S08-R06 | 3 | mapped |
| S08-R07 | 6 | mapped; the expected path set is misdescribed (MINOR 4) |
| S08-R08 | 4 | mapped; the format matches ADR 0001 |
| S08-R09 | 8, A2, A3, A5, A6 | mapped |
| S08-R10 | 5, 9, A1, A4 | mapped |
| S08-R11 | 7 | mapped |
| S08-R12 | 10 | mapped |
| A01–A07 | 1, 2, 6, 8, 9, 10, 11 | mapped |
| A08 | 12 | pending by design |

## Fact checks

All held, with these notes:

- `payload_mismatch` is in `make_sample.py:87`, not in `e2elib` as the plan says (cosmetic).
- F15 was verified against a real step 7 `.meta.json`.
- A1 is stronger than the plan says. The guard's command starts with `uv`, so the gate's `$indirectCommands`
  rule for `python` never applies either.
- `upgrade` has no same-version refusal (`deploy.py:733-783`), and `register_guard` appends last.
- `propose()` filters surface candidates to `OutputType == library` (`init_detect.py:196`), so `HT.Ui` (an Exe)
  will not be proposed.
- HT's `block-pr-review.ps1` blocks only `pr-review`.

## Round 1 dispositions

All six are resolved in the plan text. Finding 2 (the fix loop) is resolved but incomplete; see MAJOR 1 below.

## Findings

1. **[MAJOR] No way back into setup mode after a half-finished init** (S08-R03, S08-R09; plan 6a).
   - A3 would fail at `init_verify.py`, which runs after init has already written its output.
   - A re-run of `/speckit-ac-init` then enters verify mode, because the config exists (`speckit.ac.init.md:34`).
     So a fix in `init_config.py` or `init_scaffold.py` would never be applied.
   - Deleting only the config isn't enough: `init_detect` blocks on a non-empty `acProjectDir`.
   - **Fix:** the plan must state two branches.
     - Fix in verify, export or guard code → `upgrade`, then re-run init, which runs verify again.
     - Fix in config or scaffold code → `upgrade`, reset init's output, and re-run init in setup mode.
2. **[MINOR] The new test checks two of the three sentences** (S08-R01; plan step 1). Add an assertion for "wait
   for the subagent's hand-back before any further step".
3. **[MINOR] HEAD-plus-diff install not filed as a deviation** (S08-R02, S08-R03; plan step 2). File it as D2.
4. **[MINOR] Step 6's expected path set is misdescribed** (S08-R07; plan step 6).
   - The manifest already lists the extension files and the skills.
   - It does not list `.claude/settings.json`, `CLAUDE.md`, `.workflow/deploy.json` itself,
     `.specify/extensions.yml` and `.registry`.
   - Write the expected set down exactly.

## Verdict: REVISE
