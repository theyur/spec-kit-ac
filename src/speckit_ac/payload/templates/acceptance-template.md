# Acceptance criteria: [FEATURE NAME]

**Feature**: specs/[NNN-feature-name] · **Tag**: F[NNN] · **Spec**: spec.md

<!--
  How to write this file (delete this comment when done):

  - Sources: this feature's spec.md, .specify/memory/constitution.md and the extra spec documents
    listed in .workflow/config.json. Never plan.md, research.md, data-model.md, contracts/, tasks.md,
    code, tests or CLAUDE.md.
  - One item per behaviour. Heading: `### AC-NNN (<refs>) <title>`; refs are the spec's FR-NNN and
    US<N>-AS<M> (user story N, acceptance scenario M), separated by `;`.
  - Lines start with Given / When / Then / And / But. Every value is a concrete literal
    ("the amount 10.50 EUR", not "a valid amount").
  - Use a table under "Examples:" for several input/output rows of the same behaviour.
  - A golden sample (an input or expected file too large for a line) lives in Samples/F[NNN]/ of the
    AC test project. Name it in the item with a line: - Golden sample: `file-name.json`
  - Coverage: every FR-NNN needs at least one item; an FR cannot be marked "not testable" (if it
    cannot be tested through the public API, the spec or the API must change). Every spec scenario
    needs an item or a row "Not testable through the API: <reason>".
  - Check: <python> .specify/extensions/ac/scripts/check_acceptance.py --feature [NNN]
-->

## Coverage

| Requirement / scenario | AC items | Note |
|---|---|---|
| FR-001 | AC-001 | |
| FR-002 | AC-002 | |
| US1-AS1 | AC-001 | |
| US1-AS2 | AC-002 | |
| US1-AS3 | — | Not testable through the API: [reason, e.g. "only visible in the CLI output"] |

## Acceptance criteria

### AC-001 (FR-001; US1-AS1) [Short title of the behaviour]

- Given [initial state with concrete values]
- When [one action with concrete values]
- Then [observable outcome with concrete values]

### AC-002 (FR-002; US1-AS2) [Short title of the behaviour]

- Given [initial state]
- When [action with <input>]
- Then [outcome is <result>]

Examples:

| input | result |
|---|---|
| [literal] | [literal] |
| [literal] | [literal] |
