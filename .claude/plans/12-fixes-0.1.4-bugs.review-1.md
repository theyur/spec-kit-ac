# Review of plan 12 (fixes for 0.1.4), round 1

Verdict: **REVISE**. 1 BLOCKER, 4 MAJOR, 7 MINOR.

The plan-critic read the code and ran nothing.

## Requirement coverage

| Req | Plan step | Status |
|---|---|---|
| R01 | 1 | covered |
| R02 | 4 | covered; failure modes in MAJOR 3 |
| R03 | 3, 5 | covered; broken block and bad bytes undefined (MAJOR 3) |
| R04 | 2, 6, 7 | covered; step 2 names a test that does not exist (MINOR 1) |
| R05 | 8 | covered as written; leaks and corruption in MAJOR 1, 2, 4 |
| R06 | 8, 9 | covered |
| R07 | 10 | partial (MINOR 3, 4) |
| R08 | 11 | covered |
| R09 | 12 | covered |
| R10 | 13 | covered. The main-agent write case reuses the listing path (`test_guard.py:294`), not the DLL path |
| R11 | 14 | covered |
| R12 | 15, 19 | covered |
| A02, A04 | 18 | covered |
| A03 | 18 | not met for one mutation (BLOCKER 1) |
| A05 | 10, 17 | partial (MINOR 4) |

## Findings

- **[BLOCKER 1] The mutation "scrub inside `clean_stack` before `in_ac_project`" is not caught.**
  - `run_script` runs with `cwd=project` (`acproject.py:94`).
  - `in_ac_project` calls `Path(file).resolve()` (`summarize_trx.py:87`), so a relative path resolves against
    the root and the frame is still kept.
  - The e2e run also runs from the project folder (`test_e2e_sample.py:39–40`).
  - A test must run from another cwd, or test `clean_stack` in-process.
- **[MAJOR 1] The space-continuation rule leaks paths.**
  - Two paths separated by one space: `R\a.txt C:\Users\u\b.txt` joins into one path below the root, and the
    output is `a.txt C:/Users/u/b.txt`.
  - A folder name with a word that has no `\` (`Anna Maria Rossi`, `OneDrive - Contoso`) stops the path at the
    first space, and the tail leaks.
  - If the root itself has such a folder, every unquoted path below it leaks its tail.
  - The cause is in S12-R05, so a spec decision is needed.
- **[MAJOR 2] `Path(p).resolve()` on every candidate.**
  - On Windows (CI and the dev machine) the `windows=True` rows are native, so resolve runs on them.
  - A UNC path makes a network lookup.
  - `resolve()` can raise `OSError`. Neither `in_ac_project` nor `run_main` catches it, so the summary crashes.
  - "The remainder is taken from the original text" has no meaning when the match came from the resolved form.
  - Nothing tests the resolved branch.
  - Resolve can mask the case-sensitive-compare mutation.
- **[MAJOR 3] `upgrade` adds a failure while the guard is unregistered, and `doctor` changes behaviour on bad
  input.**
  - `write_block` decodes strict UTF-8, so a legacy code page gives `UnicodeDecodeError` (a `ValueError`).
    That is not caught by `deploy.py:822`. The result is a traceback, and the guard stays unregistered.
  - A broken block raises `AcError` after the extension has been replaced. The message does not name the file.
  - Neither case is pre-checked in "upgrade stopped before any change" (`deploy.py:789–800`).
  - `doctor` decodes with `replace` today. With `block_lines` it would give `[FAIL] config: …` without the file
    name and would skip the second file.
- **[MAJOR 4] The POSIX root list changes routes the judge needs.**
  - `GET /Users/42`, `/home/index`.
  - The case rule under `windows=True` is undefined.
  - A native Windows TRX holds no local POSIX paths, so the list adds risk and little gain.
- **[MINOR 1]** Step 2 edits a `gitignore_lines` test that does not exist. The block tests in
  `test_init.py:451–484` use literal lines, so a new test is needed.
- **[MINOR 2]** The doctor exit line is `deploy.py:1004`, not `:1020`. `init_scaffold` runs `sys.path.insert` at
  import (harmless).
- **[MINOR 3]** The fixture frame is "upper-cased", but step 8 keeps the original case of the remainder, so the
  expected relative frame cannot match.
- **[MINOR 4]** Two gaps in the tests:
  - R07 wants both modes where allowed, and the plan runs one mode per row (the route, URL and key rows need
    both);
  - the e2e check asserts only that the project path is absent, not that no absolute path remains.
- **[MINOR 5]** The changelog limit note is wrong.
  - Listed but not real limits:
    - `file:///C:/…` matches;
    - `C:\\Users` matches.
  - Real limits that are missing:
    - an apostrophe in a quoted path (`O'Brien`);
    - the MAJOR 1 cases;
    - MSYS `/c/…`;
    - the POSIX root followed by `'` or `.`.
- **[MINOR 6]** "block updated" is printed only after success, but the blocks stay when a later step fails.
- **[MINOR 7]** The judge prompt does not explain `[external path]` (`ac-test-fail-judge.md:54`). It may be
  declined: the spec does not ask for it.
