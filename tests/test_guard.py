"""Table tests for the payload guard (hooks/guard.py), run as Claude Code runs it: a subprocess fed a hook payload.

CT_CASES are the original project's guard cases, descriptions kept verbatim, paths moved to the per-feature model
(mapping in .claude/plans/02-runtime-port.plan.md). NEW_CASES cover the per-feature / cross-feature rules, the
active-run marker, the new main-agent denials and the `Skill` rule. Each case sets the lock files and the marker in
the project and in its worktree, then runs the guard.
"""

import json
import tempfile
from pathlib import Path

import pytest

from acproject import (AC, BUILD, CONFIG, FEATURE_FOLDERS, feature_setup, feature_tag, make_project,
                       run_guard, write)

T, W, J, MAIN = "ac-feature-translator", "ac-test-writer", "ac-test-fail-judge", None
ALLOW, DENY = 0, 2
NONE, SOURCES, FEATURES, BOTH = (), ("sources",), ("features",), ("sources", "features")
WT, BARE = ".claude/worktrees/wt", ".claude/worktrees/bare"  # a worktree with a config, and a folder without one
S1, S2 = "specs/001-alpha", "specs/002-beta"
RT = f"{S1}/ac/runs/translate-001"
RW = f"{S1}/ac/runs/run-001"
RA = f"{RW}/analyze-1"
DEFAULT = "default"
MARKERS = {
    T: {"role": T, "feature": S1, "tag": "F001", "run": "translate-001", "analyze": None},
    W: {"role": W, "feature": S1, "tag": "F001", "run": "run-001", "analyze": None},
    J: {"role": J, "feature": S1, "tag": "F001", "run": "run-001", "analyze": "analyze-1"},
}

# (description, agent_type, tool, input (paths as {root}/...), locked groups, expected[, cwd[, marker]])
# Locked groups apply to feature 001; "002:sources" locks feature 002.
CT_CASES = [
    # ac-feature-translator
    ("translator reads an AC .md", T, "Read", {"file_path": f"{{root}}/{S1}/acceptance.md"}, SOURCES, ALLOW),
    ("translator reads the SPEC", T, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, SOURCES, ALLOW),
    ("translator reads a KB doc", T, "Read", {"file_path": "{root}/docs/domain/overview.md"}, SOURCES, ALLOW),
    ("translator writes a feature", T, "Write", {"file_path": f"{{root}}/{AC}/Features/F001/Translate.feature"}, SOURCES,
     ALLOW),
    ("translator writes its report", T, "Write", {"file_path": f"{{root}}/{RT}/translation-report.md"}, SOURCES, ALLOW),
    ("translator writes a feature while locked", T, "Write", {"file_path": f"{{root}}/{AC}/Features/F001/A.feature"}, BOTH,
     DENY),
    ("translator edits an AC .md", T, "Edit", {"file_path": f"{{root}}/{S1}/acceptance.md"}, SOURCES, DENY),
    ("translator writes a step definition", T, "Write", {"file_path": f"{{root}}/{AC}/StepDefinitions/F001/A.cs"},
     SOURCES, DENY),
    ("translator reads a step definition", T, "Read", {"file_path": f"{{root}}/{AC}/StepDefinitions/F001/A.cs"}, SOURCES,
     DENY),
    ("translator reads an API listing", T, "Read", {"file_path": "{root}/artifacts/refs/api/App.Core.cs"}, SOURCES, DENY),
    ("translator reads src", T, "Read", {"file_path": "{root}/src/App.Core/Translator.cs"}, SOURCES, DENY),
    ("translator writes writer report", T, "Write", {"file_path": f"{{root}}/{RW}/writer-report.md"}, SOURCES, DENY),
    ("translator runs the build", T, "Bash", {"command": BUILD}, SOURCES, ALLOW),
    ("translator runs ls", T, "Bash", {"command": "ls"}, SOURCES, DENY),
    ("translator Glob in AC sources", T, "Glob", {"path": f"{{root}}/{AC}/Samples/F001", "pattern": "*.md"}, SOURCES,
     ALLOW),
    ("translator calls Skill", T, "Skill", {"skill": "verify"}, SOURCES, DENY),
    # ac-test-writer
    ("writer reads src", W, "Read", {"file_path": "{root}/src/App.Core/Translator.cs"}, BOTH, DENY),
    ("writer reads a unit test", W, "Read", {"file_path": "{root}/tests/App.Tests/X.cs"}, BOTH, DENY),
    ("writer reads an API listing", W, "Read", {"file_path": "{root}/artifacts/refs/api/App.Core.cs"}, BOTH, ALLOW),
    ("writer reads a spec input folder file", W, "Read", {"file_path": "{root}/docs/domain/overview.md"}, BOTH, ALLOW),
    ("writer reads the SPEC", W, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, BOTH, ALLOW),
    ("writer reads an AC .md", W, "Read", {"file_path": f"{{root}}/{S1}/acceptance.md"}, BOTH, ALLOW),
    ("writer reads another doc", W, "Read", {"file_path": "{root}/docs/cli.md"}, BOTH, DENY),
    ("writer reads a feature", W, "Read", {"file_path": f"{{root}}/{AC}/Features/F001/A.feature"}, BOTH, ALLOW),
    ("writer reads the csproj", W, "Read", {"file_path": f"{{root}}/{AC}/App.AcceptanceTests.csproj"}, BOTH, ALLOW),
    ("writer reads AC bin", W, "Read", {"file_path": f"{{root}}/{AC}/bin/Debug/App.Core.dll"}, BOTH, DENY),
    ("writer reads AC obj-ref", W, "Read", {"file_path": f"{{root}}/{AC}/obj-ref/x.cs"}, BOTH, DENY),
    ("writer writes a feature", W, "Write", {"file_path": f"{{root}}/{AC}/Features/F001/A.feature"}, NONE, DENY),
    ("writer writes a sample", W, "Write", {"file_path": f"{{root}}/{AC}/Samples/F001/x.bin"}, NONE, DENY),
    ("writer writes the csproj", W, "Edit", {"file_path": f"{{root}}/{AC}/App.AcceptanceTests.csproj"}, BOTH, DENY),
    ("writer edits a step definition", W, "Edit", {"file_path": f"{{root}}/{AC}/StepDefinitions/F001/A.cs"}, BOTH, ALLOW),
    ("writer writes Support", W, "Write", {"file_path": f"{{root}}/{AC}/Support/F001/Ctx.cs"}, BOTH, ALLOW),
    ("writer writes its report", W, "Write", {"file_path": f"{{root}}/{RW}/writer-report.md"}, BOTH, ALLOW),
    ("writer reads input feedback", W, "Read", {"file_path": f"{{root}}/{RW}/input-feedback.md"}, BOTH, ALLOW),
    ("writer reads ac-results", W, "Read", {"file_path": f"{{root}}/{RA}/ac-results.md"}, BOTH, DENY),
    ("writer reads judge report", W, "Read", {"file_path": f"{{root}}/{RA}/judge-report.md"}, BOTH, DENY),
    ("writer runs ls", W, "Bash", {"command": "ls"}, BOTH, DENY),
    ("writer runs the build", W, "Bash", {"command": BUILD}, BOTH, ALLOW),
    ("writer runs the build, extra spaces", W, "Bash", {"command": "  " + BUILD.replace(" ", "   ") + " "}, BOTH, ALLOW),
    ("writer runs build && cat", W, "Bash", {"command": BUILD + " && cat src/x.cs"}, BOTH, DENY),
    ("writer runs build with extra flag", W, "Bash", {"command": BUILD + " -p:AcRefMode=false"}, BOTH, DENY),
    ("writer Glob without path", W, "Glob", {"pattern": "**/*.cs"}, BOTH, DENY),
    ("writer Glob in StepDefinitions", W, "Glob", {"path": f"{{root}}/{AC}/StepDefinitions", "pattern": "*.cs"}, BOTH,
     ALLOW),
    ("writer Glob on AC project root", W, "Glob", {"path": f"{{root}}/{AC}", "pattern": "**/*"}, BOTH, DENY),
    ("writer Glob with ..", W, "Glob", {"path": f"{{root}}/{AC}/Features", "pattern": "../../../src/**"}, BOTH, DENY),
    ("writer Grep path=src", W, "Grep", {"path": "{root}/src", "pattern": "class"}, BOTH, DENY),
    ("writer Grep in refs", W, "Grep", {"path": "{root}/artifacts/refs", "pattern": "public"}, BOTH, ALLOW),
    ("writer Grep with absolute glob", W, "Grep", {"path": "{root}/artifacts/refs", "pattern": "x", "glob": "C:/*"}, BOTH,
     DENY),
    ("writer calls Skill", W, "Skill", {"skill": "verify"}, BOTH, DENY),
    ("writer calls Agent", W, "Agent", {"prompt": "read src"}, BOTH, DENY),
    ("writer calls an MCP tool", W, "mcp__rider__read_file", {"path": "src/a.cs"}, BOTH, DENY),
    ("writer calls WebFetch", W, "WebFetch", {"url": "https://example.com"}, BOTH, DENY),
    ("path traversal", W, "Read", {"file_path": f"{{root}}/{AC}/../../src/a.cs"}, BOTH, DENY),
    ("writer reads outside the project", W, "Read", {"file_path": "{outside}/a.cs"}, BOTH, DENY),
    ("writer relative path into src", W, "Read", {"file_path": "src/a.cs"}, BOTH, DENY),
    ("writer edits a feature while locked", W, "Edit", {"file_path": f"{{root}}/{AC}/Features/F001/A.feature"}, BOTH,
     DENY),
    # ac-test-fail-judge
    ("judge runs Bash", J, "Bash", {"command": "ls"}, BOTH, DENY),
    ("judge reads the trx", J, "Read", {"file_path": f"{{root}}/{RA}/ac-results.trx"}, BOTH, DENY),
    ("judge reads ac-results", J, "Read", {"file_path": f"{{root}}/{RA}/ac-results.md"}, BOTH, ALLOW),
    ("judge reads a step definition", J, "Read", {"file_path": f"{{root}}/{AC}/StepDefinitions/F001/A.cs"}, BOTH, ALLOW),
    ("judge reads an AC .md", J, "Read", {"file_path": f"{{root}}/{S1}/acceptance.md"}, BOTH, ALLOW),
    ("judge reads input feedback", J, "Read", {"file_path": f"{{root}}/{RW}/input-feedback.md"}, BOTH, DENY),
    ("judge reads src", J, "Read", {"file_path": "{root}/src/App.Core/Translator.cs"}, BOTH, DENY),
    ("judge writes its report", J, "Write", {"file_path": f"{{root}}/{RA}/judge-report.md"}, BOTH, ALLOW),
    ("judge edits a step definition", J, "Edit", {"file_path": f"{{root}}/{AC}/StepDefinitions/F001/A.cs"}, BOTH, DENY),
    # hand-back of the final message
    ("translator hands back a summary", T, "SubagentHandback", {"message": "Build success. 4 items, 1 issue (item)."},
     SOURCES, ALLOW),
    ("writer hands back a summary naming files", W, "SubagentHandback",
     {"message": f"Build success. 6 scenarios bound in {AC}/StepDefinitions/F001/TranslateSteps.cs."}, BOTH, ALLOW),
    ("writer hands back code", W, "SubagentHandback", {"message": "Done:\n```csharp\nvar x = 1;\n```"}, BOTH, DENY),
    ("writer hands back a binding", W, "SubagentHandback", {"message": '[When("a message is translated")] public void W()'},
     BOTH, DENY),
    ("judge hands back its table", J, "SubagentHandback", {"message": "| @AC-001 | TEST_FAULT | high | wrong table |"},
     BOTH, ALLOW),
    ("Explore hands back a step-definition path", "Explore", "SubagentHandback",
     {"message": f"Could not read {AC}/StepDefinitions/F001/A.cs"}, NONE, DENY),
    ("Explore hands back a summary", "Explore", "SubagentHandback", {"message": "The read was blocked."}, NONE, ALLOW),
    # main agent and other subagent types
    ("main reads a step definition", MAIN, "Read", {"file_path": f"{{root}}/{AC}/StepDefinitions/F001/A.cs"}, NONE, DENY),
    ("main reads Support, Windows path", MAIN, "Read",
     {"file_path": f"{{root}}\\{AC.replace('/', chr(92))}\\Support\\F001\\Ctx.cs"}, NONE, DENY),
    ("main writes a step definition", MAIN, "Write", {"file_path": f"{{root}}/{AC}/StepDefinitions/F001/A.cs"}, NONE, DENY),
    ("main Grep in StepDefinitions", MAIN, "Grep", {"path": f"{{root}}/{AC}/StepDefinitions", "pattern": "x"}, NONE, DENY),
    ("main Grep on AC project root", MAIN, "Grep", {"path": f"{{root}}/{AC}", "pattern": "x"}, NONE, DENY),
    ("main Glob StepDefinitions pattern", MAIN, "Glob", {"path": f"{{root}}/{AC}", "pattern": "StepDefinitions/**"}, NONE,
     DENY),
    ("main Bash cat a step definition", MAIN, "Bash", {"command": f"cat {AC}/StepDefinitions/F001/A.cs"}, NONE, DENY),
    ("main Bash in AC folder, bare path", MAIN, "Bash", {"command": "cat Support/F001/Ctx.cs"}, NONE, DENY, AC),
    ("main MCP tool, unknown field", MAIN, "mcp__rider__search_text", {"q": {"inFolder": f"{AC}/StepDefinitions"}}, NONE,
     DENY),
    ("main Agent prompt naming the folder", MAIN, "Agent", {"prompt": f"Read {AC}/Support/F001/Ctx.cs"}, NONE, DENY),
    ("Explore reads a step definition", "Explore", "Read", {"file_path": f"{{root}}/{AC}/StepDefinitions/F001/A.cs"}, NONE,
     DENY),
    ("unknown subagent reads src", "general-purpose", "Read", {"file_path": "{root}/src/a.cs"}, NONE, ALLOW),
    ("main writes a feature while unlocked", MAIN, "Write", {"file_path": f"{{root}}/{AC}/Features/F001/A.feature"}, NONE,
     DENY),
    ("main reads a feature", MAIN, "Read", {"file_path": f"{{root}}/{AC}/Features/F001/A.feature"}, BOTH, ALLOW),
    ("main edits an AC .md while unlocked", MAIN, "Edit", {"file_path": f"{{root}}/{S1}/acceptance.md"}, NONE, ALLOW),
    ("main edits an AC .md while locked", MAIN, "Edit", {"file_path": f"{{root}}/{S1}/acceptance.md"}, SOURCES, DENY),
    ("main writes a sample while locked", MAIN, "Write", {"file_path": f"{{root}}/{AC}/Samples/F001/x.bin"}, SOURCES, DENY),
    ("main writes a sample while unlocked", MAIN, "Write", {"file_path": f"{{root}}/{AC}/Samples/F001/x.bin"}, FEATURES,
     ALLOW),
    ("main edits the sources lock", MAIN, "Write", {"file_path": f"{{root}}/{S1}/ac/sources.lock"}, SOURCES, DENY),
    ("main edits the features lock", MAIN, "Write", {"file_path": f"{{root}}/{S1}/ac/features.lock"}, FEATURES, DENY),
    ("main reads src", MAIN, "Read", {"file_path": "{root}/src/App.Core/Translator.cs"}, NONE, ALLOW),
    ("main edits a doc that mentions the folders", MAIN, "Edit",
     {"file_path": "{root}/CLAUDE.md", "old_string": "a", "new_string": f"never read {AC}/StepDefinitions/"}, NONE, ALLOW),
    ("main Bash git status", MAIN, "Bash", {"command": "git status --porcelain"}, NONE, ALLOW),
    ("main Bash with cwd outside the project", MAIN, "Bash", {"command": "ls"}, NONE, ALLOW, "OUTSIDE"),
    ("main writes outside the project", MAIN, "Write", {"file_path": "{outside}/memory/a.md"}, BOTH, ALLOW),
    ("main edits outside the project", MAIN, "Edit", {"file_path": "{outside}/scratch/a.py"}, BOTH, ALLOW),
    ("main writes without a path", MAIN, "Write", {"content": "x"}, BOTH, ALLOW),
    # PowerShell (main agent only)
    ("main PowerShell, full path", MAIN, "PowerShell",
     {"command": f"Get-Content {AC.replace('/', chr(92))}\\StepDefinitions\\F001\\A.cs"}, NONE, DENY),
    ("main PowerShell, bare path in AC folder", MAIN, "PowerShell", {"command": "Get-Content Support\\F001\\Ctx.cs"}, NONE,
     DENY, AC),
    ("main PowerShell, git status", MAIN, "PowerShell", {"command": "git status --porcelain"}, NONE, ALLOW),
    ("writer PowerShell, the build command", W, "PowerShell", {"command": BUILD}, BOTH, DENY),
    ("writer writes outside the project", W, "Write", {"file_path": "{outside}/a.cs"}, BOTH, DENY),
    # worktree under .claude/worktrees/: CLAUDE_PROJECT_DIR is still the main checkout, rules apply to the worktree
    ("translator reads the SPEC in a worktree", T, "Read", {"file_path": f"{{root}}/{WT}/{S1}/spec.md"}, SOURCES, ALLOW,
     WT),
    ("translator Glob in a worktree", T, "Glob", {"path": f"{{root}}/{WT}/docs/domain", "pattern": "*.md"}, SOURCES,
     ALLOW, WT),
    ("translator writes a feature in a worktree", T, "Write",
     {"file_path": f"{{root}}/{WT}/{AC}/Features/F001/A.feature"}, SOURCES, ALLOW, WT),
    ("translator reads the main checkout from a worktree", T, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, SOURCES,
     DENY, WT),
    ("translator reads src in a worktree", T, "Read", {"file_path": f"{{root}}/{WT}/src/a.cs"}, SOURCES, DENY, WT),
    ("main writes a feature in a worktree", MAIN, "Write", {"file_path": f"{{root}}/{WT}/{AC}/Features/F001/A.feature"},
     NONE, DENY, WT),
    ("main edits an AC .md in a worktree while locked", MAIN, "Edit", {"file_path": f"{{root}}/{WT}/{S1}/acceptance.md"},
     SOURCES, DENY, WT),
    ("translator in a folder without a config", T, "Read", {"file_path": f"{{root}}/{BARE}/{S1}/spec.md"}, SOURCES,
     DENY, BARE),
]

NEW_CASES = [
    # per feature / cross feature: translator
    ("translator reads another feature's Features", T, "Read", {"file_path": f"{{root}}/{AC}/Features/F002/B.feature"},
     NONE, DENY),
    ("translator writes another feature's Features", T, "Write", {"file_path": f"{{root}}/{AC}/Features/F002/B.feature"},
     NONE, DENY),
    ("translator reads another feature's samples", T, "Read", {"file_path": f"{{root}}/{AC}/Samples/F002/x.bin"}, NONE,
     DENY),
    ("translator reads its own samples", T, "Read", {"file_path": f"{{root}}/{AC}/Samples/F001/x.bin"}, NONE, ALLOW),
    ("translator reads another feature's spec", T, "Read", {"file_path": f"{{root}}/{S2}/spec.md"}, NONE, DENY),
    ("translator reads its plan.md", T, "Read", {"file_path": f"{{root}}/{S1}/plan.md"}, NONE, DENY),
    ("translator reads the constitution", T, "Read", {"file_path": "{root}/.specify/memory/constitution.md"}, NONE,
     ALLOW),
    ("translator Glob in its feature folder", T, "Glob", {"path": f"{{root}}/{S1}", "pattern": "*.md"}, NONE, DENY),
    ("translator Grep in its spec file", T, "Grep", {"path": f"{{root}}/{S1}/spec.md", "pattern": "FR-"}, NONE, ALLOW),
    ("translator writes a feature while 002 features are locked", T, "Write",
     {"file_path": f"{{root}}/{AC}/Features/F001/A.feature"}, ("002:features",), ALLOW),
    ("translator writes another run's report", T, "Write",
     {"file_path": f"{{root}}/{S1}/ac/runs/translate-002/translation-report.md"}, NONE, DENY),
    ("translator writes a non-feature file into Features", T, "Write",
     {"file_path": f"{{root}}/{AC}/Features/F001/Steps.cs"}, NONE, DENY),
    ("writer writes a feature file into StepDefinitions", W, "Write",
     {"file_path": f"{{root}}/{AC}/StepDefinitions/F001/Extra.feature"}, NONE, DENY),
    ("writer writes a feature file into Support, upper case", W, "Write",
     {"file_path": f"{{root}}/{AC}/Support/Shared/Extra.FEATURE"}, NONE, DENY),
    ("translator reads the config", T, "Read", {"file_path": "{root}/.workflow/config.json"}, NONE, DENY),
    # writer
    ("writer edits another feature's step definition", W, "Edit",
     {"file_path": f"{{root}}/{AC}/StepDefinitions/F002/B.cs"}, BOTH, ALLOW),
    ("writer writes shared support", W, "Write", {"file_path": f"{{root}}/{AC}/Support/Shared/Ctx.cs"}, BOTH, ALLOW),
    ("writer reads another feature's AC .md", W, "Read", {"file_path": f"{{root}}/{S2}/acceptance.md"}, BOTH, DENY),
    ("writer reads another feature's samples", W, "Read", {"file_path": f"{{root}}/{AC}/Samples/F002/x.bin"}, BOTH, ALLOW),
    ("writer reads its tasks.md", W, "Read", {"file_path": f"{{root}}/{S1}/tasks.md"}, BOTH, DENY),
    ("writer writes another run's report", W, "Write", {"file_path": f"{{root}}/{S1}/ac/runs/run-002/writer-report.md"},
     BOTH, DENY),
    ("writer reads another run's feedback", W, "Read", {"file_path": f"{{root}}/{S1}/ac/runs/run-002/input-feedback.md"},
     BOTH, DENY),
    ("writer reads another feature's run", W, "Read", {"file_path": f"{{root}}/{S2}/ac/runs/run-001/input-feedback.md"},
     BOTH, DENY),
    # judge
    ("judge reads another feature's spec", J, "Read", {"file_path": f"{{root}}/{S2}/spec.md"}, BOTH, ALLOW),
    ("judge reads another feature's AC .md", J, "Read", {"file_path": f"{{root}}/{S2}/acceptance.md"}, BOTH, ALLOW),
    ("judge reads another feature's plan.md", J, "Read", {"file_path": f"{{root}}/{S2}/plan.md"}, BOTH, DENY),
    ("judge reads its tasks.md", J, "Read", {"file_path": f"{{root}}/{S1}/tasks.md"}, BOTH, DENY),
    ("judge writes another analyze's report", J, "Write", {"file_path": f"{{root}}/{RW}/analyze-2/judge-report.md"}, BOTH,
     DENY),
    ("judge edits its report", J, "Edit", {"file_path": f"{{root}}/{RA}/judge-report.md"}, BOTH, DENY),
    ("judge reads another analyze's results", J, "Read", {"file_path": f"{{root}}/{RW}/analyze-2/ac-results.md"}, BOTH,
     DENY),
    ("judge Grep in specs", J, "Grep", {"path": "{root}/specs", "pattern": "x"}, BOTH, DENY),
    # folders directly in the AC project are not "files in the AC project root"
    ("writer Grep in AC bin", W, "Grep", {"path": f"{{root}}/{AC}/bin", "pattern": "x"}, BOTH, DENY),
    ("judge Grep in AC bin", J, "Grep", {"path": f"{{root}}/{AC}/bin", "pattern": "x"}, BOTH, DENY),
    ("writer Glob in AC obj", W, "Glob", {"path": f"{{root}}/{AC}/obj", "pattern": "**/*"}, BOTH, DENY),
    ("judge Glob in AC obj", J, "Glob", {"path": f"{{root}}/{AC}/obj", "pattern": "**/*"}, BOTH, DENY),
    ("writer reads the AC bin folder", W, "Read", {"file_path": f"{{root}}/{AC}/bin"}, BOTH, DENY),
    ("writer Grep in the csproj", W, "Grep", {"path": f"{{root}}/{AC}/App.AcceptanceTests.csproj", "pattern": "x"},
     BOTH, ALLOW),
    ("translator reads the csproj", T, "Read", {"file_path": f"{{root}}/{AC}/App.AcceptanceTests.csproj"}, NONE, DENY),
    # active-run marker
    ("writer without a marker", W, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, NONE, DENY, None, None),
    ("writer with a malformed marker", W, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, NONE, DENY, None, "{broken"),
    ("writer with a marker that is a list", W, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, NONE, DENY, None, "[]"),
    ("writer with the translator's marker", W, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, NONE, DENY, None,
     MARKERS[T]),
    ("writer with a marker feature containing ..", W, "Read", {"file_path": "{root}/src/a.cs"}, NONE, DENY, None,
     {**MARKERS[W], "feature": "specs/001-alpha/../../src"}),
    ("writer with a marker for a missing feature", W, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, NONE, DENY, None,
     {**MARKERS[W], "feature": "specs/003-gamma", "tag": "F003"}),
    ("writer with a marker for a timestamp feature", W, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, NONE, DENY, None,
     {**MARKERS[W], "feature": "specs/20260101-120000-x", "tag": "F20260101"}),
    ("writer with a marker tag mismatch", W, "Read", {"file_path": f"{{root}}/{AC}/Samples/F002/x.bin"}, NONE, DENY, None,
     {**MARKERS[W], "tag": "F002"}),
    ("writer with a translate run in the marker", W, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, NONE, DENY, None,
     {**MARKERS[W], "run": "translate-001"}),
    ("judge without analyze in the marker", J, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, NONE, DENY, None,
     {**MARKERS[J], "analyze": None}),
    ("translator with analyze in the marker", T, "Read", {"file_path": f"{{root}}/{S1}/spec.md"}, NONE, DENY, None,
     {**MARKERS[T], "analyze": "analyze-1"}),
    ("translator hands back without a marker", T, "SubagentHandback", {"message": "done"}, NONE, DENY, None, None),
    # main policy: per-feature locks, script-only files
    ("main edits feature 002's AC .md while only 001 is locked", MAIN, "Edit", {"file_path": f"{{root}}/{S2}/acceptance.md"},
     SOURCES, ALLOW),
    ("main edits feature 002's AC .md while 002 is locked", MAIN, "Edit", {"file_path": f"{{root}}/{S2}/acceptance.md"},
     ("002:sources",), DENY),
    ("main writes a 001 sample while only 002 is locked", MAIN, "Write", {"file_path": f"{{root}}/{AC}/Samples/F001/x.bin"},
     ("002:sources",), ALLOW),
    ("main writes a 002 sample while 002 is locked", MAIN, "Write", {"file_path": f"{{root}}/{AC}/Samples/F002/x.bin"},
     ("002:sources",), DENY),
    ("main writes an unlocked feature's lock file", MAIN, "Write", {"file_path": f"{{root}}/{S2}/ac/sources.lock"}, NONE,
     DENY),
    ("main writes into a run folder", MAIN, "Write", {"file_path": f"{{root}}/{RW}/input-feedback.md"}, NONE, DENY),
    ("main edits a judge report", MAIN, "Edit", {"file_path": f"{{root}}/{RA}/judge-report.md"}, NONE, DENY),
    ("main reads a run folder file", MAIN, "Read", {"file_path": f"{{root}}/{RA}/judge-report.md"}, NONE, ALLOW),
    ("main writes an API listing", MAIN, "Write", {"file_path": "{root}/artifacts/refs/api/App.Core.cs"}, NONE, DENY),
    ("main writes the active-run marker", MAIN, "Write", {"file_path": "{root}/.workflow/active-run.json"}, NONE, DENY),
    ("main writes a feature file into unlocked samples", MAIN, "Write",
     {"file_path": f"{{root}}/{AC}/Samples/F001/x.feature"}, NONE, DENY),
    ("main writes a feature file into the AC project root", MAIN, "Write", {"file_path": f"{{root}}/{AC}/Extra.Feature"},
     NONE, DENY),
    ("main writes a feature file outside the AC project", MAIN, "Write", {"file_path": "{root}/docs/example.feature"},
     NONE, ALLOW),
    ("main edits the config", MAIN, "Edit", {"file_path": "{root}/.workflow/config.json"}, NONE, ALLOW),
    ("main writes spec.md while sources are locked", MAIN, "Edit", {"file_path": f"{{root}}/{S1}/spec.md"}, SOURCES,
     ALLOW),
    # main policy: Skill
    ("main calls Skill speckit-ac-translate", MAIN, "Skill", {"skill": "speckit-ac-translate"}, NONE, DENY),
    ("main calls Skill /speckit-ac-init", MAIN, "Skill", {"skill": "/speckit-ac-init"}, NONE, DENY),
    ("main calls Skill in mixed case", MAIN, "Skill", {"skill": "SpecKit-AC-Critic", "args": "spec"}, NONE, DENY),
    ("main calls Skill speckit.ac.tests-write", MAIN, "Skill", {"skill": "speckit.ac.tests-write"}, NONE, DENY),
    ("main calls Skill speckit-plan", MAIN, "Skill", {"skill": "speckit-plan"}, NONE, ALLOW),
    ("Explore calls Skill speckit-ac-tests-write", "Explore", "Skill", {"skill": "speckit-ac-tests-write"}, NONE, DENY),
]

CASES = CT_CASES + NEW_CASES


def lock_files(locked):
    """Lock files (relative to a project) for a case's locked groups."""
    files = []
    for group in locked:
        feature, group = group.split(":") if ":" in group else ("001", group)
        files.append(f"specs/{feature}-{'alpha' if feature == '001' else 'beta'}/ac/{group}.lock")
    return files


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    root = make_project(tmp_path_factory.mktemp("guard") / "proj").resolve()
    write(root / AC / "bin/Debug/App.Core.dll")
    write(root / AC / "obj/App.AcceptanceTests.AssemblyInfo.cs")
    make_project(root / WT)
    (root / BARE).mkdir(parents=True)
    return root


def run_case(project, agent_type, tool, tool_input, locked, cwd=None, marker=DEFAULT):
    for base in (project, project / WT):
        for f in lock_files(("sources", "features", "002:sources", "002:features")):
            (base / f).unlink(missing_ok=True)
        for f in lock_files(locked):
            write(base / f, "{}\n")
        marker_file = base / ".workflow/active-run.json"
        value = MARKERS.get(agent_type) if marker == DEFAULT else marker
        if value is None:
            marker_file.unlink(missing_ok=True)
        else:
            write(marker_file, value if isinstance(value, str) else json.dumps(value))
    outside = Path(tempfile.gettempdir()).resolve().parent
    text = json.dumps(tool_input).replace("{root}", str(project).replace("\\", "\\\\"))
    text = text.replace("{outside}", str(outside).replace("\\", "\\\\"))
    payload = {"tool_name": tool, "tool_input": json.loads(text), "hook_event_name": "PreToolUse",
               "cwd": str(outside) if cwd == "OUTSIDE" else str(project / cwd) if cwd else str(project)}
    if agent_type:
        payload["agent_type"] = agent_type
    return run_guard(project, payload)


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_guard_case(project, case):
    description, agent_type, tool, tool_input, locked, expected, *rest = case
    cwd = rest[0] if rest else None
    marker = rest[1] if len(rest) > 1 else DEFAULT
    code, reason = run_case(project, agent_type, tool, tool_input, locked, cwd, marker)
    assert code == expected, f"{description}: expected {expected}, got {code} {reason}"
    if expected == DENY:
        assert reason, "a block must give the model a reason on stderr"
    else:
        assert reason == "", "an allow must print nothing"


def test_case_descriptions_are_unique():
    names = [c[0] for c in CASES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("text", ["{not json", "", "[]", '{"tool_name": "Read", "tool_input": "x"}'])
def test_bad_input_blocks(project, text):
    code, reason = run_guard(project, text)
    assert code == DENY and reason


def test_ac_role_deny_carries_suffix_and_is_logged(project):
    code, reason = run_case(project, W, "Read", {"file_path": "{root}/src/a.cs"}, NONE)
    assert code == DENY and "Do not try to work around it" in reason
    log = (project / ".workflow/guard.log").read_text(encoding="utf-8").splitlines()
    assert log[-1] == f"{W}\tRead\tdeny"


# ---- marker against R05 (project-level states) and the root fallback ------------------------------------------

@pytest.mark.parametrize("case", FEATURE_FOLDERS, ids=[c[0] for c in FEATURE_FOLDERS])
def test_marker_feature_folder_rules(tmp_path, case):
    _, folder, setup, valid = case
    project = make_project(tmp_path / "proj").resolve()
    feature_setup(project, setup)
    marker = {**MARKERS[W], "feature": folder, "tag": feature_tag(folder)}
    code, reason = call(project, W, "Read", {"file_path": str(project / folder / "spec.md")}, marker)
    assert code == (ALLOW if valid else DENY), reason
    if not valid:
        assert "No valid active run" in reason


def test_root_fallback_without_project_dir(tmp_path):
    project = make_project(tmp_path / "proj").resolve()
    payload = {"tool_name": "Read", "hook_event_name": "PreToolUse", "cwd": str(project)}
    guard = project / ".specify/extensions/ac/hooks/guard.py"
    read = {**payload, "tool_input": {"file_path": str(project / AC / "StepDefinitions/F001/A.cs")}}
    assert run_guard(project, read, project_dir=None)[0] == DENY  # rules apply from the installed location
    read_src = {**payload, "tool_input": {"file_path": str(project / "src/a.cs")}}
    assert run_guard(project, read_src, project_dir=None)[0] == ALLOW
    # Passes only if the root really is the temp project (its marker and feature folder).
    write(project / ".workflow/active-run.json", json.dumps(MARKERS[T]))
    read_spec = {**payload, "agent_type": T, "tool_input": {"file_path": str(project / "specs/001-alpha/spec.md")}}
    assert run_guard(project, read_spec, project_dir=None) == (ALLOW, "")
    stray = tmp_path / "elsewhere" / "guard.py"
    write(stray, guard.read_text(encoding="utf-8"))
    code, reason = run_guard(project, read_src, project_dir=None, guard=stray)
    assert code == DENY and "not under <project>/.specify/extensions/ac/" in reason


# ---- config states ---------------------------------------------------------------------------------------------

def config_project(tmp_path, config):
    return make_project(tmp_path / "proj", config=config).resolve()


def call(project, agent_type, tool, tool_input, marker=None):
    payload = {"tool_name": tool, "tool_input": tool_input, "hook_event_name": "PreToolUse", "cwd": str(project)}
    if agent_type:
        payload["agent_type"] = agent_type
    if agent_type in MARKERS:
        write(project / ".workflow/active-run.json", json.dumps(marker or MARKERS[agent_type]))
    return run_guard(project, payload)


def test_missing_config_allows_main_but_not_ac_roles_or_ac_skills(tmp_path):
    project = config_project(tmp_path, None)
    assert call(project, MAIN, "Read", {"file_path": str(project / AC / "StepDefinitions/F001/A.cs")})[0] == ALLOW
    assert call(project, MAIN, "Write", {"file_path": str(project / AC / "Features/F001/A.feature")})[0] == ALLOW
    assert call(project, MAIN, "Skill", {"skill": "speckit-ac-init"})[0] == DENY
    assert call(project, "Explore", "Read", {"file_path": str(project / "src/a.cs")})[0] == ALLOW
    assert call(project, W, "Read", {"file_path": str(project / "specs/001-alpha/spec.md")})[0] == DENY


@pytest.mark.parametrize("config", [
    "{broken",
    json.dumps({**CONFIG, "schemaVersion": 2}),
    json.dumps({k: v for k, v in CONFIG.items() if k != "acRefBuildCommand"}),
    json.dumps({**CONFIG, "acProjectDir": "../outside"}),
    json.dumps({**CONFIG, "acProjectDir": "."}),
    json.dumps({**CONFIG, "acProjectDir": "tests/.."}),
    json.dumps({**CONFIG, "specInputs": ["docs", "./"]}),
    json.dumps({**CONFIG, "specInputs": ["specs"]}),
    json.dumps({**CONFIG, "specInputs": ["specs/001-alpha"]}),
    json.dumps({**CONFIG, "specInputs": ["tests"]}),
    json.dumps({**CONFIG, "specInputs": ["artifacts/refs/api"]}),
    json.dumps({**CONFIG, "specInputs": [".workflow"]}),
    json.dumps({**CONFIG, "refsDir": "C:/refs"}),
    json.dumps({**CONFIG, "specInputs": "docs"}),
    json.dumps([CONFIG]),
    json.dumps({k: v for k, v in CONFIG.items() if k != "testFramework"}),
    json.dumps({**CONFIG, "testFramework": "xunit"}),
], ids=["broken json", "schema 2", "missing key", "acProjectDir with ..", "acProjectDir .", "acProjectDir tests/..",
        "specInputs ./", "specInputs specs", "specInputs a feature", "specInputs contains the AC project",
        "specInputs inside refs", "specInputs .workflow", "absolute refsDir", "specInputs not a list",
        "not an object", "testFramework missing", "testFramework unknown"])
def test_invalid_config_blocks_everything(tmp_path, config):
    project = config_project(tmp_path, config)
    code, reason = call(project, MAIN, "Read", {"file_path": str(project / "src/a.cs")})
    assert code == DENY and "AC guard error" in reason


def test_config_paths_are_normalised(tmp_path):
    config = {**CONFIG, "acProjectDir": "./tests\\App.AcceptanceTests/", "refsDir": "artifacts/./refs"}
    project = config_project(tmp_path, json.dumps(config))
    code, reason = call(project, MAIN, "Read", {"file_path": str(project / AC / "StepDefinitions/F001/A.cs")})
    assert code == DENY and "must not look at AC step definitions" in reason
    assert call(project, MAIN, "Write", {"file_path": str(project / "artifacts/refs/api/A.cs")})[0] == DENY
