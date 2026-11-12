# Plan review — round 1 (plan-critic)

Spec: `docs/steps/10-fixes-0.1.2.spec.md` · Plan: `.claude/plans/10-fixes-0.1.2.plan.md`

## Requirement coverage

| # | Requirement | Plan step | Status |
|---|---|---|---|
| 1 | R01 | 2 | covered |
| 2 | R02 | 2 | covered in code; the wiring into `main()` is not tested (MAJOR 1) |
| 3 | R03 | 5 | covered |
| 4 | R04 | 1, 3 | covered |
| 5 | R05 | 3 | covered |
| 6 | R06 | 3 | covered |
| 7 | R07 | 4 | partly: step 8 gets the sentence, but a conflicting line stays (MAJOR 2) |
| 8 | R08 | 5, 7 | covered; one evidence claim behind it is wrong (MINOR 2) |
| 9 | R09 | 6 | covered |
| 10 | R10 | 3, 6 | covered |
| 11 | A01–A07 | 7 | covered; A05 needs one detail (MINOR 3) |
| 12 | Constraints | 3, 4 | respected |

Verified against the repo:

- The code and test evidence is correct, apart from MINOR 2. A few line numbers are off by one to four lines.
- No test names `highest` or `version_key`.
- `test_commands.py:238` asserts `"cross-feature changes, missing packages"`.
- The template has no conditional `PackageReference` group, so Assumption 3 holds.
- `sys.exit(<text>)` gives exit code 1 through `aclib.run_main`.
- `init_scaffold` already imports `init_detect`.
- The planned command sentence passes the existing rendering and named-command checks.

## Findings

- **[MAJOR] 1.** Step 5 composes `code_only` and `LOGIC` inside the test, so the scan in `main()` is untested.
  Removing `code_only(...)` from `main()` would pass every test.
  - Fix: extract a pure `logic_lines(listing) -> list[str]` that returns the original stripped lines, and call it
    from `main()`.
  - Run the R03 table against it, and assert that a returned line keeps its literal.
  - Define the mutation as "remove `code_only` from `logic_lines`".
- **[MAJOR] 2.** Step 4 leaves `speckit.ac.tests-write.md:77` saying, without condition, "The next step is
  `/speckit-ac-tests-analyze`", which contradicts R07.
  - Fix: qualify that sentence ("unless step 8 named missing packages").
  - Keep "Never start it, or any other command, yourself." exactly (`test_commands.py:216`).
  - Test the qualifier.
- **[MINOR] 3.** The scanner checks quote count before the prefix, so `@"""a"" b"` is read as a raw string. A
  later `return` is then hidden.
  - Fix: a prefix with `@` means verbatim, whatever the quote count.
  - Add the must-match case `x = @"""a"" b"; return y;`.
- **[MINOR] 4.** The evidence claim "unit tests never reach `export_refs.py`" is wrong for
  `test_verify_reports_leftovers` (`test_init.py:568`).
  - That test lets the restore succeed and starts the real `export_refs.py` subprocess.
  - Traced: it asserts only on `[9]` and should still pass.
  - Fix: correct the claim and watch this test.
- **[MINOR] 5.** A05's `git worktree add` without `--detach` creates a branch in HT.
  - Fix: use `--detach`, then `remove --force` and `prune`.
  - Copy only `export_refs.py` and `init_detect.py`; `aclib` is unchanged.

## Verdict: REVISE

No blocker. Both MAJOR items are small edits to plan steps 4 and 5.
