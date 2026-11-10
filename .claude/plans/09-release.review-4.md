# Review round 4 — Step 9 plan (Release v0.1.0)

Reviewer: `plan-critic` (Fable, high effort), 2026-11-10, requested by the user after round 3. Saved by the main
agent.

## Verdict: APPROVE

0 BLOCKER, 0 MAJOR, 4 MINOR. All six round-3 findings are resolved in the plan text, and the revision introduced no
new BLOCKER or MAJOR. The MINORs are optional text or script edits and need no fifth round.

- **Coverage:** no requirement is unmapped.
- **Re-checked:** the action tags (F7; D1 is justified); the patterns hit exactly the 10 planned files at the
  pre-rewrite HEAD; the dry-run union and map match F11; the pattern files are LF; `scrub.py` matches step 2; no
  test reads the README, the changelog or `tools/`.
- **Working-tree scan:** both pattern files give zero hits over the spec, the plan, reviews 1–3 and the tracker.
- **Not checked (no shell):** older trees and messages, GitHub and Sonar state, the local coverage run.

## Findings

1. **MINOR (steps 1, 3, 4).** `verify.sh` takes three arguments (repo, old metadata, old revs), and its inputs
   come from the dry-run clone, not from the real repository. Fix: write both files from the real repository in
   step 1, and state the three-argument call.
2. **MINOR (steps 3, 4, 16, 17).** The scans pass when grep itself fails (exit status above 1), and there is no
   positive control. The risk is new hand-written patterns on the "remove" branch. Fix: treat a grep exit status
   above 1 as a failure, and require each pattern to hit the old HEAD.
3. **MINOR (step 4, "remove" branch only).** `scrub.py` walks the whole directory and would fail on the rewritten
   tree. Fix: run it inside `<sp>/s9/wip/` and copy the results back. List the "remove" outcome as a conditional
   deviation.
4. **MINOR (step 19).** Expiring the reflog and running `git gc` can drop stash entries and other unreachable
   work. Fix: show `git stash list` and `git for-each-ref` first, run the cleanup only when they are as expected,
   and name the exact commands.
