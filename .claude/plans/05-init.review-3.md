# Plan review — step 5, round 3 (plan-critic)

Verdict: **REVISE** (0 BLOCKER, 1 MAJOR, 5 MINOR). All round-2 findings resolved; no contradiction with S05-R01..R15, DESIGN or CLAUDE.md.

1. [MAJOR] `environment()` checks timestamp folders only; the `feature_numbering`/`branch_numbering` option in `.specify/init-options.json` is the authority (aclib `_feature_numbering`, guard `timestamp_numbering`). Fix: report it too; add the case to the env tests.
2. [MINOR] Implementation-folder refusal only in `init_config.py`, after the confirmation. Fix: `init_detect.py` prints `implementationFolders`; the command re-asks; `init_config.py` stays the hard gate.
3. [MINOR] `smoke_test.py start` refusal on a stale non-smoke marker gives no way out. Fix: the message names the marker, why it is there, and tells the user to delete it by hand.
4. [MINOR] Item 8: a missing TRX gives FAIL without a cause. Fix: print the test command's last lines (40) under the FAIL line.
5. [MINOR] netstandard-only surface (ask) not in the design or tests; scaffold may recompute a different TFM. Fix: `propose` returns `targetFramework: null` + reason; the command always passes `--target-framework`; netstandard-only fixture.
6. [MINOR] `export_refs.py` needs `dotnet tool restore` in a fresh clone. Fix: `init_verify.py` runs `dotnet tool restore` before item [4].
