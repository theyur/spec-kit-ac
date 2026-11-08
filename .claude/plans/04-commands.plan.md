# Plan — Step 4: commands and extension manifest

Spec: `docs/steps/04-commands.spec.md` (approved 2026-11-08, decisions 1–9 as drafted).

## Facts (observed in the repository or the installed tools)

- **F1** `guard.py:157–159` builds `isolated_text` (`<ac folder name>/(stepdefinitions|support)`), and
  `Guard.main()` (`:236–275`) applies it to every string of a non-write, non-shell main-agent call
  (`self.strings(self.input)`), so an `Agent` call whose prompt names `…/StepDefinitions/F001/` is
  denied today. `ac-test-writer.md`'s template names `<STEP_DEFINITIONS_DIR>/`, `<SUPPORT_DIR>/`,
  `<SHARED_SUPPORT_DIR>/`.
- **F2** `Guard.load_marker(role)` (`:280–298`) validates the marker and keeps only feature, tag, run
  and analyze; unknown keys are ignored. `aclib.write_marker` writes `role, feature, tag, run,
  analyze`; `aclib.read_marker` checks only the role.
- **F3** Spike run A: a main-agent launch is `tool_name: "Agent"`, `tool_input` keys `description`,
  `prompt`, `run_in_background`, `subagent_type`; no `agent_type` on main calls.
- **F4** `changed_files.py check` (`:52–68`) reads the marker, compares hashes, raises `AcError` on a
  breach; `main()` dispatches `snapshot` / `check <role>`.
- **F5** `summarize_trx.py main()` (`:150–177`): `--current FNNN` splits into "Current feature" and
  "Regression (other features)" sections via `section(tests, level)`.
- **F6** `tests/test_agents.py` has `template(role)` (parses the ```text block of
  `## Your task message`), `fill(...)` (mechanical filler) and `test_guard_consistency` /
  `test_fill_fails_on_an_unknown_placeholder` built on it.
- **F7** `tests/test_scripts.py::test_installed_layout_has_every_script` lists the 12 scripts
  exactly; `git_project` fixture runs `git init`; `TRX` / `trx_project` fixtures exist.
- **F8** Package version `0.1.0.dev0` (`pyproject.toml:3`); `packaging.Version` accepts it.
- **F9** Probe in the scratchpad (`step04/`, specify 1.0.2, `specify init proj --integration claude
  --script ps --non-interactive` + `specify extension add --dev ../ext`, 1.4 s total): a hook event
  given as a **list** of two entries is registered with both entries and their priorities; the
  rendered `SKILL.md` body equals the source body (whitespace at the end aside) when it uses only
  `.specify/extensions/ac/scripts/…`, `.specify/memory/…`, `.specify/extensions/ac/templates/…`
  paths and `$ARGUMENTS`; `argument-hint` is **dropped** on `--dev`; the skill `description` comes
  from the command file's frontmatter.
- **F10** spec-kit's rewrite (`agents.py:195–270`): `(^|[\s`"'(])(?:\./)?<dir>/` for every payload
  sub-folder except `commands`, plus `(^|[\s`"'(])(?:\.?/)?(scripts|templates|memory)/`.
- **F11** spec-kit spec template: `### User Story N - Title (Priority: PN)`, `**Acceptance
  Scenarios**:` then `1. **Given** …, **When** …, **Then** …`; requirements `- **FR-001**: …`;
  templates contain HTML comments.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| A1 | `Agent` launch input keeps the field names of F3 in interactive Claude Code | 0.9 | The launch rule denies every AC launch (fails closed, visible) | F3; step 7 smoke test |
| A2 | The subagent receives only `prompt`, not `description` | 0.6 | `description` is a free-text channel to the subagent | Spec out of scope; WORKFLOW §6 note; step 7 |
| A3 | The model can pass a multi-line script output into `prompt` unchanged | 0.75 | Guard denies the launch; the model must retry | Normalisation in R07 absorbs line-end/trailing-space noise; step 7 |
| A4 | `Task` is the older name of `Agent` and has the same input | 0.7 | Rule is inert for `Task` (other rules still apply) | Treated identically; harmless if unused |
| A5 | Fable is available in target projects | 0.6 | `/speckit-ac-critic` launch fails; user sees the error | Decision 8 approved; command says to report the error and ask |
| A6 | spec-kit keeps the agent files at `.specify/extensions/ac/agents/` | 0.95 | `task_message.py` fails (exit 1, visible) | Step 1 check 3.1 |

No blocking assumption (none < 0.7 with a high, silent consequence).

## Design

### `task_message.py` (S04-R06)

```
task_message.py [--feature …]
  root, cfg = aclib.root/load_config; feature = resolve_feature(arg)
  marker = aclib.read_marker(root); marker["feature"] != feature.dir -> AcError
  role = marker["role"]; agent = Path(__file__).resolve().parent.parent / "agents" / f"{role}.md"
  lines = template(agent)            # [(label, raw)] from the ```text block in "## Your task message"
  drop "Other spec inputs" if not cfg["specInputs"]; drop "Feedback to address" if
      not (runsDir/run/input-feedback.md).is_file()
  agent file missing -> AcError("agent file … not found") (explicit, so the output is `FAIL: …`)
  fill <NAME>: RUN_ID=marker.run, ANALYZE_ID=marker.analyze, FEATURE_LIST from all_features
      (computed lazily, only when the placeholder occurs: all_features fails on a stray folder under
      specs/, which must not break translate or tests-write),
      else camel(NAME) in feature.paths(), else in cfg (list -> ", "), else AcError("unknown placeholder")
  message = "\n".join(f"{label}: {value}")
  marker["taskMessage"] = message; write marker; print(message)
```

`OPTIONAL = {"Other spec inputs": …, "Feedback to address": …}` — a label in the template that is
marked optional in the agent file but not in this table is still printed (the step 3 tests already
pin the optional labels).

### Guard launch rule (S04-R07)

In `Guard.main()`, after `skill_rule()` and the `cfg is None` return:

```python
if self.tool in ("Agent", "Task"):
    kind = self.input.get("subagent_type")
    kind = kind.strip().lower() if isinstance(kind, str) else ""
    if kind in AC_ROLES:
        self.launch_rule(kind)
        return        # exempt from the step-definition text rule (its message names those folders)
```

`launch_rule(role)`: `marker = self.load_marker(role)` (now returns the marker dict; message on
failure: "No valid active run for <role> …"); `taskMessage` a non-empty string else deny;
`run_in_background` not in `(None, False)` → deny; `normalise(prompt) != normalise(taskMessage)` →
deny. Reason text: "Start AC subagents only from the /speckit-ac-* commands: prompt = the exact
output of task_message.py, run_in_background false." `normalise(s)`: CRLF/CR → LF, `rstrip()` each
line, strip leading/trailing newlines. Non-string prompt → deny. Main-agent denies are not logged
(unchanged behaviour).

### Marker end (S04-R08)

`changed_files.check()`: after the snapshot exists and the marker's role matches (the existing
usage checks, which keep the marker), the hash comparison and the breach report run inside
`try: … finally: (root / aclib.MARKER).unlink(missing_ok=True)`. A usage error (no snapshot, another
role, broken config) keeps the marker, so the user can fix the call without a new run folder.
The docstring states the order `run script → task_message.py → snapshot → subagent → check`.

### `summarize_trx.py --only-current` (S04-R16)

Requires `--current` (else `AcError`). The regression section becomes one line:
`Not part of this analysis (--current): N result(s) of other features (passed P · failed F · pending
Q · skipped S); not passed: F002/AC-001, F002/AC-002.` (`none` if all passed). Stdout counts unchanged.

### `check_acceptance.py` (S04-R10)

- Strip HTML comments (`<!-- … -->`, DOTALL) from `spec.md` and `acceptance.md` first.
- spec: `FR = ^\s*[-*]\s*\*\*(FR-\d{3,})\*\*`; stories: `^###\s+User Story\s+(\d+)\b` up to the next
  `^#{2,3}\s`; inside, after a line containing `Acceptance Scenarios`, numbered items
  `^\s*(\d+)\.\s` → `US<N>-AS<M>`.
- acceptance: section `## Acceptance criteria` up to the next `^##\s`; each `^###\s+(.*)` must match
  `^(AC-\d{3,})\s*\(([^)]*)\)\s*(.*)$`; refs split on `;` or `,`; body lines with
  `^\s*(?:[-*]\s+)?(?:\*\*)?(Given|When|Then|And|But)\b`; samples from lines
  `^\s*(?:[-*]\s+)?Golden samples?:` with backticked names.
- Coverage: section `## Coverage` table rows `| ref | … |`; a **scenario** counts as not testable when
  its row contains `Not testable through the API:` followed by non-empty text. An FR is never
  exempt (spec R09 as amended; DESIGN §3); the template's instruction comment says so.
- Findings (exit 1, `FAIL: N problem(s) in <acceptance path>` on stderr, one finding per stdout
  line): missing file, no items, bad heading, duplicate id, no refs, unknown ref, no `When`, no `Then`,
  FR not covered, scenario neither covered nor not testable, sample missing or containing `..`/absolute.
  Success: `OK: <n> item(s); <f> FR and <s> scenario(s) covered, <x> not testable`.

### `acceptance.md` template (S04-R09)

`payload/templates/acceptance-template.md`: title `# Acceptance criteria: [feature name]`, line
`**Feature**: specs/[NNN-name] · **Tag**: F[NNN] · **Spec**: spec.md`, an HTML-comment instruction
block (concrete literals, one behaviour per item, refs, samples by name relative to
`Samples/F[NNN]/`, never content from `CLAUDE.md`/`plan.md`/code; delete this comment), `## Coverage`
table with sample rows `FR-001`, `FR-002`, `US1-AS1`, `US1-AS2`, `US1-AS3` (not testable row), and
`## Acceptance criteria` with `### AC-001 (FR-001; US1-AS1) [title]` and `### AC-002 (FR-002;
US1-AS2) [title]`, each with `- Given` / `- When` / `- Then` lines, AC-002 with `- Golden sample:
\`[file]\`` … — the example sample line is written as an HTML comment so the template itself passes
the check against the test's sample spec without a sample file. (The template is structurally valid
so that the check test can run it.)

### `extension.yml` (S04-R01, R02)

Block-style YAML as in F9: `schema_version: "1.0"`; `extension` (id `ac`, name `"Acceptance tests
(AC)"`, version `"0.1.0.dev0"`, description, author `"spec-kit-ac"`, license `MIT`);
`requires.speckit_version: ">=1.0.2"`; four commands; hooks `after_clarify` (critic priority 10,
translate priority 20), `after_plan`, `after_tasks` (critic), `after_implement` (tests-write); every
hook `optional: true`, a `prompt` "Type /speckit-ac-… to …", a `description`.

### Command files (S04-R03–R05, R11–R19)

Shape of each body: `## User input` with ```text `$ARGUMENTS` ```; `## Rules` (shared, R03–R05:
python command, script path form, config missing, feature resolution, lock handling table, subagent
start sequence, never read step definitions); `## Steps` (numbered, from the spec); `## Report and
stop`. The shared text is repeated in each file (skills are self-contained; a test pins the R05
order in each). tests-analyze step "other features": for each feature of `ac_feature.py --all`
other than the current one, `ac_feature.py --feature <tag>` gives `sourcesLock` / `featuresLock`;
the command verifies only the groups whose lock file exists (`verify` exits 1 for "not locked" too).
The critic command keeps the source skill's hard rules and report format verbatim,
adds the stage table rows for `ac` and `features`, the `ac` prompt rule (no code / plans / tests /
`CLAUDE.md`), the lock condition and the report-only `features` flow.

## Steps

0. **Spec status / tracker** — spec `spec-approved`, tracker row 4 `planning` (done before planning).
1. **`aclib.py`** (R06): add `camel(name)` and `template_lines(path)` (parse `## Your task message`
   ```text block; `AcError` if missing). Used by `task_message.py`; tests import nothing from it.
2. **`task_message.py`** (R06) per Design.
3. **`changed_files.py`** (R08): delete the marker after `check`; docstring order.
4. **`guard.py`** (R07): `load_marker` returns the marker dict; `launch_rule`; dispatch in `main()`;
   `normalise`. Module docstring mentions the launch rule.
5. **`summarize_trx.py`** (R16): `--only-current`.
6. **`check_acceptance.py`** (R10) per Design.
7. **`templates/acceptance-template.md`** (R09).
8. **`extension.yml`** (R01, R02).
9. **Commands** (R03–R05, R11–R19): `commands/speckit.ac.translate.md`, `speckit.ac.tests-write.md`,
   `speckit.ac.tests-analyze.md`, `speckit.ac.critic.md`.
10. **Tests** (R20):
    - `test_scripts.py`: `task_message.py` per role (exact lines from a filled template; optional
      lines dropped without `specInputs` / feedback and kept with them; `taskMessage` stored; marker
      for another feature, no marker, missing agent file, unknown placeholder (edited installed agent
      file) fail); `changed_files.py check` deletes the marker on success and on breach;
      `summarize_trx --only-current` (and without `--current` → error); a stray folder under `specs/`
      does not break `task_message.py` for the translator or writer, but does for the judge;
      **restructured existing tests**: `test_changed_files_allowlist` keeps its "no snapshot" call
      (marker kept), then success (marker deleted), then `new_run.py write` + `snapshot` before the
      breach case and again before the wrong-role case (marker kept on the usage error);
      `test_changed_files_translator` gets a fresh `new_run.py translate` + `snapshot` before its
      breach case; `check_acceptance.py` cases
      (each finding kind once, a passing file, HTML comments ignored, the template against a sample
      spec); layout list gets `check_acceptance.py`, `task_message.py`.
    - `test_guard.py`: new launch cases — allowed exact; allowed with CRLF/trailing spaces;
      denied: extra line, changed value, `run_in_background: true`, wrong role's marker, no marker,
      marker without `taskMessage`, non-string prompt; the writer's real message (from
      `task_message.py`) allowed although it names `StepDefinitions/`; `general-purpose` with that
      same prompt denied (text rule); `Task` treated like `Agent`; missing config → AC launch allowed
      (subagent's own calls are denied, existing test).
    - `test_agents.py`: `fill`/`camel` removed; `test_guard_consistency` takes the message from
      `task_message.py` (with feedback present); the unknown-placeholder test moves to
      `test_scripts.py`.
    - new `test_commands.py`: command texts (frontmatter `description` + `argument-hint`; every
      `scripts/<x>.py` exists; subcommands from a table of accepted ones; flags present in the
      script's source; F10 regexes find nothing; no `{SCRIPT}`, `{ARGS}`, `__AGENT__`; no CT strings,
      no `experiment-log`; every `/speckit-ac-<x>` is a manifest command or `init`; R05 order as a
      subsequence in the three subagent commands, with `subagent_type` = role and
      `run_in_background: false`; critic has five stages, `fable`, `high`, the hard rules); manifest
      text (version = `pyproject.toml` via `tomllib`, command names ↔ files ↔ payload files, hook
      commands ⊆ provided, every hook optional); **walks** for translate phase 2, tests-write and
      tests-analyze in a git temp project: run the script sequence (dotnet steps skipped and listed),
      launch through the real guard with the printed message (allow), a stub writes the role's
      files, `check` passes, marker gone, the same launch is denied afterwards; **real spec-kit**
      (skip without `specify`): init `--script ps`, `extension add --dev <copy of payload>`, four
      skills, bodies equal (stripped), `extensions.yml` text lists the five hook entries.
11. **Docs** (R21): WORKFLOW §3.2 (principles 3, 9), §5 drift flow, §6 `description` note and the
    existing Bash bullet extended (a marker forged by Bash now also carries `taskMessage`, so it would
    let the main agent start an AC role with any prompt; R07 closes only the tool-call routes); CONFIG
    (`taskMessage`, deletion, `acTestCommand` → `ac-results.trx`, `task_message.py`,
    `check_acceptance.py` in "Invoking the scripts"/scripts list); payload README rows; DESIGN
    decision-log row; tracker row 4 + notes.
12. **Verify** (R22): narrow test files first, then `uv run pytest -q --tb=short` on 3.14 and on the
    scratchpad 3.11 venv; mutation spot-checks (drop the launch exemption → writer launch denied;
    drop the marker deletion; break the R05 order in one command; add a bare `scripts/` to a
    command; drop an FR coverage check); no `__pycache__` in `src/`.

## Test list (spec acceptance checks)

| Check | Tests |
|---|---|
| S04-A01 | `test_commands.py` texts + manifest + real spec-kit |
| S04-A02 | `test_scripts.py` task_message cases, `test_agents.py::test_guard_consistency` |
| S04-A03 | `test_guard.py` launch cases |
| S04-A04 | `test_scripts.py` marker deletion, walk "denied afterwards" |
| S04-A05 | `test_commands.py` walks |
| S04-A06 | `test_scripts.py` check_acceptance + template |
| S04-A07 | `test_commands.py` critic text |
| S04-A08 | full suite |

## Review dispositions

### Round 1 (`04-commands.review-1.md`, REVISE: 1 MAJOR, 6 MINOR)

| # | Finding | Disposition |
|---|---|---|
| 1 | MAJOR: marker deletion breaks `test_changed_files_allowlist` and `test_changed_files_translator` | ACCEPTED — step 10 restructures both (fresh run + snapshot before each further `check`) |
| 2 | MINOR: `finally` deletes the marker on usage errors | ACCEPTED — deletion only after the usage checks (Design "Marker end"); spec R08 amended |
| 3 | MINOR: `FEATURE_LIST` must be lazy | ACCEPTED — lazy fill in Design; stray-folder test in step 10 |
| 4 | MINOR: missing agent file must be an `AcError` | ACCEPTED — explicit check in Design |
| 5 | MINOR: FR "not testable" contradiction R09/R10 | ACCEPTED — FR never exempt (DESIGN §3); spec R09 amended; template comment says so |
| 6 | MINOR: `verify` exits 1 for "not locked" too | ACCEPTED — command verifies only existing lock files of other features (Design "Command files") |
| 7 | MINOR: Bash-forged marker with `taskMessage` | ACCEPTED — WORKFLOW §6 Bash bullet extended (step 11) |

### Round 2 (`04-commands.review-2.md`, APPROVE: 5 MINOR)

| # | Finding | Disposition |
|---|---|---|
| 1 | Allowlist test: "another run" path must be `run-003`; new run before the new snapshot | ACCEPTED — step 10 |
| 2 | Critic port must not carry `knowledge base` wording (CT string test) | ACCEPTED — "project documentation" in the stage table and reference note |
| 3 | `check_acceptance.py` finding form | ACCEPTED — "line N: item heading …", "AC-NNN: reference <token> …"; no heading text |
| 4 | Marker can outlive a command (all-passed path; stop before `check`) | ACCEPTED — CONFIG row and WORKFLOW principle 9 say so |
| 5 | WORKFLOW §6: installed `agents/*.md` are the source of `taskMessage` | ACCEPTED — named in the existing bullet |
