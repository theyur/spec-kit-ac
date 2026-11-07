# Plan review — 01-platform-spike — round 1

**Reviewer:** plan-critic subagent · **Verdict: REVISE**

## Requirement coverage (reviewer)

| Req | Plan steps | Status |
|---|---|---|
| R01 | 2, 16 | mapped |
| R02 | 1, 2 | mapped (flags verified in `commands/init.py:262-333`) |
| R03 | 3 | mapped |
| R04 | 4 | mapped, evidence gap (F2) |
| R05 | 5, 12 | mapped except last sentence (accepted optional hook when skill not model-invocable) — unmapped (F1) |
| R06 | 6, 13 | mapped, false-FAIL risk (F1) |
| R07 | 14 | mapped |
| R08 | 7, 9–13 | mapped, one spec deviation (F5) |
| R09a–c, f | 9 | mapped |
| R09d | 11 | mapped, attribution gap (F3) |
| R09e | 10 | mapped, false-FAIL path (F4) |
| R09g | 8 | mapped |
| R09h | 12 | mapped |
| R10–R13 | 15–17 | mapped |
| A01–A07 | 15; 4+15; 6+13; 2+4+14; 9–12; 16–17; 16 | mapped |

Verified against spec-kit 1.0.2 source: `_render_skill` / `post_process_skill_content` at
`integrations/claude/__init__.py:140-239`; `extension remove --force/--keep-config`
(`extensions/_commands.py:1168-1172`); `init` uses bundled assets (`commands/init.py:343-344`).
Constraints (scratchpad only, no global installs, no bypassPermissions, explicit `--allowedTools`,
`--max-budget-usd 1`, ~10 runs) respected.

## Findings

- **[MAJOR] F1** — step 13 / R06, A03, R05 (last sentence). `extensions.yml` stores the raw id
  (`"command": command`, `extensions/__init__.py:5045`) = `speckit.ac.probe`; the core tasks template
  prints `` Command: `/{command}` `` / `` To execute: `/{command}` `` (`core_pack/commands/tasks.md:117-127`).
  Expected output is `/speckit.ac.probe`, not `/speckit-ac-probe`; grepping for the hyphen form gives a
  false FAIL. Accept both forms, record which appeared. Same output is the evidence for the unmapped
  R05 sentence (prompt names something that is not the Claude skill name) — add as a row.
- **[MAJOR] F2** — steps 2, 4, 12, 14 / R04, R05a, R07, A04. `--dev` → `link_commands=True`
  (`_commands.py:986-992`); `_register_extension_skills` writes the skill to
  `.specify/extensions/ac/.specify-dev/extension-skills/<skill>/SKILL.md` and symlinks
  `.claude/skills/<skill>/SKILL.md` to it, plain-file fallback if `os.symlink` fails
  (`extensions/__init__.py:1628-1630, 1713-1728`). (1) `find -type f` drops symlinks → false evidence;
  (2) patching writes through the link into the cache; `--force` regenerates it, `remove` may leave a
  dangling link; (3) `.specify-dev/` shows up in the extra-files diff. Fix: list `-type f -o -type l`,
  record `test -L` and `.specify-dev/`, state whether the patch is in place or replaces the link.
- **[MAJOR] F3** — step 11 / R09d. In C1–C4 the probe hook is replaced, so an empty log proves nothing;
  a mis-edited `settings.json` loads no hooks and C1 "read succeeded" looks like "onFailure ignored".
  Keep the probe hook registered as a second entry in all C runs; attribute blocks from stream-json
  tool_result only.
- **[MAJOR] F4** — steps 7, 10 / R09e. Both agents have `Read`; haiku may read `CLAUDE.md` from disk
  and quote the canary → false FAIL. Check the hook log for `Read` by spike-agent/spike-control during
  run B and invalidate, or give run-B agents no `Read`.
- **[MINOR] F5** — step 7 / R08. Logging every Skill string field exceeds "file paths and skill names".
  Log only values shaped like a skill name (`^/?[A-Za-z0-9._:-]+$`, ≤ 64 chars) plus field names.
- **[MINOR] F6** — Facts bullet 5 / R05. "step 6 the code path" is stale (step 6 = hooks static). Code
  path is already decidable: `_register_extension_skills` rebuilds frontmatter (name, description,
  compatibility, metadata + `argument-hint` only; `extensions/__init__.py:1685-1696`,
  `agents.py:439-482`), then `post_process_skill_content` injects `false` (`claude/__init__.py:228`).
  Risk 1 fails deterministically; steps 5 and 12 are mandatory; only passthrough candidate is
  `argument-hint`.
- **[MINOR] F7** — steps 12, 14 / R07, DESIGN §9. `extension add/remove` call
  `_refresh_events_and_warn`, which re-serializes `.claude/settings.json` (`events.py:2337-2369, 2497`).
  Hash `settings.json` before/after each `specify extension` command; input for the deploy merge rule.
- **[MINOR] F8** — step 14 / R07. `manager.remove` creates `.specify/extensions/.backup/ac/` for
  `*-config.yml` (`extensions/__init__.py:2951-2964`); expect it in the remove diff.
- **[MINOR] F9** — step 16 / A07. `system/init` carries `apiKeySource`; `api[_-]?key` hits every run
  log. Pre-declare that exclusion.
- **[MINOR] F10** — step 13 / R06. No check that `/speckit-tasks` actually ran (tasks.md written,
  `check-prerequisites.sh` Bash call in the hook log); without it "no hook prompt" can't be separated
  from "slash command not expanded in `-p`".
- **[MINOR] F11** — step 9 / R09c. If the hand-back tool is subject to the `tools:` whitelist, it shows
  for `Explore` but not `spike-agent`. Record both side by side; name the whitelist as candidate cause.
- **[MINOR] F12** — step 16 / R01. Every `claude -p` run writes a transcript under
  `~/.claude/projects/…`; R01 says no change to `~/.claude/`. Results doc should say so, or R01 is
  claimed too strongly.
