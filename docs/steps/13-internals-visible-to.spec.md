# Step 13 — `InternalsVisibleTo` on an AC surface project (GitHub issue #15)

**Status:** done (2026-11-16; spec-approved 2026-11-16: the user asked to draft it and run `/spec-implement` in one go; decision 3, R01, R02, R04, R07, R10–R12, R14, A02 and risk 1 amended after plan-critic round 1:
one-line accessor lists, a keyword backstop, structure read on `code_only`, friend candidates by their code; decision 4, 6, R01, R04, R07, R10 amended after round 2: a kept line of
any form gets the accessor rewrite, a DLL that names the attribute must show a friend line, the whole stage after
`<refsDir>` is recreated cleans up) · **Tracker row:** 13 · **Source of truth:** `docs/DESIGN.md`

## Goal

An AC surface project may use `InternalsVisibleTo` for its own unit and component tests. Today
`export_refs.py` stops on it and `init_detect.py` reports it as a blocker. After this step:

1. the API listing shows only what code outside the assembly can use: members that are not visible outside it
   are stripped, and so are the `[assembly: InternalsVisibleTo(...)]` lines;
2. the export fails when a friend assembly is the AC project's own assembly (the one thing that would let the
   acceptance tests use internals);
3. init reports `InternalsVisibleTo` as information, not as a blocker.

The `Exe` surface (#16) and the 0.1.4 release are not part of this step.

## Context (inspected 2026-11-16)

- **Today's ban.** `export_refs.check_no_internals_visible_to()` (`export_refs.py:71–79`) scans the project's
  `.cs` / `.csproj` / `.props` / `.targets` files (build folders skipped) and the root `Directory.Build.*` for
  the text `InternalsVisibleTo`, and exits on any hit. `main()` calls it for every exported project
  (`:231`). `init_detect.internals_visible_to()` (`init_detect.py:123–131`) runs the same search, and
  `blockers()` (`:271–274`) turns a hit in a surface candidate into a blocker. `speckit.ac.init.md:45, 50`
  tells the agent to stop and ask; its testability section (`:130–131`) says "no `InternalsVisibleTo` in AC
  surface projects". The e2e sample's constitution repeats it (`tests/e2e/sample/.specify/memory/constitution.md:25`).
  The CT reference (WORKFLOW-SETUP-CT §5.2, line 223; §7, line 710) gives the reason. DESIGN.md records no
  decision on it (line 42 lists it among the things init detects).
- **The listing filter.** `public_only()` (`:177–203`) drops non-visible **type** declarations, with their
  attributes and bodies, and then the namespaces left empty. Members are not filtered. The final check
  (`:248–250`) fails the export when any listing line starts with `internal`, `private` or `file`
  (`NON_PUBLIC`). `logic_lines()` runs on the raw listing before the filter (`:245–247`).
- **Probe (scratchpad, not committed; ilspycmd 11.2.0.10050, .NET SDK 11.0.100, `net10.0` class library with
  `ProduceReferenceAssembly=true`).** The listing of a reference assembly is CRLF-separated, tab-indented, one
  declaration per line; every body is `{` / `throw null;` / `}` on their own lines; a member's attributes are
  on the lines above it at the same indent.
  - **With `InternalsVisibleTo`,** the listing adds the internal and `private protected` members of public
    types: constructors, methods, fields, `const` with its value, `static readonly` fields, events (with
    `add` / `remove` blocks), indexers, properties (expression-bodied ones as a `get` block), and the
    accessor-level forms `internal set`, `internal init` and `private protected set` inside public and
    `protected internal` properties, each accessor preceded by `[CompilerGenerated]`. It also adds one
    `[assembly: InternalsVisibleTo("...")]` line per friend. A `<InternalsVisibleTo Include=... Key=...>`
    csproj item and a `.cs` attribute give the same line form; the name and key come in one string
    (`"Lib.Other, PublicKey=0024…"`).
  - **A friend with an invalid public key** is dropped by the compiler, with no warning: it is not in the
    assembly's metadata, so it grants nothing and is not in the listing either.
  - **Even without `InternalsVisibleTo`,** the reference assembly keeps `internal virtual` and
    `internal abstract` members (`internal abstract void A();` on one line), internal default members of a
    public interface, and a public struct's `internal` and `private` fields (`private int H;`). Today each of
    these fails the export through `NON_PUBLIC`.
  - Also without `InternalsVisibleTo`: a public class that implements an internal interface lists the
    interface in its base list (`public class Impl2 : IInner`) and the explicit implementation
    (`void IInner.M()`, no modifier). That names an internal type; it is not changed here (out of scope).
- **The AC assembly.** The AC project (`cfg["acProject"]`) compiles against `<refsDir>/*.dll` in ref mode
  (`-p:AcRefMode=true`). A reference DLL whose friend list names the AC assembly lets the acceptance tests
  call internal members, even though the listing no longer shows them. `check_packages()` already evaluates
  the AC project in ref mode (`:165`).
- **Failure state.** `main()` recreates `<refsDir>` (`:217–219`), copies the DLLs (`:228–241`), then lists them
  one by one (`:243–251`). A FAIL in the listing loop leaves the DLLs and the listings written so far.
- **Init verification.** `init_verify.py` step [4] runs `export_refs.py` on the real surface (`:278`), so the
  new checks run during `/speckit-ac-init` too.
- **Tests.** `tests/test_scripts.py:760–812` (`LISTING`, `test_public_only`), `:960–1023` (`main()` with dotnet
  faked), `:1026–1044` (the source scan); `tests/test_init.py:130, 157–159, 211–218` (detection and the
  blocker). The opt-in e2e sample (`tests/test_e2e_sample.py`) runs `init_verify.py`, hence the real export.

## Decisions to approve

1. **The listing keeps a member only when code outside the assembly can use it.** Kept: `public`,
   `protected`, `protected internal`, and members with no access modifier (interface members, enum values,
   explicit interface implementations, accessors that inherit their property's access). Stripped, with their
   attributes and bodies: `internal`, `private protected` and `private`. The same rule applies to
   accessors. The filter runs on every listing, with or without `InternalsVisibleTo`, so the forms that fail
   the export today (`internal virtual` / `abstract`, internal interface members, struct fields) are fixed
   too. Stripping `private` goes beyond #15: a public struct's private fields name its implementation and
   are not usable from outside.
2. **The listing has no `[assembly: InternalsVisibleTo(...)]` line.** The friend names are the unit-test
   assemblies, nothing the writer can use.
3. **Fail closed, with two backstops.** The `NON_PUBLIC` check after the filter stays as it is (first word of
   a line). A second check fails the export when the filtered listing's code (string and char literals and
   comments blanked by `code_only`) still holds the keyword `private`, or `internal` not preceded by
   `protected `, anywhere on a line — this covers a hidden accessor inside a one-line accessor list
   (`public abstract int P { get; internal set; }`), which the first check cannot see. A stripped-access
   declaration whose shape the filter does not recognise is left in the listing, so the checks fail the
   export. (Amended after plan-critic round 1: ilspycmd writes abstract, interface and extern properties,
   indexers and events on one line; probe 2.)
4. **Friend check, from the listing.** The friend names are read from the raw listing's assembly attributes,
   which are what the compiler honours (all forms: `.cs` attributes, csproj and props items; a friend with
   an invalid key is not there and grants nothing). The name part (before the first comma, trimmed) is
   compared case-insensitively with the AC project's `AssemblyName` as MSBuild evaluates it in ref mode. A
   match fails the export, whatever the public key. When the DLL's bytes contain `InternalsVisibleToAttribute`
   (true exactly when it has a friend; probe) but the listing gives no friend, the export fails too: the
   listing's form changed and the check would pass blind. An `InternalsVisibleTo` assembly line that the check
   cannot read also fails the export.
5. **The source scan goes.** `check_no_internals_visible_to()` is removed: the listing is the authority, and
   the scan could not tell which friend is named.
6. **A failure after `<refsDir>` is recreated removes it** (build, copy and listing stages). No reference DLL
   that a check rejected or never reached (logic, non-public line, friend, a later project's failed copy)
   stays where the ref-mode build would compile against it, and no partial set of listings stays for the
   writer. Failures before that (the package check) are unchanged.
7. **Init:** `init_detect.py` keeps listing each project's `internalsVisibleTo` files, but no longer makes
   them a blocker. `speckit.ac.init.md` shows them as information (the export strips internal members and
   fails if a friend is the AC assembly). The testability bullet becomes "`InternalsVisibleTo` never names
   the AC assembly (the acceptance tests use only the public API)".
8. **Known limit, documented:** internal member names (no bodies) stay in the reference DLLs, which only the
   compiler reads (since step 12 the writer and the judge cannot read or search them). A guessed internal
   name gives CS0122 instead of CS0117, which tells the writer the name exists; the same holds for internal
   types today.

## Requirements

### Listing filter

- **S13-R01** A new pure function in `export_refs.py` strips the members of decision 1 from a listing:
  - a declaration line is a line inside a type body whose first words are C# modifiers; its access is read
    from those words (`internal` without `protected`, any `private`, `private protected` → stripped;
    `protected internal` → kept);
  - structure (declarations, attribute lines, `{` / `}` lines) is read on the `code_only` form of the listing,
    so text inside a multi-line literal or comment is never taken for a declaration; the lines written are the
    original ones;
  - type declarations (`TYPE_DECL`) are left to `public_only()`, which runs first;
  - a stripped declaration takes with it the attribute lines directly above it at the same indent
    (`[assembly:` / `[module:` lines never), and its body, by its shape:
    - the line ends with `;`: nothing more;
    - the line ends with a one-line accessor list `{ … }` (no other brace on it): nothing more;
    - otherwise the block from the next line, which must be `{` at the same indent, to the first `}` at the
      same indent;
  - any other shape (no `;`, no one-line list, next line not `{` at the same indent, no matching `}`) leaves
    the line in place, and the filter goes on with the next line;
  - accessors (`internal set`, `internal init`, `private protected set`, and the same forms with other
    accessor keywords) are handled by the same rule at their own indent; on any other indented line that ends
    with a one-line accessor list (a kept member, with or without modifiers, such as an interface member), each hidden accessor (`internal set;`, `private protected set;`, …) is removed from the
    braces (`{ get; internal set; }` → `{ get; }`); a list the filter cannot read is left as it is;
  - where it removed something, stripping leaves at most one blank line, none right after a `{` line and none
    right before a `}` line; other lines are unchanged.
- **S13-R02** The same pass removes every line that the friend check (R04) reads as a friend line. Other
  `[assembly: …]` lines stay, even when their text mentions `InternalsVisibleTo`.
- **S13-R03** `main()` applies, for each DLL: the logic check on the raw listing (unchanged), the friend check
  (R04) on the raw listing, `public_only()`, the member filter (R01, R02), then the `NON_PUBLIC` check
  (unchanged) and the keyword check (decision 3), then writes the listing.

### Friend check

- **S13-R04** A pure function reads the friend names from a listing. A candidate is a line whose code
  (`code_only`) starts with `[`, optional spaces, `assembly`, optional spaces, `:` and contains
  `InternalsVisibleTo`. Every candidate must match `[assembly: <name>("<text>")]`, with `<name>` one of
  `InternalsVisibleTo`, `InternalsVisibleToAttribute`, each optionally prefixed by
  `System.Runtime.CompilerServices.` or `global::System.Runtime.CompilerServices.`, and `<text>` free of `"`
  and `\`. The friend is `<text>` up to its first comma, trimmed. A candidate that does not match is an
  error, reported with the line.
- **S13-R05** The export reads the AC project's `AssemblyName` in ref mode (one evaluation with
  `-p:AcRefMode=true`; it may share the `check_packages` evaluation). An empty or missing value fails the
  export. When a friend equals it (case-insensitive), the export fails:
  `FAIL: <Dll> grants InternalsVisibleTo to the AC assembly <AcName>; the acceptance tests may use only the
  public API. Remove that friend from <project>.` (or an equivalent message naming the DLL, the friend line
  and the fix). An unreadable line (R04) fails with the line quoted.
- **S13-R06** `check_no_internals_visible_to()` and the constants only it uses are removed from
  `export_refs.py`. `init_detect.py`'s own search stays (it feeds the information of R08).

### Failure state

- **S13-R07** Any failure raised after `<refsDir>` is recreated (a build or copy FAIL, the logic, friend,
  unreadable-friend, missing-friend-line, `NON_PUBLIC` and keyword checks, an unexpected exception) removes
  `<refsDir>` before the script exits; the message is unchanged and still reaches stderr with exit 1. If the
  removal itself fails, stderr gets one more line naming `<refsDir>`, the error, and that it must be deleted
  before the ref-mode build. A failure before
  `<refsDir>` is recreated leaves it as it was (as today).

### Init

- **S13-R08** `init_detect.blockers()` no longer adds an `InternalsVisibleTo` blocker. Each project keeps its
  `internalsVisibleTo` list.
- **S13-R09** `speckit.ac.init.md`:
  - Setup step 1 and the AC-surface question no longer stop or ask about `InternalsVisibleTo`; the summary
    lists a chosen surface project's `internalsVisibleTo` files as information, with one sentence: the export
    strips internal members from the listing and fails if a friend is the AC assembly;
  - the testability bullet becomes the decision 7 text.

### Tests

- **S13-R10** Member filter, on hand-written listings in ilspycmd's form:
  - stripped: method, constructor, field, `const` with its value, `static readonly` field, event with `add` /
    `remove`, indexer, expression-bodied property, multi-line property with attributes, `internal virtual`
    method, one-line `internal abstract` method, internal default member of an interface, a struct's
    `internal` and `private` fields, an internal constructor of a public nested type, `private protected`
    method;
  - accessors: `internal set`, `internal init` and `private protected set` removed (with their
    `[CompilerGenerated]`) inside a public property and inside a `protected internal` property, the property
    and its other accessor kept;
  - one-line forms: `internal abstract int P { get; }`, an internal one-line indexer and interface property
    stripped; `public abstract int P { get; internal set; }` and `protected internal abstract int P { get;
    private protected set; }` become `{ get; }`;
  - kept unchanged: `public`, `protected`, `protected internal` members, interface members without a
    modifier, enum values, an explicit interface implementation, `public abstract int P { get; set; }`;
  - `[assembly: InternalsVisibleTo(...)]` lines removed in each R04 form; other assembly attributes kept,
    one that mentions `InternalsVisibleTo` in a string included;
  - a declaration-like line inside a multi-line verbatim string is not stripped (`NON_PUBLIC` still matches it,
    since it reads original lines: fail closed, the TRACKER open item; ilspycmd prints string constants escaped
    on one line);
  - an unrecognised shape stays in the listing, and the `NON_PUBLIC` check then matches it; an unreadable
    one-line accessor list with a hidden accessor stays, and the keyword check matches it;
  - the keyword check: matches `private`, `internal`, `private protected`; not `protected internal`, a word
    inside a literal or comment, `@internal`, or `Internal` / `PrivateKey`;
  - the blank-line rule of R01, including two blank lines that `public_only()` left next to a stripped member;
  - a modifier-less one-line member `int Q { get; internal set; }` becomes `int Q { get; }`;
  - neither check matches any case above after filtering, except the verbatim-string case.
- **S13-R11** A committed fixture: the probes' C# sources and the ilspycmd 11.2 listings of their reference
  assemblies (probe 1: members and friends; probe 2: abstract, interface and extern one-line properties,
  indexers and events), both without any local path, under `tests/`. The filter on that listing leaves no `NON_PUBLIC`
  line, no `InternalsVisibleTo` line, and keeps every public and `protected internal` member name of the
  source.
- **S13-R12** Friend check:
  - names read for a plain friend, a friend with `, PublicKey=…`, the qualified and `Attribute`-suffixed
    forms;
  - a friend equal to the AC assembly fails in three separate cases: the exact name, another case, and the
    exact name with `, PublicKey=…`;
  - a friend whose name only starts with the AC assembly name (`Shop.AcceptanceTests.Extra`) passes;
  - an unreadable `InternalsVisibleTo` assembly line fails;
  - a DLL whose bytes contain `InternalsVisibleToAttribute` with a listing that has no friend line fails;
    without the bytes and without a line it passes.
- **S13-R13** `main()` with dotnet faked (the existing `fake_export_dotnet`, extended):
  - a listing with internal members and a friend that is not the AC assembly: the written listing has
    neither, and the public members are there;
  - a friend equal to the AC assembly: FAIL with the R05 message, and `<refsDir>` no longer exists;
  - a logic FAIL also removes `<refsDir>` (R07);
  - the AC `AssemblyName` is read in ref mode.
- **S13-R14** The tests of the removed source scan go (`test_scripts.py:1026–1044`); `test_init.py`'s blocker
  test changes to: a surface candidate with `InternalsVisibleTo` gives no blocker and keeps its
  `internalsVisibleTo` list. The removed test's folder cases (`Bindings/`, `objectives/` found; `bin/`,
  `obj-ref/` skipped) and the upper-case `Friends.CS` move to `init_detect.internals_visible_to()`, whose
  scan keeps those rules.
- **S13-R15** The e2e sample: `Shop.Pricing.csproj` gets `<InternalsVisibleTo Include="Shop.Pricing.Tests" />`,
  and a new source file (not touched by the fixtures) a public type with an internal member. The sample's
  constitution bullet follows decision 7. `test_e2e_sample.py` checks, after `init_verify.py`, that
  `<refsDir>/api/Shop.Pricing.cs` has no `internal` line, no `InternalsVisibleTo` and the new public member,
  and that `detected["blockers"] == []` still holds.

### Docs

- **S13-R16** `CHANGELOG.md` `## [Unreleased]`:
  - `### Changed`: an AC surface project may use `InternalsVisibleTo` (#15); the export strips members that
    are not visible outside the assembly and the friend lines, and fails if a friend is the AC assembly;
    init no longer blocks on it; a listing-stage FAIL removes `<refsDir>`;
  - `### Fixed`: the export no longer fails on `internal virtual` / `abstract` members, internal interface
    members or struct fields that reference assemblies keep without `InternalsVisibleTo`;
  - `### Known limits`: decision 8, and the internal interface in a base list.
- **S13-R17** Docs:
  - **`docs/WORKFLOW.md` §6:** decision 8 and the base-list limit;
  - **`docs/DESIGN.md`:** a decision-log row for decisions 1–8;
  - **`export_refs.py` docstring:** the member filter and the friend check;
  - **`docs/steps/TRACKER.md`:** row 13;
  - WORKFLOW-SETUP-CT stays as it is (reference copy). No local absolute path in any changed file.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S13-A01 | `uv run pytest -q --tb=short` passes on CPython 3.14 and 3.11 | all |
| S13-A02 | The R10 and R11 tests pass. Each of these mutations fails at least one test: keeping `private protected` members; stripping `protected internal` members; leaving an accessor's attribute line; keeping a hidden accessor in a one-line list; dropping the keyword check; stripping an unrecognised shape instead of leaving it; keeping the friend lines | R01–R03 |
| S13-A03 | The R12 and R13 tests pass. Each of these mutations fails at least one test: a case-sensitive friend compare; comparing the whole friend text (with `PublicKey=`); a prefix match; skipping an unreadable line; not removing `<refsDir>` on a FAIL | R04–R07 |
| S13-A04 | The R14 tests pass; no code path still exits on the text `InternalsVisibleTo` alone | R06, R08 |
| S13-A05 | Opt-in e2e sample (`SPECKIT_AC_DOTNET_E2E=1`, real dotnet and ilspycmd): init has no blocker, `init_verify.py` passes, the listing has no internal member and no friend line | R15 |
| S13-A06 | Changelog, WORKFLOW, DESIGN, init command and tracker entries exist. No local absolute path in any changed file | R09, R16, R17 |

## Out of scope

- #16 (`Exe` surface) and the 0.1.4 release.
- Internal type names in a public type's base list or explicit interface implementations (documented as a
  known limit).
- `[assembly: IgnoresAccessChecksTo(...)]` or reflection in the AC project: the C# compiler does not honour
  the first, and the guard and the writer's prompt cover the second.
- Editing WORKFLOW-SETUP-CT (reference copy).
- Making `init_detect.py` predict the friend check from source text: `init_verify.py` runs the real export.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Another ilspycmd version writes members in a shape the filter does not know (one-line bodies, attributes on the same line) | Unknown shapes stay in the listing; `NON_PUBLIC` (first word) and the keyword check (anywhere in the code) fail the export (decision 3); the fixtures pin 11.2's forms |
| 2 | The filter strips something the writer needs (a `protected internal` member, an accessor-less interface member) | R10 keeps-unchanged cases; the fixture checks every public and `protected internal` name of the source |
| 3 | The friend check misses a friend form | It reads what the compiler wrote into the assembly, not source text; an unreadable line fails |
| 4 | Removing `<refsDir>` on FAIL hides the listing a user wants to debug | The FAIL message quotes the offending lines; the user can run ilspycmd on the build's ref DLL directly |
| 5 | A member has several attributes, or an attribute the filter leaves behind | Every consecutive attribute line at the member's indent goes with it (R10 has two stacked attributes). ilspycmd writes each attribute on one line, string arguments escaped. A left-over attribute line holds no access keyword, so it cannot hide a non-public declaration from `NON_PUBLIC` |
