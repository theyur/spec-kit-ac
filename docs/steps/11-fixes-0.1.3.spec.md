# Step 11 — Fixes for 0.1.3 (GitHub issues #9, #10, #11)

**Status:** done (2026-11-14; decisions 1–7 approved as drafted; no deviation) · **Tracker row:** 11 · **Source of truth:** `docs/DESIGN.md`

## Goal

Close the three issues of the `v0.1.3` milestone, each with regression tests:

1. **#9:** `export_refs.py` no longer reads a multi-line string literal or a `/* … */` comment as logic.
2. **#10:** the `/speckit-ac-*` skills keep their `argument-hint`, so autocomplete shows it.
3. **#11:** the critic sub-agent replies with the full pass summary, not only the path, the verdict and the
   counts.

The release of 0.1.3 is not part of this step.

## Context (inspected 2026-11-14)

- **#9.** `logic_lines()` (`export_refs.py:129–131`) applies `code_only()` to one line at a time. The
  `code_only` docstring (`:82–83`) says an unterminated literal or comment hides the rest of its line only.
  Lexer state (inside a verbatim string, a raw string with its quote run, or a block comment) is not carried to
  the next line. A later line of such a literal that holds `return`, `if (`, `while (`, … then matches `LOGIC`,
  and the export fails with "the listing contains logic".
  - Low likelihood today: ilspycmd writes constants as one-line literals with escapes, and reference assemblies
    have no bodies. Step 10 listed it as a known limit ("Out of scope").
  - Tests: `tests/test_scripts.py:707–746` (`LOGIC_MATCH`, `LOGIC_CLEAN`, `test_code_only`, all single-line).
- **#10.** All five payload commands declare `argument-hint` (`commands/speckit.ac.*.md:3`). spec-kit 1.0.2
  drops it when it renders `.claude/skills/speckit-ac-*/SKILL.md` on `--dev` installs (step 1 result 1.4,
  step 4 plan). `deploy.patch_skill_text()` (`deploy.py:294–310`) already rewrites that frontmatter to add
  `disable-model-invocation: true`. `patch_skills()` skips the write when nothing changed (`data == new`), and
  `has_skill_flag()` is used only by `doctor` (`deploy.py:888`).
  - **Conflict with DESIGN.** DESIGN §9 says the patch changes "only that key"
    (`disable-model-invocation`), and step 6 decision 7 is "No `argument-hint` patch" for that reason. This
    step reverses decision 7 (decision 1 below).
  - The installed extension holds the command files at `.specify/extensions/ac/commands/` after
    `specify extension add`. Each skill's `metadata.source` names its command (`ac:commands/speckit.ac.init.md`).
- **#11.** The critic prompt template ends with "When finished, reply with: the report path, the verdict, and
  the count of MAJOR and MINOR notes. Nothing else." (`speckit.ac.critic.md:232`). Hosts that collapse text
  written partway through a turn (the Claude desktop app) hide the main agent's step-2 pass summary once it
  goes on to verify. The user then sees the findings nowhere. The line sits outside the HARD RULES block, which
  `test_critic_rules` keeps word for word.
  - The "Finish" section already repeats every note with its outcome, and step 6 (cap reached) repeats the
    note lines before asking.

## Decisions to approve

1. **#10 reverses step 6 decision 7.** DESIGN §9 is amended: the deploy patch sets
   `disable-model-invocation: true` **and** copies `argument-hint` from the skill's command; every other byte
   stays (`metadata.source` included). A decision-log row records it.
2. **The hint comes from the installed extension** (`.specify/extensions/ac/commands/<command>.md`, found through
   the skill's `metadata.source`), not from the bundled payload. After `specify extension add` they are the
   same files, and `doctor` already works without the bundled payload (step 6 decision).
3. **The hint line is copied verbatim** (`argument-hint: "<value as written>"`), so no YAML is re-quoted. When
   the skill already has an `argument-hint` line (a future spec-kit may emit it), its value is replaced by the
   command's. A command without a hint leaves the skill's frontmatter as it is for this key.
4. **`doctor` warns** (not FAIL) when a skill lacks its command's hint or differs from it, and names
   `speckit-ac upgrade`. The hint is cosmetic; a missing flag stays a FAIL.
5. **#9 = one pass over the whole listing.** `code_only()` takes any text, carries its state across lines and
   keeps every newline, so the result has the same number of lines as the input. `logic_lines()` pairs each
   original line with its code line. Regular strings, interpolated non-verbatim strings and char literals still
   end at the end of their line (C# allows no newline in them); `//` comments end there too.
6. **#11 = the proposed reply text, without the optional part.** The critic replies with exactly the step-2
   pass summary. The main agent's instructions do not change: the Finish section and step 6 already repeat the
   notes in the turn's final message, and the critic's own window now holds the summary.
7. **Version.** The changes go under `## [Unreleased]` in `CHANGELOG.md`. The release (`0.1.3`, tag, README
   pin) is a separate release PR, as for 0.1.2.

## Requirements

### #9: multi-line literals and comments (`export_refs.py`)

- **S11-R01** `code_only(text)` works on any text, a single line or the full listing:
  - verbatim strings (`@"…"`, `$@"…"`, `@$"…"`), raw strings (`"""…"""` with any run of 3 or more quotes, any
    `$` prefix) and `/* … */` comments may span lines. Each is replaced by `""` (strings) or `" "` (comments)
    followed by one `\n` for every newline it contained;
  - regular strings, interpolated non-verbatim strings and char literals end at the closing quote or at the end
    of their line, whichever comes first; `//` comments end at the end of their line. The newline itself is
    kept;
  - an unterminated multi-line literal or comment hides the rest of the text (as today for one line).

  For a single line, every existing `test_code_only` case returns the same result as today. The docstring
  states the new rule.
- **S11-R02** `logic_lines(listing)` runs `code_only` once over the listing and returns the original lines
  (stripped, as written) whose code line matches `LOGIC`. Line pairing must hold for `\n` and `\r\n` listings.
- **S11-R03** Regression tests (pure functions, no dotnet), each through `logic_lines()` on a small listing:

  | Case | Expected |
  | --- | --- |
  | raw string constant whose second line holds `return x;` | no logic |
  | verbatim string spanning lines with `if (a)` on a later line | no logic |
  | `$@"…"` interpolated verbatim string spanning lines with `await` on a later line | no logic |
  | raw string opened by `""""` (4 quotes) holding a `"""` line, then `while (x)` inside | no logic |
  | `/* … */` comment spanning lines with `while (x)` inside | no logic |
  | a real statement on the line right after a closed multi-line literal | that line, quoted as written |
  | a real statement on the closing line of a multi-line comment, after `*/` | that line |
  | the same listings with `\r\n` line endings | same results |

  Plus `code_only` cases: a multi-line verbatim and raw string keep their newline count; a regular string
  without a closing quote ends at its line, so `return` on the next line is still code.

### #10: `argument-hint` in the skills (`deploy.py`)

- **S11-R04** `patch_skill_text(text, hint)` takes the command's hint line (or `None`):
  - sets `disable-model-invocation: true` as today;
  - with a hint: replaces an existing `argument-hint:` line, or inserts the hint before `metadata:` (before the
    closing `---` when there is none), with the frontmatter's line ending;
  - with `None`: leaves any `argument-hint` line as it is;
  - changes nothing else (`metadata.source` and the body included).
- **S11-R05** `patch_skills(root)` finds each skill's command through its `metadata.source`
  (`ac:commands/<file>`) under `.specify/extensions/ac/`, reads its frontmatter `argument-hint` line, and passes
  it to `patch_skill_text`. A missing `metadata.source` or command file means no hint (`None`): the hint is
  cosmetic and never fails install or upgrade. Re-running it on patched skills writes nothing.
- **S11-R06** `doctor`'s skills check adds one `warn` line per skill whose `argument-hint` is missing or differs
  from its command's: `<skill> lacks the command's argument-hint (run \`speckit-ac upgrade\`)`. No warning when
  the command has no hint.
- **S11-R07** Tests:
  - `patch_skill_text`: hint added before `metadata:`; hint updated when it differs; `None` keeps an existing
    line; CRLF kept; idempotent (patching patched text returns it unchanged); the existing flag tests unchanged
    in meaning.
  - `patch_skills`: on the fixture project the skill gets its command's hint; a second run writes nothing; a
    skill without `metadata.source` still gets its flag and no hint.
  - `doctor`: a skill without the hint gives the warn line and no FAIL.
  - Opt-in real deploy (`test_deploy_real.py`, runs when `specify` is installed on Windows): after install and
    after upgrade every `speckit-ac-*` skill carries its command's `argument-hint`.

### #11: critic reply (`speckit.ac.critic.md`)

- **S11-R08** The last line of the critic prompt template becomes:

  ```text
  When finished, reply with exactly this pass summary and nothing else:
  Critic pass {n} ({stage}): <verdict>, <a> MAJOR, <b> MINOR — {report_path}
  MAJOR
  - MAJOR-1 <title>: <one line: what is wrong and what it breaks>
  MINOR
  - MINOR-1 <title>: <one line>
  Leave out a heading that has no notes. When earlier passes exist, add one line with the counts of the "Previous notes" table (Resolved / Partly / Unresolved).
  ```

  The HARD RULES block, the report format and the main agent's loop are unchanged.
- **S11-R09** Tests (`test_commands.py`): the template ends with the R08 text; "the count of MAJOR and MINOR
  notes. Nothing else." is gone; `test_critic_rules` and `test_critic_reports_each_pass_to_the_user` pass
  unchanged. The opt-in real deploy test asserts the deployed `speckit-ac-critic/SKILL.md` carries the R08
  first line.

### Docs

- **S11-R10** `CHANGELOG.md` `## [Unreleased]`:
  - `### Fixed`: multi-line literals and block comments no longer fail `export_refs.py` (#9); the skills show
    their argument hint in autocomplete (#10);
  - `### Changed`: the critic sub-agent replies with the full pass summary (#11);
  - an upgrade note: run `speckit-ac upgrade` to get the hints into existing installs.
- **S11-R11** `docs/DESIGN.md`: §9 bullet 1 names both patched keys; a decision-log row for decisions 1–6.
  `docs/steps/TRACKER.md` gets row 11. No local absolute path in any changed file.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S11-A01 | `uv run pytest -q --tb=short` passes on CPython 3.14 and 3.11 | all |
| S11-A02 | The R03 table and the `code_only` cases pass; going back to per-line scanning, or dropping newlines from a blanked literal, fails at least one test (mutation spot-check) | R01–R03 |
| S11-A03 | The R07 unit tests pass; not inserting the hint, not replacing a differing one, or dropping the doctor warning fails at least one test (mutation spot-check) | R04–R07 |
| S11-A04 | Opt-in real deploy test passes with `specify` 1.0.2 on Windows: hints present after install and upgrade, critic skill has the R08 line | R05, R07, R09 |
| S11-A05 | Manual: in the e2e sample (`<e2e-sample>`, a scratchpad copy), after `speckit-ac upgrade` from this checkout, typing `/speckit-ac-critic` in Claude Code shows the hint | R04, R05 |
| S11-A06 | The critic command text has the R08 reply; no other command changes | R08, R09 |
| S11-A07 | Changelog, DESIGN and tracker entries exist; no local absolute path in any changed file | R10, R11 |

## Out of scope

- The 0.1.3 release (version bump, tag, README pin, release PR) and upgrading consumer projects.
- The optional part of #11: telling the main agent to repeat every pass summary in its final message
  (decision 6).
- Longer per-command help in autocomplete (the hint is one line, as #10's scope note says).
- Holes of interpolated strings that contain string literals or newlines (`$"{ "a" }"`, C# 11 multi-line
  holes); `code_only` treats the whole literal as one string, as today.
- Fixing `argument-hint` loss caused by a user's own `specify extension add --force` or
  `specify integration upgrade` (same as the flag: `doctor` warns, `upgrade` fixes).

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | A mis-parsed multi-line literal now hides the rest of the listing, not one line, and real logic could pass unnoticed | Only verbatim/raw strings and block comments carry over; an unterminated one is a compile error, so ilspycmd never writes one. `@identifier` is not a verbatim prefix (existing case). The R03 table checks that a statement right after a closed literal is still caught |
| 2 | Claude Code ignores `argument-hint` in skill frontmatter | A01–A04 only prove the file content; A05 checks the host shows it |
| 3 | A target's spec-kit version renders skills without `metadata.source` | The skill gets no hint rather than a guessed one; the flag patch is unaffected. DESIGN §9 already relies on `metadata.source` for spec-kit's uninstall |
