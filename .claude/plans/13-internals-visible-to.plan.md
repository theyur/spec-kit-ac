# Plan — Step 13: `InternalsVisibleTo` on an AC surface project (#15)

Spec: `docs/steps/13-internals-visible-to.spec.md`. Probe evidence (ilspycmd 11.2.0.10050, .NET SDK 11.0.100,
`net10.0`): the spec's Context section.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| 1 | ilspycmd writes each member declaration on one line; its body is either nothing (`;`), a one-line accessor list `{ get; internal set; }` (abstract / interface / extern properties, indexers), or `{` / `throw null;` / `}` at the member's indent; attributes one per line above it at the same indent | 0.9 (probes 1 and 2) | Filter misses a shape → a hidden word stays → `NON_PUBLIC` (first word) or the keyword check (anywhere in code) fails the export | Probe listings committed as fixtures (step 6); e2e real run (step 9) |
| 2 | `run()` returns the listing with LF only (`text=True` translates CRLF) | 0.95 | Exact-match `indent + "{"` comparisons fail → members kept → export fails closed | `subprocess.run(text=True)` uses universal newlines; fixture test feeds the CRLF bytes through `str.splitlines`-equivalent path (step 6 reads the file with `newline=None`) |
| 3 | `dotnet msbuild -getItem:X -getProperty:Y` prints one JSON with both `Items` and `Properties` | 0.9 | AC `AssemblyName` read fails | Already used that way by `msbuild_json(project, "-getProperty:TargetRefPath", "-getProperty:AssemblyName")` and by `check_packages`' surface evaluation (items + property); e2e real run |
| 4 | The AC project's `AssemblyName` does not differ between ref and source mode | 0.9 | A friend naming the source-mode name slips through | The scaffold sets no `AssemblyName` (`init_scaffold.py`); MSBuild default = project file name in both modes |
| 5 | A friend with an invalid key never reaches the assembly metadata | 0.9 (probe) | Not a leak either way: we compare names regardless of key | Probe: invalid keys absent from both DLLs' bytes; valid key present |
| 6 | Removing `<refsDir>` after a listing-stage failure breaks no caller | 0.85 | `init_verify` [4] or a command reads refs after a failed export | `init_verify` checks the exit code only (`:278–279`); commands stop on a FAIL; step 2 greps callers |

## Steps

### 1. Friend parsing and the member filter (pure functions) — S13-R01, R02, R04

In `src/speckit_ac/payload/scripts/export_refs.py`:

- `FRIEND_CANDIDATE = re.compile(r"^\[\s*assembly\s*:.*InternalsVisibleTo")`, matched on the **code** form of
  a line (`code_only`), so a string that mentions the name is not a candidate, but `[assembly:X…` spacing
  variants are.
- `FRIEND_LINE = re.compile(r'^\[assembly: (?:(?:global::)?System\.Runtime\.CompilerServices\.)?'
  r'InternalsVisibleTo(?:Attribute)?\("(?P<text>[^"\\]*)"\)\]$')`, matched on the original line.
- `friends(listing) -> list[str]`: `lines, code = split + code_only(listing).split("\n")` (line-count guard as in
  `logic_lines`); for every candidate (by code), `FRIEND_LINE.match(original)` or raise `ValueError(line)`;
  friend = `text.split(",", 1)[0].strip()`.
- `MEMBER_DECL = re.compile(r"^(?P<indent>\t+)(?P<mods>(?:(?:public|private|protected|internal|static|readonly|"
  r"const|virtual|abstract|override|sealed|new|extern|unsafe|volatile|async|required|ref|fixed)\s+)+)")`.
- `hidden(mods)`: words = `mods.split()`; `"private" in words or ("internal" in words and "protected" not in
  words)`.
- `ONE_LINE_LIST = re.compile(r"\{(?P<body>[^{}]*)\}\s*$")` and
  `ACCESSOR = re.compile(r"^(?P<mods>(?:(?:public|private|protected|internal)\s+)*)(?:get|set|init|add|remove)$")`.
- `visible_members(listing) -> str`: `lines` and `code` (as in `friends`); walk index `i` with parallel
  `out` / `out_code` lists; decisions use `code[i]`, output uses `lines[i]`:
  - drop lines that `FRIEND_LINE` matches and whose code `FRIEND_CANDIDATE` matches (R02);
  - `m = MEMBER_DECL.match(code[i])`, not `TYPE_DECL`, `hidden(m["mods"])`: end =
    `i` when `code[i].rstrip()` ends with `;` or `ONE_LINE_LIST.search(code[i])`; else, when
    `code[i+1] == indent + "{"`, the first `j > i+1` with `code[j] == indent + "}"`; else none.
    No end → keep the line, continue at `i+1` (both checks match it).
  - with an end: pop the attribute lines (`out_code[-1].startswith(indent + "[")`); then blank handling:
    pop every trailing blank from `out`, skip every blank after the end, and append one blank unless `out` is
    empty, `out_code[-1].rstrip()` ends with `{`, or the next line's code is `}` (any indent) or the end of the
    listing;
  - any other kept line indented by at least one tab (a visible `MEMBER_DECL` line, or a modifier-less member
    such as an interface property; not a `TYPE_DECL` line) with a one-line list and `code[i] == lines[i]`
    (no literal or comment on it): split
    `body` by `;`, strip; if every non-empty token matches `ACCESSOR`, drop those whose mods are `hidden`
    (empty mods → kept) and rebuild `head + "{ " + " ".join(t + ";" for t in kept) + " }"`; else leave the
    line (the keyword check catches a hidden word);
  - other lines are copied unchanged. Returns `"\n".join(out)`.
- Block accessors need no extra code: `\t\tinternal set` matches `MEMBER_DECL`, its body is `{`…`}` at its own
  indent, and its `[CompilerGenerated]` is the attribute line above it.
- `HIDDEN_WORD = re.compile(r"(?<![@\w])private(?!\w)|(?<![@\w])(?<!protected )internal(?!\w)")` and
  `hidden_lines(listing) -> list[str]`: the stripped original lines where `NON_PUBLIC` matches the original or
  `HIDDEN_WORD` searches the code line (decision 3).

### 2. Wire into `main()` — S13-R03, R05, R06, R07

- `check_packages(cfg)`: the AC evaluation adds `-getProperty:AssemblyName`; the function returns the trimmed
  name, and raises `sys.exit("FAIL: cannot read the AssemblyName of <acProject> (ref mode)")` when it is empty
  or missing — after the drift check, so the drift test order is unchanged. Docstring updated.
- `main()`: `ac_name = check_packages(cfg)`; `exported` becomes `[(project, dll)]`; remove the
  `check_no_internals_visible_to(project)` call.
- Everything after `(refs / "api").mkdir(...)` — the build loop, the copy loop and the listing loop — moves into
  a helper `export(cfg, refs, ac_name)`, and `main()` runs it as
  `try: export(...) except BaseException: remove_refs(refs); raise`.
  `remove_refs(refs)`: `shutil.rmtree(refs)` when it exists; on `OSError as e`,
  `print(f"Also: could not remove {refs_rel} ({e}); delete it before the ref-mode build.", file=sys.stderr)`.
  One handler for `SystemExit` and any other exception (the `code_only` line-count `ValueError` included).
- Per DLL in the listing loop: `logic_lines` (unchanged) → friend check → `public_only` → `visible_members` →
  `hidden_lines` (replaces the inline `NON_PUBLIC` comprehension; same message) → write.
- Missing-friend-line backstop: `names = friends(listing)`; when `not names and b"InternalsVisibleToAttribute" in
  dll.read_bytes()`: `sys.exit(f"FAIL: {dll.name} has InternalsVisibleTo, but its listing shows no friend line; "
  "the friend check cannot run (ilspycmd output changed?).")`. Probe: the ref DLL bytes contain the attribute's
  type name exactly when the source has a friend (1 / 0 / 1 across builds with, without, with).
- `project_rel`: `project.relative_to(ROOT).as_posix()` when `project.is_relative_to(ROOT)`, else `str(project)`
  (a dependency outside the root; message only, never written to a file).
- Friend check: `try: names = friends(listing) except ValueError as e: sys.exit(f"FAIL: cannot read a friend
  assembly line in the {dll.name} listing:\n  {e}")`; any `n.casefold() == ac_name.casefold()` →
  `sys.exit(f"FAIL: {dll.name} grants InternalsVisibleTo to the AC assembly {ac_name}; the acceptance tests may "
  f"use only the public API. Remove that friend from {project_rel} (or the props file that adds it).")` where
  `project_rel` is the project path relative to ROOT, POSIX.
- Delete `check_no_internals_visible_to` and `BUILD_FOLDER` (only it uses `BUILD_FOLDER`; verified by grep:
  `export_refs.py:33, 74` only). Grep callers of refs after a failed export (assumption 6).
- Docstring: a third bullet ("Members: …") and the friend check; the "Reference assemblies drop…" paragraph
  says members not visible outside the assembly are stripped too.

### 3. Init — S13-R08, R09

- `init_detect.blockers(root, proposal)`: drop the IVT loop and the now-unused `projects` parameter; caller
  `:306` updated. `internals_visible_to()` and each project's `internalsVisibleTo` stay; its docstring loses
  "same search as export_refs" (now: "information for the init summary; the export checks the friends").
- `speckit.ac.init.md`:
  - Setup 1: the blockers bullet loses the `InternalsVisibleTo` parenthesis;
  - Setup 2 AC surface: replace "A chosen project with `internalsVisibleTo` entries: stop and ask …" with
    "A chosen project with `internalsVisibleTo` files: list them in the summary as information — the export
    strips internal members from the API listing and fails if a friend is the AC assembly.";
  - Setup 3 summary: add "the `internalsVisibleTo` files of the surface projects (information)";
  - Report testability bullet: decision 7 text.

### 4. Unit tests: filter and friends — S13-R10, R12

`tests/test_scripts.py`, next to `test_public_only`:

- `MEMBER_CASES`: parametrised `(name, listing_in, expected_out)` built with small helpers that wrap members in
  a `public class Api` body (tab-indented, block namespace). Cases per R10: stripped (method, ctor, field,
  const, static readonly, event add/remove, indexer, expression-bodied property, multi-line property with two
  stacked attributes, internal virtual, one-line internal abstract, interface internal default member, struct
  internal + private fields, public nested type's internal ctor, private protected method); accessors
  (`internal set`, `internal init`, `private protected set` in a public and in a `protected internal`
  property); kept (`public`, `protected`, `protected internal`, interface member without modifier, enum
  values, explicit `void IInner.M()`); friend lines in each R02 form removed, other assembly attributes kept;
  blank-line rule (member first in body, last in body, between two kept members, two adjacent removed).
- One-line forms (probe 2 shapes): `internal abstract int P2 { get; }`, `internal abstract int this[int i] {
  get; }`, interface `internal int Q2 { get; }` stripped; `public abstract int P1 { get; internal set; }` →
  `{ get; }`; `protected internal abstract int P4 { get; private protected set; }` → `{ get; }`;
  `public abstract int P3 { get; set; }`, `public static extern int X { get; }`, interface `int Q1 { get; }`
  unchanged; `internal abstract event EventHandler E2;` stripped.
- A multi-line verbatim const whose inner line reads `\t\tinternal int Fake;` is unchanged by `visible_members`;
  `hidden_lines` reports that inner line (it reads `NON_PUBLIC` on original lines: fail closed; the one case
  exempt from the "no hidden line left" assertion).
- Interface `int Q { get; internal set; }` (no modifier) → `int Q { get; }`.
- Blank lines: a listing where `public_only()` removed a nested internal type between two blank lines and an
  internal field follows (the `with.cs:48–80` shape): after both passes one blank line stays before the next
  kept member. Plus member first in body, last in body, between two kept members, two adjacent removed.
- `[assembly: AssemblyDescription("uses InternalsVisibleTo")]` stays (not a candidate).
- Every case also asserts `hidden_lines(out) == []`.
- Unknown shape: `\t\tinternal void M()` followed by `\t\tpublic void N();` stays, and `hidden_lines` reports it.
  `\t\tpublic int P { get; internal set; } // x` (a comment makes the code differ from the line, so the list is
  not rewritten) stays, and `hidden_lines` reports it through the keyword check.
- `hidden_lines` table: `private`, `internal`, `private protected` lines and `{ get; internal set; }` matched;
  `protected internal`, `"internal"` literal, `// internal`, `@internal`, `Internal`, `PrivateKey`,
  `InternalsVisibleTo` (only after filtering — R02 removed it) not matched.
- `friends()`: plain, `PublicKey=`, qualified, `Attribute` suffix, `global::`-qualified; `[assembly:InternalsVisibleTo("A")]`
  (no space) and `InternalsVisibleTo("A", AllInternalsVisible = true)` raise `ValueError`.

### 5. `main()` tests — S13-R05, R07, R13

- `fake_export_dotnet` gains `ac_name="App.AcceptanceTests"` and answers the AC ref-mode evaluation with
  `{"Properties": {"AssemblyName": ac_name}, "Items": {...}}`, and asserts `-getProperty:AssemblyName` is
  among its queries.
- New tests:
  - a listing with internal members + `[assembly: InternalsVisibleTo("App.Core.Tests")]`: the written listing
    has no `internal`, no `InternalsVisibleTo`, the public member present;
  - three separate failing friends (parametrised): `App.AcceptanceTests`, `app.acceptancetests`,
    `App.AcceptanceTests, PublicKey=00`: FAIL naming the DLL, the AC name and the project path;
    `artifacts/refs` does not exist afterwards;
  - `export_refs.remove_refs`'s `shutil.rmtree` made to raise `OSError` only for calls without
    `ignore_errors` (so `main()`'s first rmtree still works): stderr (capsys) has the extra "could not remove"
    line and the FAIL still exits;
  - a listing whose filtered form still has a hidden word (`\t\tpublic int P { get; internal set; } // x`):
    FAIL with "still declares non-public", refs removed (catches dropping the `hidden_lines` call);
  - a DLL whose fake bytes contain `InternalsVisibleToAttribute` with a listing without friend lines: FAIL
    "shows no friend line"; the same listing with plain bytes passes;
  - a copy-stage FAIL (second project without a ref DLL, via a two-project `with_dependencies` fake): refs removed;
  - friend `App.AcceptanceTests.Extra`: passes;
  - unreadable friend line: FAIL quoting it, refs removed;
  - logic FAIL (existing test extended): refs removed;
  - empty `AssemblyName`: FAIL before any build (no `build` call recorded).

### 6. Real-ilspycmd fixture — S13-R11

- Commit `tests/fixtures/ivt/source.cs.txt` (the probe's `Api.cs` with the valid key, plus the probe csproj's
  two items written as a comment header) and `tests/fixtures/ivt/listing.cs.txt` (ilspycmd 11.2 output of its
  ref DLL, CRLF converted to LF), and the same pair for probe 2 (`source2.cs.txt`, `listing2.cs.txt`:
  abstract / interface / extern one-line properties, indexer, events). Probe 2 asserts: `P1 { get; }`,
  `P4 { get; }`, `P3 { get; set; }`, `Q1`, `Q3`, `E1`, `E3`, `X` kept; `P2`, `this[int i]`, `E2`, `Q2`,
  `Q4` gone; `Auto`'s `internal set` block gone. Both fixtures also assert: `hidden_lines == []`, no `\n\n\n`,
  no blank line right after a `{` line or right before a `}` line. `.txt` so no C# tooling (Sonar) picks them up. Grep both for drive / UNC
  paths and the user name before adding.
- Test: `public_only` + `visible_members` on the listing → no `NON_PUBLIC` line, no `InternalsVisibleTo`;
  every kept name present (`public Api()`, `Count`, `get` of `Count`, `Name`, `Pi()`, `PiProp`, `Run()`,
  `Nested`, `X`, `Shown()`, `B()`, `protected Base()`, `G`, `public R(int A)`, `EqualityContract`, enum
  `A,`/`B`); every stripped name absent (`Seed`, `Field`, `Max`, `Ro`, `Changed`, `this[int i]`, `Expr`,
  `Multi`, `Old()`, `Pp()`, `V()`, `Gen<T>`, `InNested`, `Hidden()`, `A();` of `Base`, `int F;`, `int H;`,
  `S(int f)`, `int B` of `R`); `friends(listing)` gives the three friend names.

### 7. Init tests — S13-R14

- `test_detect_blockers`: 2 blockers; the IVT file gives none, and the surface project's
  `internalsVisibleTo == ["src/App.Core/Friends.cs"]`.
- Remove `test_internals_visible_to_found_in_folders_named_like_build_output` from `test_scripts.py` and port
  it to `test_init.py` against `init_detect.internals_visible_to()`: `bin/Debug/`, `obj-ref/` skipped;
  `Bindings/`, `objectives/` found; upper-case `Friends.CS` found.
- A test that `export_refs.py` source no longer exits on the bare text: `"InternalsVisibleTo puts internal"`
  not in the file, and no `check_no_internals_visible_to` attribute (S13-A04).

### 8. Commands text test

- If `tests/test_commands.py` pins the init command's IVT sentences, update it; add an assertion for the new
  testability bullet text.

### 9. e2e sample — S13-R15

- `tests/e2e/sample/src/Shop.Pricing/Shop.Pricing.csproj`: `<ItemGroup><InternalsVisibleTo
  Include="Shop.Pricing.Tests" /></ItemGroup>`.
- New `tests/e2e/sample/src/Shop.Pricing/PriceRounding.cs`: `public static class PriceRounding` with a
  documented `public static decimal ToCents(decimal amount)` and `internal const int Decimals = 2;`.
- New `tests/e2e/sample/tests/Shop.Pricing.Tests/PriceRoundingTests.cs` using `PriceRounding.Decimals` (the
  unit tests need the friend; the fixtures overwrite only `DiscountCalculator*.cs`, verified).
- Constitution bullet → decision 7.
- `test_e2e_sample.py`, after `init_verify.py`: read `cfg["refsDir"]/api/Shop.Pricing.cs`; assert no line
  matches `NON_PUBLIC`-like `^\s*(internal|private)\b`, `"InternalsVisibleTo" not in`, `"ToCents"` in,
  `"Decimals"` not in. `detected["blockers"] == []` already asserted.
- Check `make_sample.py` / `check_stage.py` for file lists that pin the sample's files and update them.

### 10. Docs — S13-R16, R17

- `CHANGELOG.md [Unreleased]`: Changed (#15 bullet, refs removal), Fixed (virtual/abstract/interface/struct
  forms), a "Known limits of the API listing" subsection (decision 8, base lists); Upgrade note: nothing to do.
- `docs/WORKFLOW.md §6`: two bullets after the "API names and signatures" bullet.
- `docs/DESIGN.md`: decision-log row 2026-11-16, step 13, decisions 1–8.
- Tracker row 13 and the spec status at the end (step 12). The open item at `TRACKER.md:273–276` (line-by-line
  filters vs multi-line literals) gets a note: the member filter and the friend check read structure on
  `code_only`, so they are literal-aware; `public_only()` and `NON_PUBLIC` still are not (NON_PUBLIC fails
  closed on such a line).

### 11. Verify

- `uv run pytest -q --tb=short` on 3.14 and `--python 3.11` (basetemp on C:, `-c safe.directory=*` already in
  helpers).
- Opt-in e2e: `SPECKIT_AC_DOTNET_E2E=1 uv run pytest tests/test_e2e_sample.py`.
- Mutation spot-check, one at a time (A02, A03): keep `private protected`; strip `protected internal`; leave
  the accessor attribute; strip unknown shape; keep friend lines; keep a hidden accessor in a one-line list;
  drop the keyword check (`HIDDEN_WORD`) inside `hidden_lines`; drop the `hidden_lines` call from the listing
  loop; case-sensitive compare; whole-text compare; prefix match (`startswith`); skip unreadable line; drop the
  missing-friend-line backstop; no `remove_refs` in `main()`.
- Grep the diff for local absolute paths.

### 12. Tracker and spec status

- `docs/steps/TRACKER.md` row 13 (done, verification, critic rounds), spec status `done`.

## Review dispositions

### Round 1 (REVISE; 1 BLOCKER, 1 MAJOR, 7 MINOR) — all ACCEPTED

Probe 2 (scratchpad `ivt2`, ilspycmd 11.2) confirmed the shape: `public abstract int P1 { get; internal set; }`,
`internal abstract int P2 { get; }`, `internal abstract int this[int i] { get; }`, interface `internal int Q2 { get; }`,
`public static extern int X { get; }`, all on one line; auto-properties stay multi-line. Spec amended (decision 3,
R01, R02, R04, R07, R10–R12, R14, A02, risk 1), recorded in its status line.

1. BLOCKER one-line accessor list fail-open — ACCEPTED: hidden accessors removed from one-line lists in kept
   members; new keyword backstop `HIDDEN_WORD` on the code form of every line (`hidden_lines`); probe 2 fixture.
2. MAJOR one-line internal property still fails — ACCEPTED: the one-line list is a recognised shape (stripped
   whole); the unknown-shape test uses a real unknown shape now.
3. MINOR friend backstop — ACCEPTED: candidates by code `^\[\s*assembly\s*:.*InternalsVisibleTo`, so spacing
   variants become unreadable-line FAILs instead of being skipped.
4. MINOR R02 broader than spec — ACCEPTED: removal = `FRIEND_LINE` matches only; a description mentioning it stays
   (test).
5. MINOR silent failed delete — ACCEPTED: no `ignore_errors`; an extra message line on `OSError` (test).
6. MINOR blank lines on the real listing — ACCEPTED: removal pops all trailing blanks and skips all following ones,
   then puts back at most one; fixture test asserts no `\n\n\n`, no blank after `{` or before `}` next to a strip.
7. MINOR lost regression cases — ACCEPTED: all five folder / extension cases ported to `init_detect`.
8. MINOR three equality cases — ACCEPTED: parametrised.
9. MINOR stale texts / traceback — ACCEPTED: `init_detect` docstring, TRACKER open-item note, `project_rel`
   fallback for a project outside the root.

### Round 2 (REVISE; 2 MAJOR, 6 MINOR) — all ACCEPTED

Spec amended again (decision 4, 6, R01, R04, R07, R10, R12), recorded in its status line.

1. MAJOR verbatim-string case vs `NON_PUBLIC` — ACCEPTED: `NON_PUBLIC` stays on original lines (decision 3
   unchanged); the verbatim case asserts only that `visible_members` leaves it, and that `hidden_lines` reports it
   (fail closed); it is the one exemption from "no hidden line left" (spec R10). TRACKER note names `NON_PUBLIC`.
2. MAJOR modifier-less one-line rewrite — ACCEPTED: the accessor rewrite applies to any kept indented line with a
   one-line list (not only `MEMBER_DECL` lines); test `int Q { get; internal set; }` → `int Q { get; }`.
3. MINOR missing mutations / unwired `hidden_lines` — ACCEPTED: mutation list extended; step 5 adds a `main()` case
   whose filtered listing keeps a hidden word (asserts the "still declares non-public" FAIL).
4. MINOR copy-stage leftover — ACCEPTED: the whole stage after `<refsDir>` is recreated (build, copy, listing) runs
   in `export()` under one cleanup handler; step 5 adds a copy-stage FAIL test.
5. MINOR no friend line at all — ACCEPTED: DLL bytes containing `InternalsVisibleToAttribute` with no friend line
   fail (probe: present exactly when a friend exists); tests both ways.
6. MINOR handler gaps — ACCEPTED: one `except BaseException` handler calling `remove_refs`, which reports a failed
   delete on stderr; the test patches `rmtree` to fail only without `ignore_errors`.
7. MINOR missing blank-line case — ACCEPTED: step 4 has the `public_only`-left double blank case; step 6 lists the
   fixture blank-line asserts.
8. MINOR approval of amended decisions — ACCEPTED: the final report tells the user that decision 3's keyword check,
   decision 4's bytes backstop, decision 6's wider cleanup and the `private` stripping were added during review.

### Round 3 (APPROVE; Opus 5.5 / high at the user's request; 4 MINOR) — all ACCEPTED

Probe 3 (scratchpad `ivt3`): a DLL whose only friend has an invalid key has no `InternalsVisibleToAttribute` in its
bytes, no friend line and no internal member in the listing, so the bytes backstop has no false positive there.

1. MINOR untested non-`SystemExit` cleanup — ACCEPTED: step 5 adds a test that patches `logic_lines` to raise
   `ValueError` inside `export()`; refs removed, the `ValueError` propagates.
2. MINOR rewrite blocked by a literal earlier on the line — ACCEPTED: the rewrite needs only the tail from the last
   `{` to agree between code and original (`code[k:] == line[k:]`, `k = code.rfind("{")`), and edits that tail.
3. MINOR R01 wording — ACCEPTED: `ONE_LINE_LIST` counts as a one-line list only when the code line has exactly one
   `{` and one `}`; the rewrite writes the line only when it removed an accessor (other lines byte-identical).
4. MINOR stderr order — ACCEPTED: for a `SystemExit`, the failed-delete note is appended to the exit message
   (`raise SystemExit(f"{stop.code}\nAlso: …")`); for any other exception it is printed to stderr before the
   re-raise. Test asserts the note follows the FAIL line.
