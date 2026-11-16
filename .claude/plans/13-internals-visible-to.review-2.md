# Review 2 — plan-critic (Fable, high) — Step 13

**Verdict: REVISE** (2 MAJOR, 6 MINOR)

Round-1 fixes traced by hand on `with.cs` / `without.cs`: fix 1 holds for lines that start with a modifier, no
fail-open path found; after filtering `internal` is left only in `protected internal`, so the keyword check has no
false positive on either real listing; fixes 2, 4, 6–9 hold; fix 3 holds for spacing variants only; fix 5 holds on the
`SystemExit` path only. Verified: `init_verify.py:278–280` returns before reading refs; the fake's AC branch at
`tests/test_scripts.py:952–953`; `.gitattributes` sets `eol=lf`; no conflict with CLAUDE.md / DESIGN.

## Findings

1. **[MAJOR] Step 1 and step 4 contradict on the verbatim-string case.** `NON_PUBLIC` runs on the original line
   (`export_refs.py:41`), so a literal's inner line `\t\tinternal int Fake;` matches it, yet step 4 asserts
   `hidden_lines(out) == []` for every case. Same conflict in the spec (decision 3 / R03 "unchanged" vs R10 "neither
   check matches"). TRACKER:273–276 records this open item; step 10's note omits `NON_PUBLIC`.
2. **[MAJOR] The one-line accessor rewrite skips members without a modifier** (only `MEMBER_DECL` lines). A public
   interface's `int Q { get; internal set; }` would stay and the keyword check fail the export: fail closed, but the
   user cannot fix it. Not probed; no test or fixture covers it.
3. **[MINOR] Step 11 lacks two A02 mutations** (hidden accessor kept in a one-line list; keyword check dropped), and
   removing the `hidden_lines` call from `main()` passes every planned test (no main() case with a hidden word left;
   no test asserts the "still declares non-public" message).
4. **[MINOR] A copy-stage failure can leave an unchecked friend DLL in `<refsDir>`**: project A copied, project B
   fails at `export_refs.py:236–239`; the source scan used to run before each copy.
5. **[MINOR] No friend line at all passes silently**: if a tool version prints no assembly attributes, `friends()`
   returns `[]` and the DLL is accepted; after R06 this is the only guard.
6. **[MINOR] Handler gaps:** the `except BaseException` branch's delete is silent on failure; step 5's blanket
   `shutil.rmtree` patch also hits `main()`'s first call at `export_refs.py:224`.
7. **[MINOR] R10's "two blank lines left by `public_only()`" case is missing** from step 4; the fixture asserts are
   only in disposition 6, not in step 6.
8. **[MINOR] The amended decision has no recorded user approval**; the final report should tell the user.

Sources: C# 8 default interface methods proposal (csharplang); Compiler Error CS0275.
