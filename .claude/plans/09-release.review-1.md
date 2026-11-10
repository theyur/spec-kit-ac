# Review round 1 — Step 9 plan (Release v0.1.0)

Reviewer: `plan-critic` (Fable, high effort), 2026-11-10. Saved by the main agent. The original path and the
§10 tokens are not quoted.

## Verdict: REVISE

1 BLOCKER, 3 MAJOR, 11 MINOR. The design is sound overall. The problems are a missing approval gate, a leak the
plan itself creates, one spec deviation that becomes permanent after the first push, and the ordering of the
gates.

## Claims checked against the repo

- F2 holds. The §10 heading is at line 784. Header lines 6 and 9 read as the plan says.
- F3 holds at HEAD. The path is in 9 files plus the reference doc, always as backtick plus backslash. The only
  forward-slash hit is inside §10.
- F4, F5 and F6 hold.
- F7: setup-uv v10.3.3 is the latest release. The checkout and scan-action pages timed out, so those two were
  not checked.
- The coverage settings (`relative_files`, `source`, `sonar.python.coverage.reportPaths`) match Sonar's Python
  guidance.
- Habit Tracker runs ubuntu with the dotnet scanner. Only its skip, trigger and permission patterns transfer.
- No shell was available, so the commit count, the messages and the all-commit greps were not checked.

## Findings

1. **BLOCKER (step 3).** The rewrite has no "ask the user" gate. Spec decision 3 requires an OK at that moment.
   Fix: show the dry-run result (hash map, diff stat, grep and scan results), ask, and run on the real repo only
   after the OK.
2. **MAJOR (steps 4, 11).** The plan file publishes what Phase A removes. The step 4 grep spells the path as a
   thin regex and lists three §10 tokens, and step 11 commits the plan. A01 then can't be repeated, because the
   pattern matches the plan itself. There is also no scan of the release-branch commits before their push.
   Fix: keep the patterns in `<sp>/s9/patterns.txt` and use `git grep -f`. Describe them in words in the plan.
   Before the push in step 12, scan `master..release/v0.1.0` and the working tree. Tell critics not to quote them.
3. **MAJOR (steps 2, 4).** A §10 heading stays, and the check is narrowed so it misses it. Decision 1 says
   "one line", and R02/A01 say "no §10 heading". Fix: write the line without a heading, and check that
   `^## 10\.` finds nothing in any commit.
4. **MAJOR (steps 6, 12, 13, 15).** The gates are switched on after the PR is opened. CodeQL default setup
   doesn't analyze an existing PR head. Without `SONAR_TOKEN` the Sonar job skips green, so
   `SonarCloud Code Analysis` never reports. The PR analysis needs a baseline analysis of `master`.
   Fix: reorder:
   1. after step 6, the user makes the repo public;
   2. enable CodeQL;
   3. the user imports into SonarQube Cloud and waits for the first automatic analysis;
   4. the user turns Automatic Analysis off and adds the token.

   Preflight before opening the PR: visibility, the secret name, and the default-setup state. Expect only
   `python` in the CodeQL languages until the workflows reach `master`.
5. **MINOR (step 4).** The verification is weaker than R02 needs. It diffs HEAD to HEAD only, proves the §10
   removal with sample tokens only, and miscounts the files (9 vs 10 vs 11). Fix:
   - diff `--name-only` for each of the 15 old/new pairs, as a subset of an explicit list;
   - check that the reference doc is one blob across all commits, and inspect it once;
   - check that the real new HEAD equals the dry run's;
   - use one file list.
6. **MINOR (step 4).** A02 on the rewritten HEAD needs both Pythons. Fix: run 3.14 and 3.11 in step 4.
7. **MINOR (step 16).** The tag push is the real publish, and nothing is checked right before it. Fix:
   - run `release_check.py check` on the merge commit, and confirm `master` CI is green for that SHA;
   - say what happens when the release run fails after the tag is public: never move the tag; the user chooses
     a re-run or `v0.1.1`.
8. **MINOR (step 10).** `release.yml` doesn't state a Python version or the cache. Fix: pin `python-version`
   and set `enable-cache: false`.
9. **MINOR (step 9).** The text checks can pass on the wrong text: a comment line satisfies a substring, and
   only part of the order is checked. Fix:
   - strip comments;
   - assert the full release order: check, pytest, build, notes, release;
   - assert no `continue-on-error` and no `if:` in `release.yml`;
   - assert the `sonar.yml` triggers and the `ci.yml` concurrency.
10. **MINOR (step 9, R10).** The README and changelog tests break on the next dev version. Fix: decide the rule
    now.
11. **MINOR (step 10).** `actions/setup-dotnet` is not in R06, and `init_verify.py` in step 17 goes beyond R14.
    Fix: record both as deviations, or drop setup-dotnet and state the runner's SDK after the first run.
12. **MINOR (steps 9, 10).** The Sonar organization and key live in two places, and the `-D` defaults always
    win. Fix: keep the defaults in the properties file, and pass `-D` only when the variable is set.
13. **MINOR (step 12).** The coverage path mapping is first tried in CI. Fix: run the coverage commands
    locally, check that the `filename`/`<source>` pairs resolve, and git-ignore `.coverage` and `coverage.xml`.
14. **MINOR (steps 5, 11).** Stale §10 pointers stay at HEAD (`CLAUDE.md` line 10, `docs/DESIGN.md` lines
    26–27). Fix: reword them in the release branch.
15. **MINOR (steps 3, 11, 14, 18).** Loose ends:
    - no step asks the user to release the bundle and `refs/original`;
    - remap the two hashes right after step 3;
    - no step creates the branch;
    - step 14's "as in step 8" means step 8 of the tracker;
    - the tracker row is left as "implementing" inside `v0.1.0`;
    - the plan and spec cite pre-rewrite hashes;
    - a fork PR gets no `SONAR_TOKEN`, so it can never pass Sonar; the README should say so.

Not a finding, for the user to decide before the first push: other local absolute paths (the Habit Tracker
checkout, paths under the user profile, the scratchpad) appear in about 14 tracked files. The rewrite covers
only the original project.

Sources: setup-uv releases; SonarQube Cloud Python test coverage; SonarQube Cloud pull request analysis; Sonar
community thread "A regular analysis is required before analyzing a pull request".
