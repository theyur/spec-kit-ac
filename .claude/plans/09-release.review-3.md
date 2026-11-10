# Review round 3 — Step 9 plan (Release v0.1.0)

Reviewer: `plan-critic` (Fable, high effort), 2026-11-10. Saved by the main agent. The secret shape the
reviewer found in the spec is described in words, not spelled.

## Verdict: REVISE

0 BLOCKER, 2 MAJOR, 4 MINOR. Both MAJORs are text-level plan edits; the reviewer sees no need for a fourth round
once they are made.

- **Round-2 findings resolved in the plan text:** 1, 3, 4, 5, 6, 7, 8, 9, 10.
- **Round-2 #2:** resolved as written, but the new scan trips on the spec (finding 1).
- **Round-2 #11:** resolved, except the WIP gap on the "remove" loop (finding 2).
- **No requirement is unmapped.**

## Findings

1. **MAJOR (steps 16, 17).** The secret-shape gate can't pass on the release branch.
   - The first release commit adds the 09 spec. Its S09-R02 bullet names the password-assignment shape
     literally, in backticks, and the last secret pattern matches it. A working-tree run found exactly that one
     hit.
   - F11 couldn't see it: the dry run cloned committed content only.
   - The plan has no rule for a hit at step 16.

   Fix:
   - reword the spec bullet in step 5 so it describes the shape in words;
   - add a pre-commit pass in step 16 that runs both pattern files over the files to be committed;
   - keep "nothing" as the rule, with no allowlist;
   - saved reviews must not spell the shape either.
2. **MAJOR (only if the user answers "remove" at gate 3(b); steps 1, 3, 4, 16).** The WIP restore puts the F13
   paths back, and no scan would see them. `TRACKER.md` (row 8 holds the Habit Tracker checkout path) and the
   plan header (the scratchpad path) are restored unscrubbed, and `patterns.txt` has no F13 patterns.
   Fix: on that branch, add the F13 patterns to `patterns.txt`, scrub the restored WIP files before the step 4
   pytest run, and run the step 16 and 17 scans with the extended pattern file.
3. **MINOR (step 1 vs step 3).** The tree changes before the gate. Step 1 removes the WIP files from the tree,
   but the bundle holds commits only. F1's file list is also stale: reviews 2 and 3 are untracked too.
   Fix:
   - move the removal into step 4, after the OK;
   - compare the copy byte for byte before reverting;
   - only the modified tracked file needs to leave the tree (filter-branch refuses on tracked changes, not on
     untracked files).
4. **MINOR (steps 3, 4).** `dryrun.sh` doesn't do what step 3 says, and step 4 has no script. The script compares
   subjects only (`%s`), has no message scan and no path-limited heading grep, and prints unplanned files rather
   than the union. Fix: one verify script that takes the repository path, compares `%B`, and runs every step 4
   check; use it for any rerun and for the real rewrite.
5. **MINOR (steps 17, 19).** Row 9 says `done` before A07/A08, and the result record is optional. The `.dev0`
   follow-up has no tracker entry, and the changelog date can't be fixed if the merge and the tag fall on
   different days. Fix:
   - the row 9 "Verified" cell says A01–A06 verified, A07–A08 pending the tag;
   - an explicit ask at the end of step 19 for one follow-up PR (A07/A08 results, release URL, the dev bump if
     the rule was accepted, a date fix if needed);
   - record that PR as an open item before the merge.
6. **MINOR (step 13 vs S09-R10).** `sonar.yml`'s permissions are only checked for presence. Fix: assert the exact
   set (the Habit Tracker pattern: `contents: read`, `pull-requests: read`), with no `write` scope.

## Claims checked against the repo

- F4 and F5 hold.
- The scrub script matches step 2: each anchor matches once, it exits 1 on a leftover path, and the replacement
  has no heading.
- The repo-wide heading pattern includes the old title, so DESIGN's own §10 heading doesn't match.
- The dry-run map has 15 pairs, and its last new hash equals F11's.
- `.gitattributes` pins LF.
- The artifact names follow `uv_build`.
- The new files don't exist yet.
- The spec, the plan and reviews 1–2 contain neither the path nor the tokens.

Not checked (no shell): commit bodies, older trees, GitHub and Sonar state, the action versions.
