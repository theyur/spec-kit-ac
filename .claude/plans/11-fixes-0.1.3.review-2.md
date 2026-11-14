# Plan review 2 — step 11 (plan-critic)

**Verdict: APPROVE** (0 BLOCKER, 0 MAJOR, 3 MINOR)

All eight accepted round-1 findings are resolved in the plan steps; the F8 decline holds (`n` picked as the next
free number at `speckit.ac.critic.md:60–63`, report read by that `n` at `:79`, one critic at a time at `:255`).
F4's known limit confirmed in specify 1.0.2 (`specify_cli/extensions/__init__.py:1689`, which also copies
`argument-hint` itself at `:1696`). F5's `ValueError` exits non-zero through `aclib.run_main` (`aclib.py:45–50`).
spec-kit renders frontmatter with `width=inf` (`specify_cli/agents.py:164`), so a hint is always one line.

## Findings

1. **[MINOR] Step 5's file-name rule is not exact; step 7 pins only `../x.md`.** On Windows `C:x.md` (no
   separator, no `..`) makes `root / EXT / "commands" / name` read another drive; `name.md:stream` is similar.
   Same function family as the Sonar S2083 finding on the 0.1.0 PR (`TRACKER.md:242–245`), a required gate.
2. **[MINOR] Doctor's CRLF fold of the hint is pinned only by the opt-in real test.** `test_doctor_folds_crlf`
   (`test_deploy.py:551–559`) asserts only the exit code, a warn never changes it (`deploy.py:959`), and CI has no
   `specify` (`.github/workflows/ci.yml:2`). A slip gives five false warnings on every `autocrlf=true` checkout.
3. **[MINOR] `docs/CONFIG.md:146` and `docs/WORKFLOW.md:283–290` still describe the skill patch and the doctor
   check as flag-only.** Plan step 10 does not edit them (R11 does not list them either).
