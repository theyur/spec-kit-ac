# Step 12 — Bug fixes for 0.1.4 (GitHub issues #17, #18, #19)

**Status:** done (2026-11-16; spec-approved 2026-11-16; decision 7, S12-R05, R07 and Risk 3 amended with the user's approval after
plan-critic round 1: root found by its prefix, other Windows paths hidden up to their last separator, no POSIX root
list, no `resolve()` of candidates; refined again with the user's approval after rounds 2 and 3: UNC start
`\\server\share`, root forms without a trailing separator, roots inside an earlier root's run, frames below the
root up to `:line`) · **Tracker row:** 12 · **Source of truth:** `docs/DESIGN.md`

## Goal

Close the three bugs of the `v0.1.4` milestone, each with regression tests:

1. **#19:** the raw `ac-results.trx` files are no longer committed. They hold the user's login, the machine name
   and local paths.
2. **#18:** `ac-results.md` holds no absolute local path. Paths below the project root become repo-relative, and
   every other absolute path becomes a placeholder.
3. **#17:** the writer and the judge can read and search only the API listings (`<refsDir>/api/`), not the
   reference DLLs.

The two enhancements of the milestone (#15 `InternalsVisibleTo`, #16 an `Exe` surface) are later steps. The
release of 0.1.4 is not part of this step.

## Context (inspected 2026-11-16)

- **#19.** `init_scaffold.gitignore_lines()` (`init_scaffold.py:120–122`) builds the `.gitignore` block. Only
  `init_scaffold.py` writes the blocks (`:174–175`). `uninstall` removes them (`deploy.py:755–762`).
  - `upgrade` (`deploy.py:785–821`) never touches them, so an existing install keeps its old block.
  - `doctor` (`deploy.py:984–990`) checks only that each block exists. When one is missing it says "run
    /speckit-ac-init again to verify and repair", but re-running init with a config only verifies (step 5
    decision). It writes no block, so the advice is wrong today.
  - The TRX is read once, by `summarize_trx.py` in step 8 of `/speckit-ac-tests-analyze`. No AC role reads it
    (WORKFLOW §3.1). No script or check reads it after that. The judge reads only `ac-results.md`.
  - The CT method allows ignoring it (WORKFLOW-SETUP-CT §5.8: "except `*.trx` if the user prefers"). Our docs
    list it with the committed run records (CONFIG.md per-feature paths table).
- **#18.** `summarize_trx.py` hides stack frames outside the AC project (`clean_stack`, `:93–104`). It keeps the
  AC project's frames as written, with absolute paths (`in <drive>:\…\StepDefinitions\X.cs:line 42`). The
  exception message (`:124`), the step trace and stdout (`:126–127`) are copied unchanged. A
  `FileNotFoundException` message, for example, quotes the full path.
  - The project root is `aclib.root(__file__)`: the folder the scripts are installed in, so in a worktree
    session it is the worktree.
  - The stack, exception and trace sections are code-fenced (`section()`, `:150–155`). The results table
    (test names, tags) is not.
  - Tests: `tests/test_scripts.py:552–650`, `:1174–1187` (`trx_project` fixture).
- **#17.** `Guard.folders()` (`guard.py:425–429`) gives the writer and the judge `self.refs` (the whole
  `refsDir`) as a read and search root. `export_refs.py` writes the DLLs to `<refsDir>/` and the listings to
  `<refsDir>/api/<Assembly>.cs` (`:223–252`). The agents use only `<REFS_DIR>/api/` (`ac-test-writer.md:30`,
  `ac-test-fail-judge.md:23`). Their placeholder tables say "Reference assemblies and their API listings"
  (`:55`, `:40`).
  - The ref-mode build is the one allowed Bash command. `dotnet` reads the DLLs itself, so the guard's Read and
    Grep rules don't apply to it.
  - Tests: `tests/test_guard.py:52, 63, 92–93` (`writer Grep in refs` expects ALLOW today).

## Decisions to approve

1. **#19: git-ignore, don't delete.** The `.gitignore` block gets `/specs/*/ac/runs/**/*.trx`. The file stays on
   disk for local debugging (the main agent may read it). v1.0 supports only `specs/NNN-name` features (step 2
   decision), so one pattern covers every feature.
2. **`upgrade` refreshes both managed blocks** (`.gitignore` and `.gitattributes`) when `.workflow/config.json`
   exists. `upgrade` already refuses an invalid config. It reuses the init lines (one definition, in
   `init_scaffold.py`). Without a config it writes no block: init writes them later. This amends DESIGN §9
   ("`/speckit-ac-init` writes them"). `install` stays unchanged: a fresh install has no config yet.
3. **`doctor`:** a missing block stays a FAIL, and its advice becomes `run \`speckit-ac upgrade\``. A block whose
   lines differ from what the config gives is a new `warn`: `<file>: the speckit-ac block is out of date (run
   \`speckit-ac upgrade\`)`.
4. **TRX files already in git** are not touched. The changelog says how to untrack them
   (`git rm --cached -- "specs/*/ac-results.trx"`), and that this does not remove them from history.
5. **#18: clean the whole file, not only the frames.** Every line `summarize_trx.py` writes passes through one
   function, `scrub_paths(text, root)`. This covers the table, the step trace, stdout, the exception and the
   frames. The frame filter still decides on the raw path, before cleaning.
6. **Placeholder `[external path]`**, not `<external>`. An angle-bracket tag in the unfenced results table
   disappears when GitHub renders the file. The square brackets match the existing `[non-AC frame(s) hidden]`.
7. **What counts as an absolute path** (rules in S12-R05):
   - **The project root** is found by its own prefix wherever it appears (both separators, case-insensitive on
     Windows). A folder name with spaces below the root therefore cannot cut the path short.
   - **Every other Windows drive path and UNC path** is hidden up to the last separator of its kind on its
     line (or the last matching quote). The rule prefers hiding too much to leaking a tail such as a user name
     with spaces.
   - **POSIX:** only the project root is replaced. Other POSIX paths stay as they are: a bare `/api/users/42` or
     `/Users/42` in an exception message is far more likely a route than a local path, and the judge needs it.
     v1.0 targets Windows (DESIGN §2), so a native TRX holds no other local POSIX paths.
   - Candidates are compared as text, never resolved. That avoids network lookups for UNC paths and `OSError`
     from the file system.
8. **#17: the listings folder only.** For the writer and the judge, the read and search root is `<refsDir>/api`
   instead of `<refsDir>`. The main agent is unchanged: it may read the whole `refsDir`, but writes there are
   still denied.
9. **Version.** The changes go under `## [Unreleased]` in `CHANGELOG.md`. The release is a separate release PR,
   as for 0.1.3.

## Requirements

### #19: TRX files git-ignored

- **S12-R01** `init_scaffold.gitignore_lines(cfg)` ends with `/specs/*/ac/runs/**/*.trx`. Other lines and their
  order are unchanged.
- **S12-R02** `upgrade` writes both managed blocks, with `aclib.write_block`, after the `CLAUDE.md` block and
  before the guard self-test, when `.workflow/config.json` exists:
  - the lines come from `init_scaffold.gitignore_lines` / `gitattributes_lines`, loaded with `payload_module`;
  - it prints `<file>: speckit-ac block updated.` only when the file changed;
  - an unchanged block is not rewritten (`write_block` returns `False`, and the file's bytes stay the same);
  - without a config it writes no block and prints nothing about blocks.

  When a later upgrade step fails, the refreshed blocks stay. They are the same content init would write.
- **S12-R03** `doctor`'s block check, when a valid config exists:
  - missing block: `FAIL`, `<file> has no speckit-ac block (run \`speckit-ac upgrade\`)`;
  - lines differ from the config's: `warn`, the S12 decision 3 text. Compare the lines between the markers
    with CRLF folded to LF, ignoring trailing whitespace on each line;
  - same lines: `ok` as today.

  Without a config, the check stays as it is (the config check already warns that init has not run).
- **S12-R04** Tests:
  - `gitignore_lines` holds the TRX line, and `git check-ignore` matches a real
    `specs/001-x/ac/runs/run-001/analyze-1/ac-results.trx` and not `.../ac-results.md`. This runs in a temporary
    git repo and is skipped when `git` is missing.
  - `upgrade` on the fixture project with an old block (no TRX line) writes the new line and leaves the rest of
    `.gitignore` byte-identical. A second `upgrade` writes nothing to `.gitignore` (unchanged mtime and bytes).
    Without a config, no `.gitignore` is created.
  - `uninstall` after `upgrade` removes the whole block, the TRX line included. The install → uninstall
    round-trip tests still pass.
  - `doctor`: an old block gives the warn line and no FAIL; a missing block gives the FAIL with the new advice;
    a CRLF copy of a current block is `ok`.
  - The opt-in real deploy test (`test_deploy_real.py`) asserts the TRX line after `upgrade` in a project that
    has a config.

### #18: no absolute paths in `ac-results.md`

- **S12-R05** `scrub_paths(line, roots, windows=os.name == "nt")` replaces each absolute path in one line of
  text. `roots` are the root's forms. `summarize_trx.py` passes the resolved root (`aclib.root`) and, when the
  current folder resolves to the same folder, the current folder as the OS gives it. Candidates are compared as
  text; nothing is resolved.
  - **Pass 1, the root.**
    - Every place where a root form appears counts, both separators accepted and case ignored on Windows,
      provided:
      - it is not preceded by a letter, a digit, `_`, `.` or a separator;
      - it is followed by a separator or by a character that cannot be part of a path name (whitespace, a
        quote, `<>|`, the end of the line).
    - A trailing separator of a root form is dropped first. A drive root (`X:\`, a `subst` drive) then counts
      only when a separator follows.
    - The root and the one separator after it are removed. In the run after them, `\` becomes `/`. The run
      ends at whitespace, a quote, `<>|`, `:line `, the next place where a root form appears, or the end of the
      line. In a stack frame (` in ` before the root, `:line ` plus digits later on the line), the run ends only
      at `:line `, so folder names with spaces convert fully.
    - The root alone, or the root and a separator with an empty run after them, becomes `.`.
    - A folder with spaces below the root keeps its name. It is part of the repository, so it leaks nothing.
  - **Pass 2, other Windows paths**, on the text left by pass 1:
    - **Starts:**
      - a drive path: `X:\` or `X:/`, not preceded by a letter or digit, so `http://` does not count;
      - a UNC path: two backslashes, a server name (letters, digits, `.`, `-`, `_`), a backslash and a share
        name, not preceded by a backslash, a letter or a digit (`\\server\share`). A regex such as `\\d+\\.`
        therefore does not count.

      The path's separator is `/` for `X:/` and `\` otherwise.
    - **Region:** from the start to the first `<`, `>` or `|` after it, or the end of the line.
    - **End**, the first rule that applies:
      - a stack frame (the text before the start ends with ` in `, and `:line ` plus digits follows in the
        region): the path ends at `:line`;
      - quoted (the character before the start is `'` or `"`, and that quote appears again in the region): the
        path ends at the **last** such quote in the region;
      - otherwise: the path ends at the end of the whitespace-free run that holds the path's last separator
        in the region. Trailing `.`, `,`, `;`, `:` and `)` go back to the text.
    - Each such path becomes `[external path]`. That covers the user profile, the NuGet cache, SDK folders, a
      network share, and the main checkout when the root is a worktree. The rule prefers hiding too much (text
      between two paths on one line) to leaking a tail.
  - **POSIX:** pass 1 runs with the POSIX root. Other POSIX paths stay as they are (decision 7). Pass 2 runs in
    both modes: a Windows path in the text is hidden on any OS.
  - Text without a path comes back unchanged.
- **S12-R06** `summarize_trx.py` applies `scrub_paths` to every line it writes. That covers the table rows, the
  headings, the step trace, stdout, the exception and the kept frames. `clean_stack` still decides with the raw
  frame (`in_ac_project`), so cleaning never changes which frames are kept. The module docstring states the
  rule.
- **S12-R07** Tests:
  - Pure `scrub_paths` cases. Rows marked *both* run with `windows=True` and `windows=False`, the others with
    `windows=True` (POSIX rows: `windows=False`). Root `R` = `<drive>:\w\repo`, POSIX `/home/u/repo`:

    | Input | Expected | Mode |
    | --- | --- | --- |
    | frame ` in R\tests\App.AcceptanceTests\StepDefinitions\X.cs:line 42` | ` in tests/App.AcceptanceTests/StepDefinitions/X.cs:line 42` | Windows |
    | the same with `/` separators and the root part in lower case | same | Windows |
    | two root forms `<drive>:\real\repo` and `S:\` (a `subst` drive), frame ` in S:\tests\X.cs:line 1` | ` in tests/X.cs:line 1` | Windows |
    | `cwd is R.` (root followed by a full stop) | `cwd is [external path].` | Windows |
    | `cwd is R\` | `cwd is .` | Windows |
    | `R\a.cs;R\b.cs` (two root paths, no space) | `a.cs;b.cs` | Windows |
    | `/home/u/repo/a.cs,/home/u/repo/b.cs` | `a.cs,b.cs` | POSIX |
    | frame ` in R\tests\My Steps\X.cs:line 4` | ` in tests/My Steps/X.cs:line 4` | Windows |
    | `open C:/Users/u/x.json failed` | `open [external path] failed` | Windows |
    | root `<drive>:\w\my repo`, frame ` in <drive>:\w\my repo\tests\X.cs:line 4` | ` in tests/X.cs:line 4` | Windows |
    | the root of a worktree (`R\.claude\worktrees\w1`) as root, a frame below it | repo-relative to the worktree | Windows |
    | a frame in the main checkout `R\src\…` while the root is the worktree | `[external path]` | Windows |
    | `cwd is R` | `cwd is .` | Windows |
    | `R\a.txt C:\Users\u\b.txt` | `a.txt [external path]` | Windows |
    | `Could not find file 'C:\Users\First Last\AppData\x.json'.` | `Could not find file '[external path]'.` | Windows |
    | `'C:\Users\O'Brien\x.json'` | `'[external path]'` | Windows |
    | unquoted `C:\Users\Anna Maria Rossi\src\x.cs failed` | `[external path] failed` | Windows |
    | NuGet cache path `C:\Users\u\.nuget\packages\reqnroll\…\X.cs:line 9` in a frame | `[external path]:line 9` | Windows |
    | `\\server\share\x.cs` | `[external path]` | Windows |
    | `Expected pattern "^\\d+\\.\\d+$"` | unchanged | Windows |
    | table row `\| C:\a b\x.cs \| failed \|` | `\| [external path] \| failed \|` | Windows |
    | a path ending a sentence: `in C:\x\y.txt.` | `in [external path].` | Windows |
    | `/home/u/repo/tests/X.cs:line 3` | `tests/X.cs:line 3` | POSIX |
    | `/usr/share/dotnet/sdk/x` | unchanged | POSIX |
    | `GET /api/users/42 returned 404`, `GET /Users/42` | unchanged | both |
    | `see https://example.com/a/b` and `F001/AC-001` | unchanged | both |
    | `ratio 1:2` and `Expected: 5` | unchanged | both |

  - `summarize_trx.py` on the `trx_project` fixture, run **from a folder other than the project root**. Its TRX
    has three parts:
    - frames that use the fixture's real absolute root, one of them with `/` separators and the root part
      upper-cased;
    - an exception message that quotes a path in a fake user profile with a space in it;
    - stdout that holds the root.

    The test checks:
    - the written file contains neither the root (case-folded, either separator) nor any part of the fake
      profile, and no drive or UNC path at all;
    - the kept frame reads `<acProjectDir>/StepDefinitions/…:line N`;
    - `[non-AC frame(s) hidden]` still appears where it did.
  - The existing `summarize_trx` cases still pass unchanged: step trace, tags, pending outcome, hidden frames,
    NUnit names, `--current`, `--only-current`.

### #17: AC roles read only the API listings

- **S12-R08** `Guard.folders(role)` returns `f"{self.refs}/api"` in place of `self.refs` for the writer and
  the judge. The translator's folders, `readable_file()` and every main-agent rule are unchanged.
- **S12-R09** The agents' placeholder rows read `` `<REFS_DIR>` | Folder of the reference assemblies; you read
  only the API listings in `<REFS_DIR>/api/` `` (writer and judge). Their "Public API listings" lines are
  unchanged.
- **S12-R10** Tests (`test_guard.py` table and `test_agents.py`):
  - Writer and judge, each denied:
    - Read `<refsDir>/App.Core.dll`;
    - Grep and Glob with `path` `<refsDir>`;
    - Grep with `path` `<refsDir>/App.Core.dll`.
  - Writer and judge, each allowed:
    - Read `<refsDir>/api/App.Core.cs`;
    - Grep and Glob with `path` `<refsDir>/api`.
  - `writer Grep in refs` becomes a DENY case. A new `writer Grep in refs/api` case is ALLOW.
  - The writer's ref-mode build command is still allowed.
  - The main agent may still Read `<refsDir>/App.Core.dll`; a write there is still denied.
  - The `test_agents.py` walk (every input the template names is readable) still passes with the new rows.
  - The smoke-test cases are unchanged (none of them touches `refsDir`).

### Docs

- **S12-R11** `CHANGELOG.md` `## [Unreleased]`:
  - `### Fixed`:
    - raw TRX files are git-ignored (#19);
    - `ac-results.md` holds no absolute local path (#18);
    - the writer and the judge can no longer search the reference DLLs (#17);
    - `doctor`'s advice for a missing block.
  - `### Changed`: `upgrade` refreshes the `.gitignore` / `.gitattributes` blocks.
  - An upgrade note:
    - run `speckit-ac upgrade`;
    - untrack committed TRX files with `git rm --cached -- "specs/*/ac-results.trx"` (history keeps them);
    - `ac-results.md` files written before the upgrade are not rewritten.
- **S12-R12** Docs:
  - **`docs/CONFIG.md`:**
    - the `.gitignore` block list gets the TRX line;
    - the managed-blocks sentence says `upgrade` refreshes them;
    - the per-feature paths table marks `ac-results.trx` as git-ignored;
    - a sentence on `ac-results.md` path cleaning.
  - **`docs/WORKFLOW.md`:**
    - §3.1: the refs row splits into `<refsDir>/api/**` (writer, judge: read) and the DLLs (compiler only);
    - the TRX row says "local only, git-ignored".
  - **`docs/DESIGN.md`:**
    - §9: `upgrade` refreshes the blocks;
    - a decision-log row for decisions 1–8.
  - **`docs/steps/TRACKER.md`:** row 12.
  - No local absolute path in any changed file. WORKFLOW-SETUP-CT stays as it is (reference copy).

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S12-A01 | `uv run pytest -q --tb=short` passes on CPython 3.14 and 3.11 | all |
| S12-A02 | The R04 tests pass. Each of these mutations fails at least one test: dropping the TRX line; `upgrade` skipping the blocks; rewriting an unchanged block; `doctor` treating an old block as `ok` | R01–R04 |
| S12-A03 | The R07 table and the fixture test pass. Each of these mutations fails at least one test: case-sensitive root match on Windows; no `/` separator handling; cleaning before `clean_stack`; ending an unquoted external path at its first whitespace | R05–R07 |
| S12-A04 | The R10 cases pass. Putting `self.refs` back in `folders()` fails at least one test | R08–R10 |
| S12-A05 | Opt-in real runs (`SPECKIT_AC_DOTNET_E2E=1`): in the e2e sample, `ac-results.md` of the 001-buggy run contains no absolute path, and the failing frame is repo-relative. The real deploy test shows the TRX line after `upgrade` | R02, R06 |
| S12-A06 | Changelog, CONFIG, WORKFLOW, DESIGN and tracker entries exist. No local absolute path in any changed file | R11, R12 |

## Out of scope

- #15 (`InternalsVisibleTo`) and #16 (`Exe` surface): later steps.
- The 0.1.4 release (version bump, tag, README pin, release PR) and upgrading consumer projects.
- Removing committed TRX files from git history, or rewriting `ac-results.md` files written before the fix.
- `doctor` checking the git index for tracked TRX files.
- `install` writing the blocks when a config already exists (uninstall → install keeps the config): `doctor`
  reports the missing block and `upgrade` repairs it.
- Other personal data in test output that is not a path (a user name printed by the implementation, a machine
  name in an exception message).
- POSIX absolute paths outside the root (decision 7), and MSYS forms such as `/c/Users/…`.
- `Glob` results that list the DLL file names from a search root above `api/`: that root is now denied.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | `scrub_paths` changes text the judge needs (a route, a URL, a `F001/AC-001` key) | POSIX: only the root is replaced; drive paths need `X:\` or `X:/` not after a letter. The R07 table holds the route, URL, key and colon cases. An external Windows path can hide text between it and a later separator on the same line; that loses words, never a path |
| 2 | A local path survives in an unusual form (an unquoted POSIX path, an MSYS `/c/…` path) | The fixture test checks that neither the root nor any part of the fake profile appears, and that no drive or UNC path is left; the known forms that are not covered go in the changelog note as limits |
| 3 | The frames are built in a folder that is not the root as written (a junction, `subst`) | The root is compared in its resolved form and as the current folder gives it. Candidates are not resolved. A path that still does not match becomes `[external path]`, which hides it rather than leaking it |
| 4 | `upgrade` now edits `.gitignore`, which users treat as their own file | Only the text between the markers changes; R04 checks the rest stays byte-identical and that an unchanged block is not rewritten |
| 5 | An agent prompt or command still points the writer or judge at a DLL | R10 walks every input in the templates through the real guard; the templates name only `<REFS_DIR>/api/` |
