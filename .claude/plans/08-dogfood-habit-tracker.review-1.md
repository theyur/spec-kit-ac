# Plan review — round 1 (plan-critic)

Spec: `docs/steps/08-dogfood-habit-tracker.spec.md` · Plan: `.claude/plans/08-dogfood-habit-tracker.plan.md`

## Requirement coverage

| Req | Plan step(s) | Status |
|---|---|---|
| S08-R01 | 1 | mapped; wording deviates for critic/init (MINOR) |
| S08-R02 | 2 (implicitly 6) | mapped; step 6 does not say "by full path" (MINOR) |
| S08-R03 | 6, A3, Deviations | mapped, but no re-deploy path to HT after a fix (MAJOR) |
| S08-R04 | 11 | mapped |
| S08-R05 | 11 | mapped |
| S08-R06 | 3 | mapped (adds a self-test baseline; harmless) |
| S08-R07 | 6 | mapped |
| S08-R08 | 4 | mapped; the ADR is written before init, as required |
| S08-R09 | 8 | mapped; the session-location risk is not handled (MAJOR) |
| S08-R10 | 5, 9 | mapped |
| S08-R11 | 7 | mapped |
| S08-R12 | 10 | mapped; no doctor / settings re-check after the smoke test (MAJOR) |
| A01–A07 | 1, 2, 6, 8, 9, 10, 11 | mapped |
| A08 | 12 | pending by design |

**Fact checks.** All of the plan's facts held against the repository. A1 is effectively confirmed:
`architecture-gate.ps1` exits 0 for any command that doesn't mention `git` or `commit`. A6 holds:
`init_config.implementation_folders` returns `src` plus the folders that hold a `.csproj`.

## Findings

1. **[MAJOR] Session location** (S08-R09 / S08-R10; plan steps 8–9, A5).
   - HT's `.claude/worktrees/` holds five desktop-app worktrees, so the user's sessions often start in a worktree.
   - The installed files exist only in the main checkout, uncommitted. In a worktree session the scripts aren't
     there, and anything init writes lands in the wrong tree.
   - A5's validation, "HT CLAUDE.md", validates nothing.
   - **Fix:** the runbooks must tell the user to open the session on the main checkout, not a worktree. The step 8
     check must confirm from the transcript that `cwd` is `<habit-tracker>`.
2. **[MAJOR] No way to get a fix into HT after install** (S08-R03 / S08-R07; plan step 6, A3).
   - Step 7 could rebuild its sample with `make_sample.py --force`; HT can't be rebuilt.
   - **Fix:** add an explicit loop: fix → `uv tool install --reinstall` → `speckit-ac upgrade` in HT (uninstall /
     install if init hasn't run) → `doctor` → the user re-runs init or smoke.
   - Without it, HT dogfoods a stale payload, and the results file can't say which code was exercised.
3. **[MAJOR] The hand restore after manual check 3 is never checked** (S08-A02 / S08-R12; plan steps 9–10).
   - Smoke manual check 3 has the user edit the guard command in `.claude/settings.json` by hand and restore it.
   - Step 10 checks only which paths `git status` lists, not their content. A restore that drops the
     `$CLAUDE_PROJECT_DIR` quoting, the `onFailure` key or the CRLF style would pass and land in the PR.
   - **Fix:** in step 10, re-run `speckit-ac doctor` and compare `settings.json` with the post-install snapshot.
4. **[MINOR] Wording deviation not recorded** (S08-R01; plan step 1).
   - The spec's third bullet says "never run `changed_files.py check` before then" for all five commands. The plan
     uses `smoke_test.py end` for init and "step 2" for the critic.
   - That's sensible, but it deviates from the approved text, and the Deviations section still says "(none yet)".
     Record it.
5. **[MINOR] Full-path rule missing for the other CLI calls** (S08-R02; plan step 6).
   - Step 2 runs `--version` by the full `uv tool dir --bin` path, but step 6 just says "run the tool's
     `speckit-ac install`". The step 7 trap applies here too: under `uv run`, the checkout's
     `.venv\Scripts\speckit-ac.EXE` comes first on PATH.
   - **Fix:** state the full-path rule for every CLI call in HT.
   - Also record in the results which commit the tool was built from, and that the tree was dirty. The step 1
     edits are uncommitted, so "at the current HEAD" isn't literally what gets installed.
6. **[MINOR] Same evidence source as step 7** (S08-R10; plan step 9).
   - For "does the `Agent` description reach the subagent", the plan repeats step 7's method, which came out
     "not observed" (`07-e2e-sample.results.md:38`).
   - **Fix:** name a different evidence source (the subagent's own transcript file), or state up front that the
     expected answer is again "not observed".

## Verdict: REVISE
