# Review 1 — plan-critic (Fable, high) — Step 13

**Verdict: REVISE** (1 BLOCKER, 1 MAJOR, 7 MINOR)

Requirement coverage: R03, R05, R06, R08, R09, R13, R15–R17, A01–A06 covered; R01 partly (one-line accessor lists,
blank-line rule); R02 broader than spec; R07 silent on failed delete; R10 pins a real shape as "unknown"; R12 folds
three equality cases into one; R14 loses two regression cases. Verified true: LF from `text=True`; `init_verify.py:278–280`
returns before reading refs; translate / tests-write stop on a failed export; `test_commands.py` pins none of the
changed init sentences; the plan's algorithm on the real `with.cs` leaves no NON_PUBLIC line and keeps every public
and `protected internal` name; no conflict with CLAUDE.md or DESIGN.

## Findings

1. **[BLOCKER] A non-public accessor on a one-line property passes the filter and NON_PUBLIC.** ILSpy prints a
   property or indexer on one line when every accessor has no body and no attribute (`CSharpOutputVisitor`,
   `IsPrintedAsSingleLine`, `VisitAccessor`): every abstract, non-default interface and extern property in a ref
   assembly. `public abstract int P { get; internal set; }` starts with `public`, so it is kept, and NON_PUBLIC looks
   only at the first word: fail open. Assumption 1's "never leaks" is wrong for this shape; the probe had no such
   property; the e2e regex would not see it. Needs a spec decision (R01 defines only `;` and block shapes).
2. **[MAJOR] `internal abstract int P { get; }` (and an internal interface property) still fails the export**, and the
   plan pins `\t\tinternal int X { get; set; }` as "unknown shape". Contradicts decision 1's "fixed too".
3. **[MINOR] Friend check has no backstop** if the attribute line changes form (not starting `[assembly: `); ilspycmd
   is installed unpinned (`init_scaffold.py:174`).
4. **[MINOR] `visible_members` drops every `[assembly: ` line containing the text** (e.g. an `AssemblyDescription`
   mentioning it), broader than R02; hidden coupling with `friends()`.
5. **[MINOR] `rmtree(ignore_errors=True)` hides a failed delete**; the rejected DLL could stay.
6. **[MINOR] Blank-line rule fails on the real listing:** `public_only` leaves blanks 49 and 62 adjacent after
   removing `InNested`; the member filter then strips `Field`… and two blanks stay before `public int Count`. The
   fixture test does not assert it.
7. **[MINOR] Step 7 drops `objectives/` and upper-case `Friends.CS` cases** of the remaining `init_detect` scan
   (TRACKER:190 fix).
8. **[MINOR] R12 asks for exact / other-case / `PublicKey=` equality cases; the plan has one mixed case.**
9. **[MINOR] Stale texts and a raised path:** `init_detect.py:124` docstring "same search as export_refs";
   TRACKER:273–276 open item (line-by-line filters) now also covers the new filter; `project_rel` raises for a
   dependency project outside ROOT (`with_dependencies`), giving a traceback instead of the R05 message.

Source: ILSpy `CSharpOutputVisitor.cs` (master).
