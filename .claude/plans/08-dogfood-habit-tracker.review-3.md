# Plan review — round 3, final (plan-critic)

Spec: `docs/steps/08-dogfood-habit-tracker.spec.md` · Plan: `.claude/plans/08-dogfood-habit-tracker.plan.md`

## Requirement coverage

All of S08-R01–R12 and A01–A07 are mapped; A08 is pending by design. S08-R07: the expected path set contradicts
the step order (MAJOR).

## Fact checks

All held: F9, F10, F12, F14, F16/A1; the deploy manifest kinds; init's outputs; the `xunit2`/`vstest` recipe.

- **`HT.UnitTests`:** it is proposed as a test project, because its packages name a framework.
- **Leftovers:** `init_verify` lists files with `git ls-files --exclude-standard`, so git-ignored `.idea/` and
  `.claude/worktrees/` can't cause a false "leftovers" FAIL.
- **Extension files:** HT's `.specify/.gitignore` doesn't hide the extension files, so they will be committed.

## Earlier findings

Every finding from rounds 1 and 2 is resolved and was verified against the repository.

## Findings

1. **[MAJOR] Step 6's exact path set contradicts the step order** (S08-R07, S08-R03; plan steps 4, 6, 6a.4).
   - Step 4 writes the ADR before step 6 runs `install`, so the ADR is an extra path in step 6's
     "exactly these paths" check.
   - 6a.4 has the same gap, plus `sonar.yml` after step 7.
   - **Fix:** add these paths to the expected sets, or move the ADR step after install. The spec only requires the
     ADR to exist before init.
2. **[MINOR] Step 5 is redundant** (steps 5, F16, A1). F16 already reads the gate's exit-0 rule from the code. Fold
   step 5 into step 3 or drop it.
3. **[MINOR] Step 4's Consequences go beyond S08-R08.**
   - "Sonar excludes the AC project" and the writer's "Missing packages" report are not part of decisions 2–5.
   - Both are consistent with the spec, so this finding may be declined. If they stay, keep the packages sentence
     tool-neutral.
4. **[MINOR] Step 8 calls the `init_verify.py` re-run "read-only checks".**
   - It is not read-only: it writes a temporary feature (`specs/999-speckit-ac-check/`, and `F999` folders in the
     AC project and `.workflow/init-check/`), then removes it.
   - **Fix:** call it "self-cleaning", so a leftover from an interrupted run is recognised as the script's.

## Verdict: REVISE
