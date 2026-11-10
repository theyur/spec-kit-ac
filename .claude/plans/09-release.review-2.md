# Review round 2 — Step 9 plan (Release v0.1.0)

Reviewer: `plan-critic` (Fable, high effort), 2026-11-10. Saved by the main agent, without the reviewer's list of
absolute file paths.

## Verdict: REVISE

0 BLOCKER, 5 MAJOR, 6 MINOR.

- **Resolved in the plan text:** round-1 findings 1, 4, 6, 8, 9, 11, 12, 13, 14 and 15.
- **Partly resolved:** 2, 3, 5, 7 and 10.
- **Sound:** the ruleset timing and the release step order.
- **Verified in the repo:** the path is in 10 files at HEAD (the reference doc plus 9); F4 and F5 hold; the plan
  and review 1 contain no path; setup-uv `v10.3.3` is the latest and immutable; the commit subjects contain no
  path.
- **Not checked:** commit bodies and older trees (the reviewer had no shell).

## Findings

1. **MAJOR (steps 2, 4, 16).** The heading pattern can't pass: `docs/DESIGN.md:185` is DESIGN's own `## 10.`
   heading. Fix: run the heading regex with a pathspec for the reference doc only, keep the path and token
   patterns repo-wide, and state both commands.
2. **MAJOR (steps 16, 17).** The release-branch leak scan can pass on nothing. `master..release/v0.1.0` is
   empty before the commit, and `git grep` skips untracked files. Later pushes are never scanned. Fix: commit
   after the OK, scan each commit in `origin/master..HEAD`, then push. Repeat before every later push. Don't use
   `--no-index`, which would hit `CLAUDE.local.md`.
3. **MAJOR (step 17).** Fix commits and pushes happen without the user's OK. Fix: ask before each push, or get
   a recorded standing OK for follow-up commits on this PR.
4. **MAJOR (steps 12, 13, 15).** The version rule (`.dev0` after a release, `[Unreleased]`) is a new decision
   the user never saw. It changes R10 (package version → `latest`), and no step performs the bump. Fix: put it
   to the user before step 12. If accepted, record it as a deviation and name the follow-up PR. If declined, keep
   R10 as written.
5. **MAJOR (steps 3, 4).** Commit messages are never scanned. Fix: grep `git log --format=%B` with both pattern
   files (counts only), and show the result at the gate.
6. **MINOR (step 4).** The "11 files" explanation is a guess. Fix: print the union of changed files over the 15
   pairs at the gate, and show the user the spec correction.
7. **MINOR (steps 16, 18).** The pre-tag rehearsal covers only `check`. Fix:
   - test `notes` on the real changelog;
   - run `notes` and `uv build` on the merge commit;
   - name which runs gate the tag, and say what a red Sonar run on `master` means.
8. **MINOR (step 10).** The preflight doesn't check A5. Fix: add the baseline analysis and "Automatic Analysis
   off", confirmed by the user.
9. **MINOR (steps 9, 18).** The `actions` language re-read has no step. Fix: read the languages in step 18
   before the tag ask, and report them.
10. **MINOR (steps 13, 14).** Spec deviations aren't recorded as such: setup-uv's full-version pin vs R06's
    "major", `sonar.sources=src,tools` vs decision 5's `src/`, and R10. Fix: add a deviations list and carry it
    into the tracker.
11. **MINOR (steps 3, 19).** Two open branches. If the user wants the F13 paths removed, steps 2–3 must run
    again. The Habit Tracker baseline isn't captured before the upgrade. Fix: state the loop, and capture HT's
    branch and `git status` first.
