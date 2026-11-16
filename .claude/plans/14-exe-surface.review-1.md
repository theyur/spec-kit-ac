# Plan review 1 — Step 14 (plan-critic on Opus, 2026-11-16)

**Verdict: REVISE** — 0 BLOCKER · 1 MAJOR · 6 MINOR. (The critic hit its turn limit once and was asked to report
from what it had checked.)

## Findings

1. **[MAJOR] Step 3 / Assumption 5 — dropping an explicit `Microsoft.NETCore.App` is an undeclared deviation.**
   Decision 3 says "the non-implicit references, as today, plus" an implicit AspNetCore; R05 says "explicit ones are
   kept". Today `init_scaffold.py:77` copies an explicit NETCore.App; the plan's `key == BASE_FRAMEWORK` drops it
   whether implicit or not. Either declare it as a deviation for the user, or limit the skip to implicit references.
2. **[MINOR] Step 8 — the "`BASE_FRAMEWORK` skip removed" mutation is not A02's "copying the implicit
   `Microsoft.NETCore.App`".** With the skip removed an implicit NETCore.App is still dropped by the implicit clause.
   Define the mutation by its effect (put NETCore.App in `IMPLICIT_KEPT`) and confirm the "implicit NETCore.App
   dropped" row kills it.
3. **[MINOR] Step 5 — the fixture test must not reuse `filtered_fixture()` (`test_scripts.py:1015–1023`).** It
   reads `fixtures/ivt` and asserts no blank line after `{` / before `}`; the stripped worker state machine leaves
   exactly that (out of scope per the spec). Use an own loader without the blank-line asserts.
4. **[MINOR] Step 5 — "every `public` member name of the source is in the result" is not concrete.** A regex over
   the source is fragile, and the web `Program` is public only through the SDK generator. Use explicit kept / gone
   lists as `test_scripts.py:1031–1038` does.
5. **[MINOR] Step 4 — `test_config_accepts_an_exe_surface` can't tell an Exe from a library.** `init_config.build()`
   never reads the csproj. Write a real `OutputType Exe` csproj at the path so the test pins intent.
6. **[MINOR] D1 — the TFM fallback ignores the user's actual choice.** No unit tests, library on net8.0, host on
   net10.0: the proposal is net8.0; if the user picks the host the AC project cannot reference it, and the command
   asks for the TFM only when it is null (`speckit.ac.init.md:56`). Add a sentence to the command, or accept a known
   limit.
7. **[MINOR] Step 6 — the host csproj needs another SDK; the refactor touches shared code.** `csproj()` hard-codes
   `Microsoft.NET.Sdk` (`initproject.py:70`). Add an `sdk=` parameter and keep `make_solution`'s signature and
   output byte-identical.

## Not checked by the critic

`test_commands.py` style; DESIGN log and TRACKER format; `aclib.validate_config` and the guard; the internals of
`visible_members`; whether the real web ref DLL bytes name `InternalsVisibleToAttribute` (only R08 covers it); the
probe; the CHANGELOG wording.
