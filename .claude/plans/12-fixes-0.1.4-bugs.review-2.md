# Review of plan 12 (fixes for 0.1.4), round 2

Verdict: **REVISE**. 0 BLOCKER, 1 MAJOR, 8 MINOR.

The plan-critic read the code and ran nothing.

All twelve round-1 dispositions are reflected in the plan steps. Every evidence line it checked is correct. Each
step-18 mutation is caught by a planned test:

| Mutation | Caught by |
|---|---|
| TRX line dropped | the step 2 tests and the step 6 old-block test |
| `upgrade` skips the blocks | the step 6 refresh test |
| `write_block` always rewrites | the second-upgrade print check |
| doctor treats an old block as `ok` | the `["x"]` doctor case |
| no `IGNORECASE` | row 2 and the fixture |
| `\` only | row 2 and the fixture |
| scrub before the frame filter | the fixture run from another folder |
| first-whitespace end | the `Anna Maria Rossi` row |
| `self.refs` back | the guard deny cases |

Rows 1–19 trace correctly through step 8. The one exception is row 12, below.

## Findings

- **[MAJOR 1] Spec and plan disagree on the UNC start.**
  - The spec says `\name\` and its row is `\server\share\x.cs`, both with one backslash (`spec.md:141, 178`).
    The plan needs `\\`.
  - Read literally, the spec would match any relative Windows path.
  - With `\\`, JSON- or regex-escaped text (`"^\\d+\\.\\d+$"`) would count as a UNC path.
- **[MINOR 1]** Row 2 does not say that only the root part changes case. The text after the root keeps its case.
- **[MINOR 2]** The pass-1 lookahead `.,;:)` is wider than R05. `cwd is R.` gives `cwd is ..`, and no row covers
  it.
- **[MINOR 3]** A root form ending in a separator (`X:\`, a `subst` drive at its root) never matches in pass 1.
  No test passes two root forms.
- **[MINOR 4]** The step 7 round-trip fails: an empty `.workflow/` is left after the config is deleted
  (`deploy.py:773–774`, `fakespecify.py:52–55`).
- **[MINOR 5]** The judge sentence "not the test's input" can be false. A step argument path is the input.
- **[MINOR 6]** The changelog limit note misses these leak forms:
  - `HOME is C:\Users\First Last`;
  - a file name with a space after the last separator;
  - mixed separators;
  - an unclosed quote;
  - `dirC:\…`;
  - a sibling folder `repo 2`.
- **[MINOR 7]** The fixture tests the profile path only in quoted form.
- **[MINOR 8]** `upgrade` now refuses a non-UTF-8 `.gitignore`. The changelog does not say so.
