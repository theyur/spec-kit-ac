# Review 3 — plan-critic (Opus 5.5, high; user's choice for this round) — Step 13

**Verdict: APPROVE** (0 BLOCKER, 0 MAJOR, 4 MINOR; all fail closed or cosmetic)

The critic hit its 20-turn limit once and was asked to report from what it had checked.

Every requirement R01–R17 maps to a plan step. Round-2 fixes hold: verbatim exemption matches R10 / decision 3; the
modifier-less rewrite never removes a member-level keyword, and a hidden line `MEMBER_DECL` misses keeps its keyword
for the keyword check; step 11 covers every A02 / A03 mutation; `export()` wraps build, copy and listing, with
`main()`'s first `rmtree(ignore_errors=True)` outside it; the `rmtree` patch keys on `ignore_errors`. Hand trace of the
planned algorithm on `ivt\with.cs` and `ivt2\listing2.cs`: every hidden form stripped, `[Obsolete]` and
`[CompilerGenerated]` go with their members, the `public_only` double blank collapses to one, `PiProp` / `Pi` stay,
P1 / P4 become `{ get; }`, P3 / Q1 / Q3 / E1 / E3 / X unchanged; no keyword-check false positive; `FRIEND_CANDIDATE`
matches only the friend lines; the fake DLL bytes (`test_scripts.py:943`) do not trigger the bytes backstop.

## Findings

1. **[MINOR] R07's "unexpected exception" cleanup has no test**: narrowing `except BaseException` to `except
   SystemExit` passes every planned test.
2. **[MINOR] The one-line rewrite needs `code[i] == lines[i]`**, so a kept line with a literal before the list
   (`public abstract int this[string k = "x"] { get; internal set; }`) cannot be rewritten and fails the export (closed).
   Fix: compare only the tail from the last `{`.
3. **[MINOR] Two departures from R01's wording**: hidden-line stripping does not check "no other brace on it"; the
   rewrite rebuilds every readable list even when it drops nothing, changing spacing ("other lines are unchanged").
4. **[MINOR] stderr order**: `remove_refs` prints "Also: could not remove …" before the `FAIL:` line that Python
   prints at exit.

## Not finished by the critic

- Invalid-key-only friend and the bytes backstop — **checked by the main agent afterwards (probe 3, scratchpad
  `ivt3`)**: a DLL whose only friend has an invalid key has no `InternalsVisibleToAttribute` in its bytes, no friend
  line, and no internal member in the listing. No false positive.
- e2e file lists (`make_sample.py`, `stage.py`, `check_stage.py`), `tests/test_commands.py`, CRLF input to
  `visible_members` (only direct callers; `run()` gives LF): left to plan steps 8 and 9.
