# Plan — Step 11: fixes for 0.1.3 (issues #9, #10, #11)

Spec: `docs/steps/11-fixes-0.1.3.spec.md` (approved 2026-11-14, decisions 1–7 as drafted).

## Evidence (inspected)

- `src/speckit_ac/payload/scripts/export_refs.py`:
  - `code_only(line)` (`:81–126`) walks one line: `//` → `break`; `/*` → skip to `*/` or end, emit `" "`; `'` →
    skip escapes to `'`, emit `''`; `STRING_START` (`:44`, `([$@]*)("+)`) → verbatim (`@` in prefix, `""`
    escape), raw (3+ quotes, ends at the same quote run), else regular (`\` escapes); each emits `""`.
  - `logic_lines(listing)` (`:129–131`) = `[line.strip() for line in listing.splitlines() if LOGIC.search(code_only(line))]`.
  - The only caller is `main()` (`:231–234`): `listing = run("dotnet", "tool", "run", "ilspycmd", …)`.
    `run()` uses `subprocess.run(..., text=True)`, so the listing has `\n` line endings (universal newlines).
  - `public_only()` and the `NON_PUBLIC` scan use `splitlines()` on their own; untouched.
- `tests/test_scripts.py:707–746`: `LOGIC_MATCH` (14), `LOGIC_CLEAN` (13) run through `logic_lines` wrapped in
  `namespace A\n{\n…\n}\n`; `test_logic_lines_quote_the_original_line`; `test_code_only` (11 single-line cases,
  among them `('a = "unterminated return', 'a = ""')` and `("/* if (a) */ x", "  x")`).
- `src/speckit_ac/deploy.py`:
  - `SKILL_FLAG = "disable-model-invocation: true"` (`:52`), `EXT = ".specify/extensions/ac"` (`:29`),
    `SKILLS = ".claude/skills"` (`:38`).
  - `patch_skill_text(text)` (`:294–310`): finds the frontmatter (`---` … `---`), the line ending from line 0,
    sets an existing flag line in place or inserts it before `metadata:` (else before the closing `---`).
  - `patch_skills(root)` (`:325–352`): checks links, reads each `SKILL.md` through its link, writes
    `patch_skill_text(...)`; skips the write when the file is real and unchanged. Called by `install` (`:636`)
    and `upgrade` (`:769`), both after `specify_add`, inside the undo `try`.
  - `doctor.c_skills()` (`:876–892`): FAIL for a symlink or a missing flag (`has_skill_flag`), else one `ok`
    line. `line("warn", …)` prints `[warn] …` (`:805`).
- `tests/fakespecify.py:124–152` (`FakeHost.add`): copies the payload to `.specify/extensions/ac/`, renders
  each skill with `name`, `description`, `compatibility`, `metadata` (`source: ac:commands/<file>`) and **no**
  `argument-hint` — the same keys as real specify 1.0.2 on `--dev`.
- `tests/test_deploy.py`:
  - `SKILL_TEXT` + five `patch_skill_text` tests (`:229–262`) call it with one argument;
  - `test_patch_skills_makes_real_files` (`:265`) compares with `deploy.patch_skill_text(target)`;
  - `test_doctor_passes_after_install_and_writes_nothing` (`:540`) asserts no `[FAIL]` and one specific warn.
- `tests/test_deploy_real.py`: skipped unless `specify` is on PATH on Windows (it is here: specify 1.0.2).
  `test_clone_upgrade_uninstall` (`:83–115`) asserts `out.count("[warn]") == 1` on a clone's doctor; after the
  change the hint must be present in a clone, or that count breaks.
- Payload commands: all five have `argument-hint: "…"` on line 3 (`commands/speckit.ac.*.md`).
  `tests/test_commands.py:125` asserts each command frontmatter is exactly `{description, argument-hint}`.
- `src/speckit_ac/payload/commands/speckit.ac.critic.md:232`: the template's last line. `test_critic_rules`
  (`test_commands.py:293`) checks the HARD RULES block; `test_critic_reports_each_pass_to_the_user` (`:308`)
  reads the step-2 ```` ```text ```` block that follows "pass summary** in its own message" — the first such
  block, not the template's.
- `docs/DESIGN.md` §9 bullet "Human-only `/speckit-ac-*` skills", item 1: "changing only that key".
  Decision log ends with the 2026-11-12 step 10 row.
- `CHANGELOG.md`: `## [Unreleased]` holds `_Nothing yet._`.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| 1 | Claude Code reads `argument-hint` from a skill's `SKILL.md` frontmatter and shows it in autocomplete | 0.85 | #10 changes files but not what the user sees | Spike 1.4 saw spec-kit emit it on non-`--dev` paths (it targets Claude). Spec A05 checks the host manually |
| 2 | ilspycmd output reaches `logic_lines` with `\n` line endings | 0.95 | Line pairing off by `\r` | `run()` uses `text=True`; the new code pairs on `\n` and strips each line, so `\r\n` works too (tested) |
| 3 | Real specify 1.0.2 writes `metadata.source: ac:commands/<file>` into every `--dev` skill | 0.95 | No hints after a real install | DESIGN §9 relies on it; `test_patch_skills_makes_real_files` asserts it for the fake; A04 real test asserts the hint |
| 4 | `.specify/extensions/ac/commands/*.md` exist after `specify extension add --dev` | 0.95 | No hints | Step 6 probe ("every payload file"); A04 |
| 5 | A C# raw string with N opening quotes ends at the first run of N quotes (content cannot hold N in a row) | 0.95 | A wrong end hides or exposes text | C# 11 spec; the current single-line code already relies on it |

None is blocking.

## Steps

1. **`code_only` over any text** (S11-R01). Rewrite `export_refs.code_only(text)` keeping its structure:
   - `//` → skip to the next `\n` (not consumed), emit nothing;
   - `/*` → skip to after `*/` (or the end); emit `" "` plus one `\n` per newline skipped;
   - `'` → scan to `'` or `\n` (a `\` skips the next char unless it is `\n`); emit `''`; consume the closing `'`
     only when found;
   - regular / interpolated non-verbatim string → same rule with `"`; emit `""`;
   - verbatim (`@` in the prefix) → scan to the closing `"` across newlines, `""` = escape; emit `""` plus the
     newlines;
   - raw (3+ quotes, any `$` prefix) → `find(quotes)` across newlines; emit `""` plus the newlines;
   - an unterminated verbatim/raw string or block comment runs to the end of the text, newlines kept.

   Docstring: the new rule (multi-line literals and comments carry over; regular/char literals and `//`
   end at their line; the output has the same `\n` count as the input).
2. **`logic_lines` in one pass** (S11-R02): `lines = listing.split("\n")`, `code = code_only(listing).split("\n")`;
   if `len(code) != len(lines)` raise `ValueError("code_only changed the line count")` (fails loudly instead of a
   short scan; review 1 F5); return `[l.strip() for l, c in zip(lines, code) if LOGIC.search(c)]`. The `LOGIC`
   comment (`:35`, "Scanned on code_only(line)") becomes "Scanned on code_only(listing), line by line" (F9). The
   module docstring ("outside string literals and comments") stays true.
3. **#9 tests** (S11-R03) in `tests/test_scripts.py`, after `test_code_only`:
   - parametrized `MULTILINE_CLEAN` listings through `logic_lines` → `[]`: raw string with `return x;` on line 2;
     verbatim spanning lines with `if (a)`; `$@"…"` with `await` on a later line; `""""` raw string holding a
     `"""` line and `while (x)`; `/* … */` spanning lines with `while (x)`;
   - `MULTILINE_MATCH` listings → exactly the expected original line: `return y;` on the line after a closed
     raw string; `*/ if (b)` closing a multi-line comment (expects that line);
   - every case again with `\r\n` (a parameter that replaces `\n`);
   - `code_only` cases: newline count preserved for a multi-line verbatim and raw string and comment;
     `'a = "x\nreturn y;'` → second line still `return y;`; `"c = '\nreturn y;"` likewise.
   - Existing `LOGIC_MATCH`, `LOGIC_CLEAN`, `test_code_only` stay unchanged and must pass.
4. **`patch_skill_text(text, hint=None)`** (S11-R04) in `deploy.py`:
   - the flag goes where it goes today (an existing flag line set in place, else inserted before `metadata:` /
     the closing `---`), but **without the early return**: the hint edit always runs after it (F2);
   - then, when `hint` is given (`argument-hint: …` without line ending): replace the first frontmatter line that
     matches `argument-hint\s*:` (keep its line ending), else insert `hint + eol` before `metadata:` (else before
     the closing `---`);
   - `hint=None` leaves the key alone. Default `None` keeps every existing call and test valid.
   - Implemented by finding `close` once and doing both edits on the `lines` list (insertions shift `close`; the
     helper re-finds `metadata` after the flag insert).
5. **Command hint lookup** (S11-R05): new helpers in `deploy.py`:
   - `frontmatter(text) -> list[str] | None`: the frontmatter lines without line endings (shared by
     `has_skill_flag`'s logic and the new code);
   - `skill_hint(root, skill_text) -> str | None`: the `metadata` `source:` value `ac:commands/<file>` → reads
     `root / EXT / "commands" / <file>` (no `..`, plain file name only), returns its frontmatter line matching
     `argument-hint\s*:` with trailing whitespace stripped, else `None`. Any missing piece → `None`, and so is
     any `OSError` or `UnicodeDecodeError` while reading the command (caught inside `skill_hint`), so the hint can
     never fail install, upgrade or doctor (F3).
   - `patch_skills(root)` passes `skill_hint(root, text)` to `patch_skill_text`. The skip-unchanged logic stays.
6. **`doctor` warning** (S11-R06): in `c_skills`, for every skill file that exists (a symlink is read through
   its link; a flagless skill too — F4), compare
   `skill_hint(root, text)` with the skill's own `argument-hint` line (`rstrip`, CRLF-folded); when the command
   has one and the skill's differs or is missing → `line("warn", f"{rel} lacks the command's argument-hint (run
   \`speckit-ac upgrade\`)")`. The `ok` line is still printed when no FAIL (warnings do not count as `bad`).
   Known limit (F4): after a user's own `specify integration upgrade`, spec-kit writes
   `metadata.source: extension:ac`, so `skill_hint` finds no command and no hint warning appears; that skill also
   lost its flag, so doctor already FAILs it and names `speckit-ac upgrade`, which restores both.
7. **#10 tests** (S11-R07) in `tests/test_deploy.py`:
   - `patch_skill_text(SKILL_TEXT, H)` inserts `H` before `metadata:` after the flag; with an existing different
     hint it replaces it; with `None` an existing hint stays; CRLF text gets `H\r\n`; patching the result again
     gives the same text; **a text that already has the flag but no hint (or a different one) gets the hint**
     (F2);
   - `test_patch_skills_makes_real_files` compares with `patch_skill_text(target, <init's hint line>)` and
     asserts `argument-hint: "[smoke]"` is in the skill; a second `patch_skills` run performs no write — asserted
     by monkeypatching `Path.write_bytes` to record calls, not by mtime (F7);
   - a skill whose `metadata` has no `source:` gets the flag and no hint;
   - `skill_hint` refuses `source: ac:commands/../x.md` (returns `None`); returns `None` for a command file that is
     not valid UTF-8 and for a missing one (F3);
   - `test_install_deploys_everything`: every skill carries its command's hint;
   - doctor: after install, remove the hint from one skill and fix its manifest hash → `[warn] … lacks the
     command's argument-hint`, exit 0, no `[FAIL]`.
   - `tests/test_deploy_real.py`: after install, in the clone, and after upgrade, each of the five skills
     `speckit-ac-<x>/SKILL.md` contains the exact `argument-hint: …` line read **independently** from the payload
     command `commands/speckit.ac.<x>.md` (folder-name mapping and a plain regex on the command text, not
     `deploy.skill_hint`), and that line is non-empty for all five (F1). The `[warn]` count assertion stays 1.
8. **#11 critic reply** (S11-R08): replace `speckit.ac.critic.md:232` with the R08 text, verbatim from the spec.
9. **#11 tests** (S11-R09) in `tests/test_commands.py`: new `test_critic_replies_with_the_pass_summary`: the
   template (between ````` ````text ````` and the closing `````` ```` ``````) ends with the R08 lines; the old
   "the count of MAJOR and MINOR notes. Nothing else." is absent. `tests/test_deploy_real.py`: the deployed
   `speckit-ac-critic/SKILL.md` contains "reply with exactly this pass summary and nothing else".
10. **Docs** (S11-R10, R11):
    - `CHANGELOG.md` `[Unreleased]`: replace `_Nothing yet._` with Fixed (#9, #10), Changed (#11) and the upgrade
      note. The #9 entry says the **logic check** no longer fails on multi-line literals and comments (F6);
    - `docs/DESIGN.md` §9 item 1: the patch sets the flag and copies `argument-hint` from the skill's command;
      decision-log row dated 2026-11-14 for decisions 1–6;
    - `docs/steps/TRACKER.md`: row 11 (status, links, verification), after verification; the step-10 known
      limit "multi-line literals in a listing are not stripped" (`:267–268`) is marked resolved by step 11 for the
      logic scan (F9); row 11's open items name the `NON_PUBLIC` / `public_only` per-line gap (F6);
    - spec status → done.
11. **Verification**: `uv run pytest -q --tb=short` (3.14), then with 3.11 (`uv run -p 3.11 …`, as step 10);
    mutation spot-checks A02/A03 (temporarily revert one piece, run the narrow tests, restore); grep changed files
    for local absolute paths (`E:\`, `C:\Users`). A05 (manual autocomplete check in the e2e sample) is reported as
    not run by me unless the user runs it.

## Review dispositions

### Round 1 (`11-fixes-0.1.3.review-1.md`, REVISE: 1 MAJOR, 8 MINOR)

| # | Sev | Disposition |
|---|---|---|
| F1 | MAJOR | ACCEPTED — step 7: the real-deploy test reads each command's hint independently (folder mapping + regex) and requires it non-empty |
| F2 | MINOR | ACCEPTED — step 4 drops the early return; step 7 adds the "flag present, hint missing/different" case |
| F3 | MINOR | ACCEPTED — step 5: `skill_hint` catches `OSError` / `UnicodeDecodeError` → `None`; step 7 tests both |
| F4 | MINOR | ACCEPTED — step 6 warns for every existing skill file; the `extension:ac` case is stated as a known limit covered by the flag FAIL |
| F5 | MINOR | ACCEPTED — step 2 raises `ValueError` on a line-count mismatch |
| F6 | MINOR | ACCEPTED (record only) — changelog says "logic check"; the `NON_PUBLIC` / `public_only` per-line gap goes to the tracker's open items and the report to the user. Spec scope is "as logic"; no code change |
| F7 | MINOR | ACCEPTED — step 7 counts `write_bytes` calls instead of mtime |
| F8 | MINOR | DECLINED — R08 is the approved verbatim text (decision 6). The main agent picks `n` as the next free number right before launch (`speckit.ac.critic.md:62–64`) and reads the report by that `n` in step 2, so the loop is already bound to `n`; the fallback only fires on a race. Reported to the user as a possible follow-up |
| F9 | MINOR | ACCEPTED — step 2 updates the `LOGIC` comment; step 10 updates the tracker's step-10 known limit |

### Round 2 (`11-fixes-0.1.3.review-2.md`, APPROVE: 3 MINOR)

| # | Sev | Disposition |
|---|---|---|
| R2-F1 | MINOR | ACCEPTED — step 5: the command file name must fullmatch `speckit\.ac\.[a-z0-9-]+\.md` (an allow-list, so no drive, stream, separator or `..`); step 7 also tests `C:x.md` and `x.md:s` → `None` |
| R2-F2 | MINOR | ACCEPTED — step 7: `test_doctor_folds_crlf` also asserts no "lacks the command's argument-hint" warning |
| R2-F3 | MINOR | ACCEPTED — step 10: `docs/CONFIG.md` (deploy files table) and `docs/WORKFLOW.md` (doctor / reverts) name the hint too |

## Verification (2026-11-14)

- `uv run pytest -q --tb=short` (with `--basetemp` on an NTFS drive; see the tracker note): 888 passed, 9 skipped
  on CPython 3.14.6 and on 3.11.15. The skips are the opt-in dotnet e2e tests; `test_deploy_real.py` ran against
  specify 1.0.2 (A04).
- Mutation spot-checks, 8 of 8 caught: per-line scan, literal and comment newlines dropped (A02); no hint passed,
  differing hint not replaced, early return on an existing flag, doctor warning dropped, allow-list dropped (A03).
  The allow-list mutation was missed at first (the refused targets did not exist); the test now plants readable
  targets.
- No local absolute path in any changed or new file.
- Not run: S11-A05 (the hint in Claude Code's autocomplete; manual).
