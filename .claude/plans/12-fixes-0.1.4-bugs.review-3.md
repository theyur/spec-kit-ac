# Review of plan 12 (fixes for 0.1.4), round 3 (final)

Verdict: **APPROVE**. 0 BLOCKER, 0 MAJOR, 7 MINOR.

The plan-critic read the code and ran nothing. It traced all 29 prototype rows by hand.

All nine round-2 dispositions are applied in the spec and the plan. The step 8 `START` regex is the prototype's,
and the pass-1 and pass-2 rules match R05. Every R07 row, the new rows included, gives its expected output.

Note for the implementer: with `cwd` elsewhere, the fixture test must pass absolute TRX and output paths
(`summarize_trx.py:118, 202`).

## Findings

- **[MINOR 1] Pass 1 skips a root inside an earlier root's run.**
  - The leaks:
    - `/home/u/repo/a.cs,/home/u/repo/b.cs` (POSIX) gives `a.cs,/home/u/repo/b.cs`;
    - a UNC root joined the same way leaks too.
  - A drive root is caught by pass 2.
- **[MINOR 2]** No test covers the `X:/` branch of pass 2.
- **[MINOR 3]** The plan does not say whether pass 2 runs with `windows=False`.
- **[MINOR 4]** The limit note misses two forms that the stricter UNC start lets through:
  - a JSON-escaped UNC path (`\\\\server\\share`);
  - a long-path UNC path (`\\?\UNC\…`).
- **[MINOR 5]** No row covers a folder with a space below the root (mixed separators after the space), or
  `cwd is R\` (it gives an empty string, not `.`).
- **[MINOR 6]** Spec A03 still names the removed "space-continuation" rule.
- **[MINOR 7]** The approval of the round-2 spec edits is not recorded. The plan header says "Revision 2". The
  bullets in step 8 are misplaced, and the cited prototype is not durable.
