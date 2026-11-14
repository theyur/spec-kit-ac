# Plan review 1 — step 11 (plan-critic)

**Verdict: REVISE** (0 BLOCKER, 1 MAJOR, 8 MINOR)

Lexer design, line pairing (`\n` and `\r\n`), frontmatter patch idempotency and the existing doctor warn counts
were checked and hold. Claims verified: `export_refs.py:81–131, 48, 231–234`; `deploy.py:29, 38, 52, 294–310,
325–352, 636, 769, 805, 876–892`; test counts (14 / 13 / 11); `fakespecify.py:141–143`; real specify writes
`source: ac:commands/<file>` on `--dev` (`01-platform-spike.results.md:68`); Claude Code skills reference lists
`argument-hint` as a `SKILL.md` frontmatter field.

## Findings

1. **[MAJOR] The real-deploy hint assertion uses the code under test as its oracle.** Plan step 7 compares each
   skill's hint with `deploy.skill_hint`. If real specify renders `metadata.source` in a way `skill_hint` does not
   parse, both sides are `None` and the test passes with no hint written; the clone's `[warn]` count also stays 1.
   A04 is the only automated proof of #10 with real spec-kit.
2. **[MINOR] No test for "flag already present, hint missing or different".** `deploy.py:303–307` returns early
   when the flag exists; plan step 4 says "flag handling stays as is" and "both edits on the lines list". A kept
   early return passes every planned test.
3. **[MINOR] `skill_hint` error paths are not pinned.** An `OSError` in `patch_skills` fails install/upgrade at
   the skills step (`deploy.py:650, 784`); a decode `ValueError` is not caught there at all (`cli.py:56` catches
   only `DeployError`); in doctor `check()` (`:812`) turns either into `[FAIL] skills`. R05/decision 4 promise the
   hint never fails anything.
4. **[MINOR] Step 6 narrows R06** to "a real file that has the flag". Symlinked or flagless skills get no hint
   warning (they do get a FAIL naming upgrade). After a user's `specify integration upgrade`, `metadata.source`
   becomes `extension:ac` (`01-platform-spike.results.md:56`) and `skill_hint` finds nothing; state the deviation.
5. **[MINOR] `zip(lines, code)` hides a broken invariant.** A length mismatch would truncate the scan silently and
   let the export pass; the script should fail loudly.
6. **[MINOR] `public_only()` and the `NON_PUBLIC` scan keep the #9 defect; the changelog wording overclaims.**
   `NON_PUBLIC` (`:40`, `:236`) fails on a literal line starting with `private`/`internal`/`file`; `public_only`
   (`:175–190`) can silently drop lines when a literal line matches `TYPE_DECL`. R10 says multi-line literals "no
   longer fail `export_refs.py`" — true for the logic check only. Spec scope is "as logic": record or hand to user.
7. **[MINOR] "Second run writes nothing" relies on mtime**, which may not change within one clock tick on Windows.
8. **[MINOR] (spec-level) R08 pre-fills `{n}` and `{report_path}`** while the template lets the critic use the
   next free number when the file exists (`speckit.ac.critic.md:199`); the old reply said "the report path".
   Needs a user decision since R08 is verbatim.
9. **[MINOR] Stale statements:** `TRACKER.md:267–268` lists multi-line literals as a known step-10 limit;
   `export_refs.py:35` says "Scanned on code_only(line)".
