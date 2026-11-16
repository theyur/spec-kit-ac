# Plan — Step 12: bug fixes for 0.1.4 (issues #17, #18, #19)

Spec: `docs/steps/12-fixes-0.1.4-bugs.spec.md`. It was approved on 2026-11-16. The user approved amendments to
decision 7, S12-R05, S12-R07 and Risk 3 after critic round 1, and refinements after rounds 2 and 3. Revision 3
of this plan follows the spec as amended. Critic verdict: APPROVE (round 3).

## Evidence (inspected)

- `src/speckit_ac/payload/scripts/init_scaffold.py`:
  - `gitignore_lines(cfg)` (`:120–122`) and `gitattributes_lines(cfg)` (`:125–128`);
  - `main()` writes them with `aclib.write_block` (`:174–175`);
  - at import it runs `sys.path.insert` (`:22`) and imports `aclib`, `init_config` and `init_detect`. This is
    harmless from the CLI, because `payload_module` already put that folder on `sys.path`. No subprocess runs at
    import.
- `src/speckit_ac/payload/scripts/aclib.py:386–445`:
  - `_block_span` raises `AcError` on a broken block, and its message names no file;
  - `write_block` decodes strict UTF-8 (`:413`), so a legacy code page raises `UnicodeDecodeError`, which is a
    `ValueError`;
  - `write_block` returns `False` and writes nothing when nothing changes, and it keeps the file's line ending.
- `src/speckit_ac/deploy.py`:
  - `aclib = payload_module("aclib")` (`:26`). `payload_module(name, payload)` imports from
    `<payload>/scripts` and caches in `sys.modules`;
  - `config_problem(root)` (`:248–256`);
  - `upgrade()` (`:785–836`):
    - checks the prerequisites and the config before any change (`:789–800`);
    - unregisters the guard (`:802`);
    - runs the steps in a `try` whose handler catches `DeployError`, `AcError` and `OSError` (`:822`) and then
      re-registers;
    - prints its `say` lines after success;
  - `cli.py:54–58` catches only `DeployError`;
  - uninstall removes both blocks (`:755–762`);
  - `doctor.c_config()` (`:970–990`):
    - without a config, a warn and return;
    - else the python check, then each block file decoded with `replace`, giving `ok` or `FAIL … (run
      /speckit-ac-init again to verify and repair)`;
    - the exit code is 1 only on FAIL (`:1004`).
- `tests/test_deploy.py`:
  - `valid_config(project)` = `acproject.CONFIG` (`:667`);
  - `test_doctor_config_ok_and_blocks` (`:730–741`);
  - `test_upgrade_then_uninstall_round_trips` (`:611`).
- `tests/test_init.py:451–484`: block tests with literal lines; no test calls `gitignore_lines`.
- `tests/test_deploy_real.py:97–131`: no config; its clone's doctor expects exactly one warn.
- `src/speckit_ac/payload/scripts/summarize_trx.py`:
  - `root = aclib.root(__file__)` is resolved;
  - `in_ac_project` resolves the frame's file against the current folder (`:87`);
  - `main()` writes `"\n".join(lines)` (`:202`).
- `tests/acproject.py:91–95`: `run_script` always runs with `cwd=project`.
- `tests/test_scripts.py:552–650`: the `TRX` fixture with `{ac}` / `{root}` = `str(project / AC)` / `str(project)`.
- `src/speckit_ac/payload/hooks/guard.py`:
  - `folders(role)` (`:425–429`);
  - Grep/Glob path rule (`:473–483`);
  - the main agent's write denial under refs (`:325`).
- `tests/test_guard.py`:
  - CT cases `writer Grep in refs` (`:92`, ALLOW) and `writer Grep with absolute glob` (`:93`, path refs);
  - `main writes an API listing` (`:294`).
- `tests/test_agents.py:43–47, 208`: the "Public API listings" line is walked as a `dir` through the real guard.
- Agents:
  - `ac-test-writer.md:55` and `ac-test-fail-judge.md:40` (`<REFS_DIR>` rows);
  - `ac-test-fail-judge.md:54` (hidden frames).
- `tests/test_e2e_sample.py:51–66`: `implement_and_run` (opt-in, dotnet).
- Probed on 2026-11-16 in a scratch repo:
  - `/specs/*/ac/runs/**/*.trx` ignores `specs/001-x/ac/runs/run-001/analyze-1/ac-results.trx` and not the
    `.md`;
  - `git rm --cached -- "specs/*/ac-results.trx"` untracks it;
  - git on the scratch drive needs `-c safe.directory=*`, because that file system records no owner.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| 1 | Loading `init_scaffold` through `payload_module` from the CLI runs no command | 0.95 | `upgrade` / `doctor` would run commands | Read (done); the unit tests call it in the fake project |
| 2 | `doctor` compares against the **bundled** payload's lines, the same source `upgrade` writes from | 0.75 | A CLI newer than the install warns "out of date" alongside the version warn; `upgrade` fixes both | `deploy.aclib` is bundled too |
| 3 | The git pathspec in the changelog untracks nested TRX files | verified | — | Probed |
| 4 | The ignore pattern matches the TRX path | verified | — | Probed; also the step 2 test |
| 5 | A real TRX writes frame paths with the root as the compiler saw it, so in the same form as the resolved root or the current folder | 0.8 | Repo-relative replacement misses, and the path becomes `[external path]` (hidden, no leak) | The e2e assertion (step 10) on a real TRX |
| 6 | Nothing reads `<refsDir>` (other than `api/`) as the writer or judge | 0.9 | An agent loses an input | `test_guard_consistency` walks every template input |

None is blocking.

## Steps

### #19

1. **TRX line** (S12-R01). `init_scaffold.gitignore_lines()` appends `"/specs/*/ac/runs/**/*.trx"`.
2. **Tests for R01** (S12-R04), in `test_init.py`:
   - new `test_gitignore_lines_end_with_the_trx_pattern`: the last line, and the earlier lines are unchanged in
     order;
   - new `test_trx_pattern_is_ignored_by_git` (skipped without `git`): a temporary repo holds a `.gitignore`
     with the block. `git -c safe.directory=* check-ignore -q --no-index <trx>` exits 0, and the same for the
     `.md` exits 1.
3. **Block reader** (`aclib.py`). New `block_lines(path, begin=BLOCK_BEGIN, end=BLOCK_END) -> list[str] | None`:
   - it returns `None` when the file or the block is missing;
   - otherwise it returns the lines between the markers, CRLF folded and trailing whitespace stripped per line;
   - it decodes strict UTF-8. A `UnicodeDecodeError`, or an `AcError` from `_block_span`, is re-raised as
     `AcError(f"{path.name}: {reason}")`.
4. **`upgrade` writes the blocks** (S12-R02), in `deploy.py`:
   - new `GIT_BLOCKS = (".gitignore", ".gitattributes")`, used by uninstall, doctor and here;
   - **pre-check:** when the config exists, `aclib.block_lines` is called on each file in the "stopped before any
     change" list (`:789–800`), and each `AcError` adds a problem. A broken block or a non-UTF-8 file therefore
     stops `upgrade` before the guard is unregistered;
   - new `write_git_blocks(root, payload) -> list[str]`:
     - without `.workflow/config.json` it returns `[]`;
     - else it validates the config, loads `init_scaffold` with `payload_module("init_scaffold", payload)`, and
       calls `aclib.write_block` for each file;
     - `AcError`, `UnicodeError` and `OSError` become `DeployError(f"{name}: {error}")`;
     - it returns the changed names;
   - in `upgrade()`, after `write_claude_block`: `step = "git blocks"`, then the call, and right after it
     `say(f"{name}: speckit-ac block updated.")` for each changed name. The line is printed at once, so the
     user sees it even when a later step fails (MINOR 6).
5. **`doctor` block check** (S12-R03), in `c_config()`. After validation, the expected lines come from the bundled
   `payload_module("init_scaffold")`. Each file is checked on its own, in its own `try`:
   - `AcError` from `block_lines` → `FAIL`, `<name>: cannot read the speckit-ac block (<reason>)`, and the next
     file is still checked;
   - `None` → `FAIL`, `<name> has no speckit-ac block (run \`speckit-ac upgrade\`)`;
   - lines differ from the expected ones (trailing whitespace stripped on both sides) → `warn`,
     `<name>: the speckit-ac block is out of date (run \`speckit-ac upgrade\`)`;
   - else → `ok`, as today.
6. **Deploy tests** (S12-R04), in `test_deploy.py`:
   - `test_upgrade_refreshes_git_blocks`. Install, write `valid_config`, write `.gitignore` = user lines plus an
     old block (the current lines without the TRX line), and write `.gitattributes` with its current block.
     - `upgrade` prints `.gitignore: speckit-ac block updated.` and no `.gitattributes` line;
     - the TRX line is in the block, and the bytes outside the block are unchanged;
     - a second `upgrade` leaves the `.gitignore` bytes and `st_mtime_ns` unchanged and prints no "block
       updated".
   - `test_upgrade_without_config_writes_no_block`: no `.gitignore` or `.gitattributes` is created.
   - `test_upgrade_stops_on_a_broken_git_block`, parametrised with "begin marker without end" and
     "non-UTF-8 bytes in `.gitignore`":
     - it raises `DeployError` with "stopped before any change" and the file name;
     - the guard is still registered (`ours(project) == [deploy.guard_group()]`);
     - the extension files are unchanged (manifest hashes still match).
   - `test_upgrade_with_config_then_uninstall_round_trips`: the config is written before the snapshot, then
     install → upgrade (which creates both files) → uninstall, and the snapshot is equal.
   - `test_doctor_config_ok_and_blocks` is rewritten:
     - with no `.gitattributes` block: the FAIL with the new advice;
     - `["x"]` blocks: two out-of-date warns, and code 0;
     - the current lines: `ok` for both;
     - a CRLF copy of the current block: `ok`;
     - a broken `.gitignore` block: a FAIL naming `.gitignore`, and the `.gitattributes` line still appears.
7. **Real deploy test** (S12-R04, A05). New `test_upgrade_writes_git_blocks_with_a_config` in
   `test_deploy_real.py`:
   - write `acproject.CONFIG` as the config **before** the snapshot, then install and `upgrade`;
   - the `.gitignore` block contains the TRX line, and `doctor` prints no git-block warn or FAIL;
   - uninstall, and the snapshot equals the one taken before install. The config is still in place, so
     `.workflow/` is not left empty (round 2, MINOR 4).

### #18

8. **`scrub_paths(line, roots, windows=os.name == "nt")`** in `summarize_trx.py` (S12-R05 as amended).
   - **Constants:**
     - `EXTERNAL = "[external path]"`;
     - `QUOTES = "'\""`;
     - `REGION_END = re.compile(r"[<>|]")`;
     - `START = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?<![\\A-Za-z0-9])\\\\[A-Za-z0-9._-]+\\[^\\\s<>|'\"]")`.
       The UNC part needs two backslashes, a server name and the first character of a share name, so the regex
       text `\\d+\\.` does not count (round 2, MAJOR 1).
   - **Pass 1, per root form.**
     - A trailing separator of the root form is removed first (round 2, MINOR 3).
     - The pattern:
       - the lookbehind `(?<![A-Za-z0-9_.\\/])`;
       - then the root, with each separator written as `[\\/]` and every other character escaped;
       - then either a separator, or a lookahead `(?=[\s'"<>|]|$)`, as R05 lists it, with no `.,;:)`
         (round 2, MINOR 2). A bare drive root (`X:`) has only the separator branch, so `Expected S: 5` stays
         as it is.
     - It uses `re.IGNORECASE` when `windows`. Longer root forms are tried first.
   - Prototyped outside the repo on 2026-11-16 (scratchpad `scrub_proto.py`). Every row of the amended R07 table
     gives the expected output, and so do the extra rows: `Expected S: 5`, and `HOME is C:\Users\First Last`,
     which gives the documented limit.
     - **A match with a separator:** the match is removed. The following run is copied with `\` → `/` until
       whitespace, a quote, `<>|`, `:line ` or the end of the line.
     - **A match without one:** it becomes `.`.
   - **Pass 2, scanning left to right with `START`:**
     - The region runs from the match to the first `REGION_END` after it, or to the end of the line.
     - The path's separator is `/` when the match is `X:/`, else `\`.
     - **End:**
       - **Frame:** `line[:start].endswith(" in ")` and `re.search(r":line \d", region)`. The path ends at that
         `:line`.
       - **Quoted:** `start > 0`, `line[start-1] in QUOTES`, and that quote occurs again in the region. The path
         ends at the last occurrence in the region.
       - **Otherwise:** the path runs to the end of the non-whitespace run that holds the last separator in
         the region. Trailing `.,;:)` are given back to the text.
     - The path is replaced by `EXTERNAL`, and scanning goes on after it.
   - **Roots in `main()`:** `[str(root)]`, plus `os.getcwd()` when it differs as text and
     `Path.cwd().resolve() == root`. An `OSError` there means no cwd form.
   - The module docstring states the two passes.
9. **Apply it** (S12-R06). `main()` builds `text = "\n".join(lines)` as today, then writes
   `"\n".join(scrub_paths(l, roots) for l in text.split("\n")) + "\n"`. `clean_stack()` still works on raw frames,
   since scrubbing happens only at write time.
10. **Tests** (S12-R07):
    - `test_scripts.py`, new parametrised `test_scrub_paths`:
      - it has every row of the amended spec table. Rows marked *both* run in both modes;
      - the roots are plain strings: `"C:\\w\\repo"`, `"C:\\w\\my repo"`, `"C:\\w\\repo\\.claude\\worktrees\\w1"`,
        the pair `["C:\\real\\repo", "S:\\"]`, and `"/home/u/repo"` for POSIX;
      - row 2 lower-cases only the root part (round 2, MINOR 1);
      - extra rows:
        - `Expected S: 5` with root `S:\` stays unchanged;
        - `HOME is C:\Users\First Last` gives `HOME is [external path] Last`. This pins the documented limit, so a
          change to it is deliberate;
      - nothing touches the file system, so the rows are deterministic on any OS.
    - `tests/acproject.py`: `run_script` gets an optional keyword `cwd`, defaulting to `project`. Every existing
      caller is unchanged.
    - New `test_summarize_trx_scrubs_paths`. It runs with `cwd=tmp_path / "elsewhere"`, which catches the
      "scrub before `in_ac_project`" mutation (BLOCKER 1). The TRX is built on the `trx_project` fixture:
      - a kept frame `in {ROOT_UPPER}/{AC}/StepDefinitions/F001/LoginSteps.cs:line 12`, where only the root part
        is upper-cased and the separators are `/`;
      - a second kept frame written natively;
      - a non-AC frame;
      - the exception message `Could not find file 'C:\Users\First Last\AppData\x.json'.`;
      - stdout `cwd: {root}` and, unquoted, `profile C:\Users\First Last\AppData\y.json failed` (round 2, MINOR 7).

      The test checks:
      - the output, lower-cased with `\` folded to `/`, contains neither `str(project)` in the same form, nor
        `first last`, nor `appdata`;
      - `re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\\w", md)` is `None`;
      - both frames read `in {AC}/StepDefinitions/F001/LoginSteps.cs:line 12`;
      - `[non-AC frame(s) hidden]` appears;
      - `cwd: .` is in the trace.
    - `test_summarize_trx` gets one more assertion: `f"in {AC}/StepDefinitions/F001/LoginSteps.cs:line 12"`.
    - `test_e2e_sample.py` `implement_and_run` (opt-in) gets three checks:
      - the drive/UNC regex finds nothing in `ac-results.md`, and the project path does not appear (case-folded,
        both separators);
      - the buggy run has a line with `StepDefinitions/F001/`;
      - `git -c safe.directory=* check-ignore -q` matches the TRX.

### #17

11. **Guard** (S12-R08). In `folders()`, the non-translator list uses `f"{self.refs}/api"` instead of
    `self.refs`.
12. **Agents** (S12-R09, MINOR 7):
    - the `<REFS_DIR>` rows in `ac-test-writer.md` and `ac-test-fail-judge.md` get the spec text;
    - `ac-test-fail-judge.md:54` gets one sentence: "`[external path]` replaces a local path outside the project,
      removed on purpose; the original path is not available to you." (reworded, round 2, MINOR 5).
13. **Guard tests** (S12-R10), in `test_guard.py`:
    - CT `writer Grep in refs` → DENY, description unchanged, with a comment naming step 12;
    - CT `writer Grep with absolute glob` → `path` `{root}/artifacts/refs/api`;
    - new cases, each for W and J:
      - Read `artifacts/refs/App.Core.dll`: DENY;
      - Grep and Glob with `path` `artifacts/refs`: DENY;
      - Grep with `path` `artifacts/refs/App.Core.dll`: DENY;
      - Read `artifacts/refs/api/App.Core.cs`: ALLOW;
      - Grep and Glob with `path` `artifacts/refs/api`: ALLOW;
    - main agent:
      - Read `artifacts/refs/App.Core.dll`: ALLOW;
      - Write `artifacts/refs/App.Core.dll`: DENY (new);
    - the writer's ref build is still allowed: confirm that the existing case is there, and add one if it is
      not.

    `test_agents.py` runs unchanged.

### Docs

14. **Changelog** (S12-R11), under `[Unreleased]`, replacing `_Nothing yet._`. The text is as in the spec. The
    limit note says:
    - POSIX paths other than the project root are kept, and so are MSYS `/c/…` forms;
    - an external Windows path can hide the words between it and a later separator on the same line;
    - the words after an external path's last separator stay. Examples: `C:\Users\First Last` keeps `Last`, and
      a file name with a space keeps its tail. The same goes for a path with mixed separators, a path with an
      unclosed quote, and a drive path glued to a word (`dirC:\…`);
    - a sibling folder whose name is the root plus a space (`repo 2`) gives `. 2\…`.

    The upgrade note adds that `upgrade` now stops on a `.gitignore` or `.gitattributes` that is not UTF-8, and
    names the file (round 2, MINOR 6 and 8).
15. **Docs** (S12-R12):
    - `CONFIG.md`:
      - the TRX line in the block list;
      - "written by `/speckit-ac-init`, refreshed by `speckit-ac upgrade`, removed by `speckit-ac uninstall`";
      - `ac-results.trx` (local, git-ignored) in the per-feature table;
      - one sentence on `ac-results.md` path cleaning;
    - `WORKFLOW.md` §3.1:
      - two refs rows;
      - the TRX row text;
    - `DESIGN.md` §9 bullet:
      - init writes the blocks and upgrade refreshes them;
      - a decision-log row dated 2026-11-16 for decisions 1–8 (as amended);
    - `TRACKER.md`: row 12 and a notes entry.

### Verification

16. **Test suite:** `uv run pytest -q --tb=short` on CPython 3.14, then on 3.11 with
    `uv run --python 3.11 pytest -q --tb=short`.
17. **Opt-in runs:**
    - the real deploy test (specify on PATH);
    - `SPECKIT_AC_DOTNET_E2E=1` for `test_e2e_sample.py` (A05).
18. **Mutation spot-checks.** Each is applied and reverted by hand, and each must fail at least one test:
    - **A02:**
      - drop the TRX line;
      - `upgrade` skips `write_git_blocks`;
      - `write_block` always rewrites (remove the `new == old` return);
      - doctor treats a differing block as `ok`;
    - **A03:**
      - pass 1 without `IGNORECASE` (caught by the lower-case row and the fixture's upper-cased root);
      - pass 1 accepts only `\` as the separator (caught by the `/` row);
      - scrub inside `clean_stack` before `in_ac_project` (caught by the fixture test from another folder);
      - pass 2 ends unquoted paths at the first whitespace (caught by the `Anna Maria Rossi` row);
    - **A04:** `self.refs` put back in `folders()`.
19. **No local paths:** `git diff` is checked for local absolute paths.

## Review dispositions

### Round 1 (`12-fixes-0.1.4-bugs.review-1.md`, REVISE)

| Finding | Disposition |
|---|---|
| BLOCKER 1: the scrub-before-filter mutation is not caught | ACCEPTED: `run_script` gets a `cwd` keyword, and the fixture test runs from another folder (steps 10, 18) |
| MAJOR 1: space continuation leaks and joins paths | ACCEPTED: spec amended (user-approved). Pass 1 finds the root by its prefix; pass 2 hides up to the last separator in the region (step 8). New rows for two paths, `Anna Maria Rossi`, a root with a space, `O'Brien` |
| MAJOR 2: `resolve()` on candidates | ACCEPTED: spec amended. No resolve of candidates; the root forms are the resolved root plus the cwd form; pure tests with string roots (steps 8, 10) |
| MAJOR 3: upgrade failure while the guard is unregistered; doctor on bad input | ACCEPTED: `block_lines` names the file; an `upgrade` pre-check before any change; `write_git_blocks` wraps errors in `DeployError`; doctor checks each file in its own `try` (steps 3–6) |
| MAJOR 4: the POSIX root list blanks routes | ACCEPTED: spec amended, the list is dropped; route rows `GET /Users/42` in both modes (steps 8, 10) |
| MINOR 1: no existing `gitignore_lines` test | ACCEPTED: new tests (step 2) |
| MINOR 2: evidence line numbers, `init_scaffold` import | ACCEPTED: evidence corrected |
| MINOR 3: the upper-cased fixture conflicts with case keeping | ACCEPTED: only the root part is upper-cased (step 10) |
| MINOR 4: one mode per row; the e2e check is weaker than "no absolute path" | ACCEPTED: rows marked *both*; a drive/UNC regex check in the fixture and e2e tests (step 10) |
| MINOR 5: wrong limit note | ACCEPTED: the limit note is rewritten (step 14) |
| MINOR 6: "block updated" is printed only after success | ACCEPTED: printed right after the write (step 4) |
| MINOR 7: the judge prompt does not explain the placeholder | ACCEPTED: one sentence in `ac-test-fail-judge.md` (step 12) |

### Round 2 (`12-fixes-0.1.4-bugs.review-2.md`, REVISE)

| Finding | Disposition |
|---|---|
| MAJOR 1: UNC start, one backslash in the spec | ACCEPTED: a typo from a shell edit. The spec now says `\\server\share`, with a stricter start (server-name characters plus a share character). A regex row `"^\\d+\\.\\d+$"` stays unchanged (spec R05 and R07; plan step 8) |
| MINOR 1: row 2 case | ACCEPTED: spec row 2 reads "the root part in lower case"; plan step 10 |
| MINOR 2: lookahead wider than R05 | ACCEPTED: the plan follows R05 (no `.,;:)`); a new spec row `cwd is R.` → `cwd is [external path].` |
| MINOR 3: a root form ending in a separator | ACCEPTED: trailing separators are stripped, and a drive root needs a separator. New spec row with two root forms (`subst`); step 10 |
| MINOR 4: step 7 round trip | ACCEPTED: the config is written before the snapshot |
| MINOR 5: the judge sentence can be false | ACCEPTED: reworded to "the original path is not available to you" |
| MINOR 6: the limit note misses forms | ACCEPTED: the note lists them; the `First Last` limit is pinned by a row |
| MINOR 7: the fixture's profile path is only quoted | ACCEPTED: an unquoted profile path is added to stdout |
| MINOR 8: non-UTF-8 `.gitignore` refused | ACCEPTED: stated in the upgrade note |

### Round 3 (`12-fixes-0.1.4-bugs.review-3.md`, APPROVE)

| Finding | Disposition |
|---|---|
| MINOR 1: a root inside an earlier root's run is skipped | ACCEPTED: a pass-1 run also ends where the next root form appears. Spec R05 and new rows (Windows `;` and POSIX `,`) |
| MINOR 2: the `X:/` branch is untested | ACCEPTED: spec row `open C:/Users/u/x.json failed` |
| MINOR 3: pass 2 with `windows=False` | ACCEPTED: it runs in both modes (spec R05, POSIX bullet) |
| MINOR 4: limit note misses JSON-escaped and `\\?\UNC` paths | ACCEPTED: added to the step 14 limit note |
| MINOR 5: folder with a space below the root; `cwd is R\` | ACCEPTED: a frame's run ends only at `:line `; an empty run gives `.`. Spec rows added |
| MINOR 6: A03 names the removed rule | ACCEPTED: the spec A03 text is updated |
| MINOR 7: approval not recorded; plan header; prototype not durable | ACCEPTED: user approval recorded in the spec status; header updated. The prototype is ported into `summarize_trx.py`, and the R07 table becomes the durable test |
