"""install / uninstall / upgrade / doctor: the deploy step of spec-kit-ac (DESIGN §9; docs/steps/06-cli-deploy.spec.md).

spec-kit installs the extension (`specify extension add --dev <payload>`); this module deploys what spec-kit doesn't know
about: the three agents in .claude/agents/, the guard registration in .claude/settings.json, real and patched
`speckit-ac-*` skills, a block in CLAUDE.md, and the manifest .workflow/deploy.json. All external programs go through
a `Host`, so tests can replace them. Output is ASCII only.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from speckit_ac import __version__
from speckit_ac.paths import payload_dir, payload_module

aclib = payload_module("aclib")
PYTHON = payload_module("init_config").PYTHON  # the v1.0 Python command (DESIGN §2), one definition

EXT = ".specify/extensions/ac"
GUARD_REL = f"{EXT}/hooks/guard.py"
GUARD_COMMAND = f'{PYTHON} "$CLAUDE_PROJECT_DIR/{GUARD_REL}"'
GUARD_SUFFIX = f' "$CLAUDE_PROJECT_DIR/{GUARD_REL}"'
TIMEOUT = 30
MANIFEST = ".workflow/deploy.json"
MANIFEST_SCHEMA = 1
SETTINGS = ".claude/settings.json"
AGENTS = ".claude/agents"
SKILLS = ".claude/skills"
EXTENSIONS = ".specify/extensions"
REGISTRY = f"{EXTENSIONS}/.registry"
BACKUP = f"{EXTENSIONS}/.backup"
EXTENSIONS_YML = ".specify/extensions.yml"
ROLES = aclib.ROLES
AGENT_FILES = tuple(f"{AGENTS}/{role}.md" for role in ROLES)
PREEXISTING = (SETTINGS, AGENTS, *AGENT_FILES, EXTENSIONS, EXTENSIONS_YML, REGISTRY, BACKUP)
MD_BEGIN = "<!-- >>> speckit-ac (managed; do not edit) -->"
MD_END = "<!-- <<< speckit-ac -->"
# What `specify extension remove` leaves in extensions.yml when no extension is left (specify 1.0.2, CRLF folded).
EMPTY_EXTENSIONS_YML = "installed: []\nsettings:\n  auto_execute_hooks: true\nhooks: {}\n"
MIN_SPECIFY = (1, 0, 2)
MIN_PYTHON = (3, 11)
SKILL_FLAG = "disable-model-invocation: true"
MANUAL_STEPS = f"""Undo by hand, in this order:
  1. In {SETTINGS}, remove the PreToolUse group whose command names {GUARD_REL}. Do this first: a registered
     guard whose file is gone blocks every Claude Code tool call.
  2. Delete {', '.join(AGENT_FILES)} unless you changed them.
  3. Remove the speckit-ac block from CLAUDE.md, .gitignore and .gitattributes.
  4. Run: specify extension remove ac --force"""

CLAUDE_BLOCK = [
    "## Acceptance tests (spec-kit extension `ac`)",
    "",
    "This project uses the isolated acceptance-test workflow of spec-kit-ac. These rules are for the main agent; the",
    "AC subagents never load this file.",
    "",
    "- Flow per feature: /speckit-specify -> /speckit-clarify -> /speckit-ac-translate (draft `acceptance.md`, user",
    "  review, lock; then translate to `.feature` files, lock) -> /speckit-plan -> /speckit-tasks -> /speckit-implement",
    "  -> /speckit-ac-tests-write -> /speckit-ac-tests-analyze. /speckit-ac-critic reviews on request.",
    "- The /speckit-ac-* commands are started only by the user, who types them. Never start them yourself, and never",
    "  start the AC subagents (ac-feature-translator, ac-test-writer, ac-test-fail-judge) except from those commands,",
    "  with the exact task message their scripts print.",
    "- After each step: report, then stop and wait for the user. Never start the next step on your own.",
    "- Never read, search, list, diff or review the step definitions and AC support code: the `StepDefinitions/` and",
    "  `Support/` folders of the AC project (`acProjectDir` in `.workflow/config.json`). This holds for every tool,",
    "  including Bash, PowerShell, `git diff` / `git show` / `git log -p` and code-review tools. Use the test results",
    "  and the judge report instead.",
    "- Never edit `.feature` files, lock files (`specs/*/ac/*.lock`), run records (`specs/*/ac/runs/`), the reference",
    "  assemblies (`refsDir`) or `.workflow/active-run.json`. Locked acceptance criteria change only after the user",
    "  asks for an unlock.",
    "- Every domain rule the acceptance criteria depend on belongs in the feature's `spec.md` or in the constitution,",
    "  not only in this file.",
    "- The extension's files are in `.specify/extensions/ac/` (see its README.md). Setup and checks: /speckit-ac-init;",
    "  `speckit-ac doctor` in a terminal.",
]


class DeployError(Exception):
    """A user-facing failure: printed as `FAIL: <message>`, exit code 1."""


def say(text: str = "", err: bool = False):
    """Print ASCII only (R01): anything else is backslash-escaped, so no console code page can fail on it."""
    print(text.encode("ascii", "backslashreplace").decode("ascii"), file=sys.stderr if err else sys.stdout)


# ---- host: every external program ------------------------------------------------------------------------------

def _real_run(cmd, cwd, stdin=None, env=None, timeout=60):
    """(exit code, stdout + stderr); exit code None when the program is missing or timed out."""
    full_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", **(env or {})}
    try:
        result = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", env=full_env, timeout=timeout)
    except FileNotFoundError:
        return None, f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return None, f"{' '.join(map(str, cmd[:3]))} timed out after {timeout} s"
    return result.returncode, (result.stdout or "") + (result.stderr or "")


@dataclass
class Host:
    run: Callable = _real_run
    which: Callable = shutil.which
    system: Callable = platform.system


def tail(text: str, limit: int = 600) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else "..." + text[-limit:]


# ---- small helpers ---------------------------------------------------------------------------------------------

def content_hash(path: Path) -> str:
    """sha256 of the content with CRLF folded to LF (an autocrlf=true clone checks the files out with CRLF)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def newline_of(text: str) -> str:
    return "\r\n" if "\n" in text and text.split("\n", 1)[0].endswith("\r") else "\n"


def rmdir_if_empty(path: Path) -> bool:
    if path.is_dir() and not path.is_symlink() and not any(path.iterdir()):
        path.rmdir()
        return True
    return False


def aclib_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except aclib.AcError as error:
        raise DeployError(str(error)) from None


def require_root(root: Path):
    if not (root / ".specify").is_dir():
        raise DeployError(f"{root} has no .specify/ folder. Run speckit-ac from the root of a spec-kit project.")


def read_json(path: Path):
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def registry_lists_ac(root: Path) -> bool:
    try:
        data = read_json(root / REGISTRY)
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and isinstance(data.get("extensions"), dict) and "ac" in data["extensions"]


def registry_version(root: Path):
    data = read_json(root / REGISTRY)
    return data["extensions"]["ac"].get("version")


# ---- prerequisites and refusals (R02, R04) -------------------------------------------------------------------

def prerequisites(root: Path, host: Host) -> list[str]:
    problems = []
    if host.system() != "Windows":
        problems.append(f"OS is {host.system()}; spec-kit-ac v1.0 supports Windows only")
    for tool in ("uv", "pwsh", "specify"):
        if host.which(tool) is None:
            problems.append(f"{tool} is not on PATH")
    if host.which("specify") is not None:
        code, out = host.run(["specify", "--version"], root, timeout=300)
        match = re.search(r"specify\s+(\d+)\.(\d+)\.(\d+)", out or "")
        if code != 0 or not match:
            problems.append(f"could not read the spec-kit version (`specify --version`): {tail(out, 200)}")
        elif tuple(int(n) for n in match.groups()) < MIN_SPECIFY:
            problems.append(f"spec-kit {'.'.join(match.groups())} is too old; v1.0 needs specify >= "
                            f"{'.'.join(map(str, MIN_SPECIFY))}")
    if host.which("uv") is not None:
        code, out = host.run([*PYTHON.split(), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], root,
                             timeout=300)
        # The version is the last word of the last line (uv may print warnings first). An anchored full match
        # on that one word avoids an unanchored search with backtracking (Sonar S8786).
        lines = (out or "").strip().splitlines()
        match = re.fullmatch(r"(\d+)\.(\d+)", lines[-1].rpartition(" ")[2]) if lines else None
        if code != 0 or not match:
            problems.append(f"`{PYTHON}` does not start Python: {tail(out, 200)}")
        elif tuple(int(n) for n in match.groups()) < MIN_PYTHON:
            problems.append(f"`{PYTHON}` starts Python {'.'.join(match.groups())}; the guard needs >= 3.11")
    try:
        options = read_json(root / ".specify" / "init-options.json")
    except (OSError, ValueError):
        options = None
    if not isinstance(options, dict):
        problems.append(".specify/init-options.json is missing or not valid JSON (is spec-kit initialised?)")
    else:
        if options.get("script") != "ps":
            problems.append(f'.specify/init-options.json has "script": {json.dumps(options.get("script"))}; v1.0 '
                            'needs "ps" (specify init --script ps)')
        if options.get("integration") != "claude":
            problems.append(f'.specify/init-options.json has "integration": {json.dumps(options.get("integration"))};'
                            ' spec-kit-ac needs the Claude Code integration ("claude")')
    if not (root / "CLAUDE.md").is_file():
        problems.append("CLAUDE.md is missing (create it first, e.g. with /init in Claude Code)")
    if not any(p.is_file() and p.suffix.lower() in (".sln", ".slnx") for p in root.iterdir()):
        problems.append("no .sln or .slnx in the project root")
    code, out = host.run(["git", "rev-parse", "--is-inside-work-tree"], root, timeout=60)
    if code != 0 or (out or "").strip() != "true":
        problems.append("the project is not a git repository")
    return problems


def read_settings(root: Path):
    """(object, original text) of .claude/settings.json, or (None, None) when missing. Wrong shapes → DeployError."""
    path = root / SETTINGS
    if not path.is_file():
        return None, None
    text = path.read_bytes().decode("utf-8")
    try:
        obj = json.loads(text.lstrip("﻿"))
    except ValueError as error:
        raise DeployError(f"{SETTINGS} is not valid JSON ({error}). Fix it first.") from None
    if not isinstance(obj, dict):
        raise DeployError(f"{SETTINGS} is not a JSON object. Fix it first.")
    if "hooks" in obj:
        hooks = obj["hooks"]
        if not isinstance(hooks, dict):
            raise DeployError(f'"hooks" in {SETTINGS} is not an object. Fix it first.')
        if "PreToolUse" in hooks:
            groups = hooks["PreToolUse"]
            if not isinstance(groups, list) or not all(isinstance(g, dict) for g in groups):
                raise DeployError(f'"hooks.PreToolUse" in {SETTINGS} is not a list of objects. Fix it first.')
    return obj, text


def config_problem(root: Path):
    path = root / aclib.CONFIG
    if not path.is_file():
        return None
    try:
        aclib.validate_config(read_json(path))
    except (ValueError, aclib.AcError) as error:
        return f"{aclib.CONFIG} is invalid ({error}); a registered guard would block every tool call. Fix it first."
    return None


def install_refusals(root: Path, payload: Path) -> list[str]:
    problems = []
    if (root / MANIFEST).exists():
        problems.append(f"{MANIFEST} exists: spec-kit-ac is already deployed here. Use `speckit-ac upgrade` or "
                        "`speckit-ac doctor`.")
    if registry_lists_ac(root):
        problems.append("the spec-kit extension `ac` is already installed. Use `speckit-ac upgrade` or "
                        "`speckit-ac doctor`.")
    for rel in AGENT_FILES:
        target, source = root / rel, payload / "agents" / Path(rel).name
        if target.is_file() and content_hash(target) != content_hash(source):
            problems.append(f"{rel} exists with other content; move it away first (install would overwrite it)")
    try:
        read_settings(root)
    except DeployError as error:
        problems.append(str(error))
    problem = config_problem(root)
    if problem:
        problems.append(problem)
    return problems


# ---- spec-kit -------------------------------------------------------------------------------------------------

def specify_add(root: Path, host: Host, payload: Path, force: bool = False):
    cmd = ["specify", "extension", "add", "--dev", str(payload)] + (["--force"] if force else [])
    code, out = host.run(cmd, root, timeout=300)
    if code != 0:
        raise DeployError(f"`{' '.join(cmd[:4])}{' --force' if force else ''}` failed (exit {code}): {tail(out)}")


def specify_remove(root: Path, host: Host):
    code, out = host.run(["specify", "extension", "remove", "ac", "--force"], root, timeout=300)
    if code != 0:
        raise DeployError(f"`specify extension remove ac --force` failed (exit {code}): {tail(out)}")


# ---- skills (R06) ---------------------------------------------------------------------------------------------

def patch_skill_text(text: str) -> str:
    """Add or set `disable-model-invocation: true` in the frontmatter; every other byte stays."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise DeployError("a speckit-ac skill has no frontmatter")
    close = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---"), None)
    if close is None:
        raise DeployError("a speckit-ac skill has an unterminated frontmatter")
    eol = lines[0][3:] or "\n"
    for i in range(1, close):
        if re.match(r"disable-model-invocation\s*:", lines[i]):
            body = lines[i].rstrip("\r\n")
            lines[i] = SKILL_FLAG + lines[i][len(body):]
            return "".join(lines)
    at = next((i for i in range(1, close) if re.match(r"metadata\s*:", lines[i])), close)
    lines.insert(at, SKILL_FLAG + eol)
    return "".join(lines)


def skill_files(root: Path) -> list[Path]:
    folder = root / SKILLS
    return sorted(folder.glob("speckit-ac-*/SKILL.md")) if folder.is_dir() else []


def has_skill_flag(text: str) -> bool:
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return False
    return any(re.fullmatch(r"disable-model-invocation\s*:\s*true\s*", line) for line in lines[1:lines.index("---", 1)])


def patch_skills(root: Path) -> list[str]:
    """Replace each speckit-ac skill symlink with a real, patched file. Returns the project-relative paths."""
    skills = skill_files(root)
    if not skills:
        raise DeployError(f"spec-kit rendered no {SKILLS}/speckit-ac-*/SKILL.md (is the Claude integration set up?)")
    base = (root / SKILLS).resolve()
    for found in skills:
        # Only SKILL.md itself may be a link (spec-kit's --dev install). A skill folder that leads outside SKILLS
        # (a directory link or junction) would make the write below land outside the project: refuse it.
        folder = found.parent.resolve()
        if folder.parent != base or not folder.name.startswith("speckit-ac-"):
            raise DeployError(f"{found.parent.relative_to(root).as_posix()} leads outside {SKILLS}; "
                              "replace it with a real folder")
        skill = folder / "SKILL.md"
        try:
            data = skill.read_bytes()  # through the link
        except OSError as error:
            raise DeployError(f"cannot read {skill}: {error}") from None
        new = patch_skill_text(data.decode("utf-8")).encode("utf-8")
        if skill.is_symlink():
            skill.unlink()
        elif data == new:
            continue
        skill.write_bytes(new)
    return [s.relative_to(root).as_posix() for s in skills]


# ---- agents (R07) ---------------------------------------------------------------------------------------------

def deploy_agents(root: Path, recorded: dict | None = None):
    """Copy the installed agents to .claude/agents/. In an upgrade (`recorded` = manifest hashes), an agent the user
    changed is kept. Returns (written, kept) project-relative paths."""
    written, kept = [], []
    for rel in AGENT_FILES:
        source, target = root / EXT / "agents" / Path(rel).name, root / rel
        if not source.is_file():
            raise DeployError(f"{EXT}/agents/{Path(rel).name} is missing after the spec-kit install")
        if target.is_file():
            if content_hash(target) == content_hash(source):
                continue
            if recorded is not None and rel in recorded and content_hash(target) != recorded[rel]:
                kept.append(rel)
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        written.append(rel)
    return written, kept


# ---- CLAUDE.md block (R08) ------------------------------------------------------------------------------------

def write_claude_block(root: Path) -> bool:
    return aclib_call(aclib.write_block, root / "CLAUDE.md", CLAUDE_BLOCK, begin=MD_BEGIN, end=MD_END)


def remove_claude_block(root: Path) -> bool:
    return aclib_call(aclib.remove_block, root / "CLAUDE.md", begin=MD_BEGIN, end=MD_END)


# ---- guard registration (R10, R11) ----------------------------------------------------------------------------

def guard_group() -> dict:
    return {"matcher": "*",
            "hooks": [{"type": "command", "command": GUARD_COMMAND, "timeout": TIMEOUT, "onFailure": "block"}]}


def is_ours(group) -> bool:
    hooks = group.get("hooks") if isinstance(group, dict) else None
    return isinstance(hooks, list) and any(
        isinstance(h, dict) and isinstance(h.get("command"), str) and GUARD_REL in h["command"] for h in hooks)


def serialise(obj, newline: str) -> str:
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").replace("\n", newline)


def settings_style(root: Path) -> dict:
    """Line ending of .claude/settings.json and whether our serialisation would reformat it, read BEFORE spec-kit
    touches the file: `specify extension add/remove` rewrite an existing settings.json (json.dumps(indent=2), text
    mode, so CRLF on Windows)."""
    obj, text = read_settings(root)
    if obj is None:
        return {"newline": "LF", "reformatted": False}
    newline = newline_of(text)
    return {"newline": "CRLF" if newline == "\r\n" else "LF", "reformatted": serialise(obj, newline) != text}


def register_guard(root: Path, newline: str | None = None) -> dict:
    """Add our PreToolUse group last (replacing an earlier one). Returns what install created / changed.
    `newline` ("LF" / "CRLF") is the file's own line ending from before spec-kit rewrote it."""
    obj, text = read_settings(root)
    created_file = obj is None
    if obj is None:
        obj, text = {}, None
    if newline is not None:
        newline = "\r\n" if newline == "CRLF" else "\n"
    else:
        newline = newline_of(text) if text else "\n"
    reformatted = text is not None and serialise(obj, newline) != text
    created = []
    if "hooks" not in obj:
        obj["hooks"] = {}
        created.append("hooks")
    if "PreToolUse" not in obj["hooks"]:
        obj["hooks"]["PreToolUse"] = []
        created.append("hooks.PreToolUse")
    groups = obj["hooks"]["PreToolUse"]
    groups[:] = [g for g in groups if not is_ours(g)]
    groups.append(guard_group())
    path = root / SETTINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(serialise(obj, newline).encode("utf-8"))
    return {"createdFile": created_file, "createdKeys": created, "reformatted": reformatted}


def unregister_guard(root: Path, created_file: bool = False, created_keys=()) -> bool:
    """Remove our group; drop keys / the file only where install created them. No group: no-op. True if changed."""
    obj, text = read_settings(root)
    if obj is None:
        return False
    original = json.loads(text.lstrip("﻿"))
    hooks = obj.get("hooks")
    if isinstance(hooks, dict) and isinstance(hooks.get("PreToolUse"), list):
        hooks["PreToolUse"] = [g for g in hooks["PreToolUse"] if not is_ours(g)]
        if "hooks.PreToolUse" in created_keys and hooks["PreToolUse"] == []:
            del hooks["PreToolUse"]
    if isinstance(hooks, dict) and "hooks" in created_keys and hooks == {}:
        del obj["hooks"]
    path = root / SETTINGS
    if created_file and obj == {}:
        path.unlink()
        return True
    if obj == original:
        return False
    path.write_bytes(serialise(obj, newline_of(text)).encode("utf-8"))
    return True


def restore_settings_style(root: Path, newline: str) -> bool:
    """Undo spec-kit's rewrite of an existing settings.json: our serialisation in the recorded line ending."""
    obj, text = read_settings(root)
    if obj is None:
        return False
    new = serialise(obj, "\r\n" if newline == "CRLF" else "\n")
    if new == text:
        return False
    (root / SETTINGS).write_bytes(new.encode("utf-8"))
    return True


def registered_groups(root: Path) -> list:
    obj, _ = read_settings(root)
    groups = ((obj or {}).get("hooks") or {}).get("PreToolUse") or []
    return [g for g in groups if is_ours(g)]


def guard_self_test(root: Path, host: Host):
    """None if the installed guard allows a main-agent Read of CLAUDE.md and blocks `Skill speckit-ac-init`."""
    guard = root / GUARD_REL
    if not guard.is_file():
        return f"{GUARD_REL} is missing"
    cases = [("Read", {"file_path": str(root / "CLAUDE.md")}, 0), ("Skill", {"skill": "speckit-ac-init"}, 2)]
    for tool, tool_input, expected in cases:
        payload = json.dumps({"hook_event_name": "PreToolUse", "cwd": str(root), "tool_name": tool,
                              "tool_input": tool_input})
        code, out = host.run([*PYTHON.split(), str(guard)], root, stdin=payload,
                             env={"CLAUDE_PROJECT_DIR": str(root)}, timeout=60)
        if code != expected:
            return f"guard self-test: {tool} gave exit {code}, expected {expected}: {tail(out, 300)}"
    return None


# ---- manifest (R09) -------------------------------------------------------------------------------------------

def snapshot_preexisting(root: Path) -> dict:
    return {rel: (root / rel).exists() for rel in PREEXISTING}


def extension_files(root: Path) -> list[str]:
    folder = root / EXT
    return sorted(aclib.rel_posix(root, p) for p in folder.rglob("*")
                  if p.is_file() and "__pycache__" not in p.relative_to(folder).parts and p.suffix != ".pyc")


def build_manifest(root: Path, skills, preexisting, created_keys, style, kept_agents=()) -> dict:
    files = []
    for rel in AGENT_FILES:
        # A kept (user-changed) agent is recorded with the deployed source's hash, so uninstall still keeps it.
        source = root / EXT / "agents" / Path(rel).name if rel in kept_agents else root / rel
        files.append({"path": rel, "kind": "agent", "sha256": content_hash(source)})
    files += [{"path": rel, "kind": "skill", "sha256": content_hash(root / rel)} for rel in skills]
    files += [{"path": rel, "kind": "extension", "sha256": content_hash(root / rel)} for rel in extension_files(root)]
    return {
        "schemaVersion": MANIFEST_SCHEMA,
        "version": __version__,
        "command": GUARD_COMMAND,
        "installedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "preexisting": preexisting,
        "settingsCreatedKeys": sorted(created_keys),
        "settingsNewline": style["newline"],
        "settingsReformatted": bool(style["reformatted"]),
        "files": sorted(files, key=lambda f: f["path"]),
    }


def write_manifest(root: Path, manifest: dict):
    aclib.write_text(root / MANIFEST, json.dumps(manifest, indent=2) + "\n")


def read_manifest(root: Path) -> dict:
    path = root / MANIFEST
    if not path.is_file():
        raise DeployError(f"no deploy manifest ({MANIFEST}): spec-kit-ac is not deployed here (`speckit-ac install`).")
    try:
        manifest = read_json(path)
    except (OSError, ValueError) as error:
        raise DeployError(f"{MANIFEST} is not valid JSON ({error})") from None
    ok = (isinstance(manifest, dict) and manifest.get("schemaVersion") == MANIFEST_SCHEMA
          and isinstance(manifest.get("version"), str) and isinstance(manifest.get("command"), str)
          and isinstance(manifest.get("preexisting"), dict) and isinstance(manifest.get("settingsCreatedKeys"), list)
          and isinstance(manifest.get("settingsReformatted"), bool) and isinstance(manifest.get("files"), list)
          and manifest.get("settingsNewline") in ("LF", "CRLF")
          and all(isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("sha256"), str)
                  and f.get("kind") in ("agent", "skill", "extension") for f in manifest["files"]))
    if not ok:
        raise DeployError(f"{MANIFEST} does not have the expected shape (schemaVersion {MANIFEST_SCHEMA}).")
    return manifest


# ---- removal helpers (R13) ------------------------------------------------------------------------------------

def remove_leftovers(root: Path, preexisting: dict) -> list[str]:
    """spec-kit's empty bookkeeping, removed only where it did not exist before install (decision 4)."""
    removed = []
    registry = root / REGISTRY
    if not preexisting.get(REGISTRY) and registry.is_file():
        try:
            data = read_json(registry)
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict) and data.get("extensions") == {}:
            registry.unlink()
            removed.append(REGISTRY)
    yml = root / EXTENSIONS_YML
    if not preexisting.get(EXTENSIONS_YML) and yml.is_file() and \
            yml.read_bytes().decode("utf-8", "replace").replace("\r\n", "\n") == EMPTY_EXTENSIONS_YML:
        yml.unlink()
        removed.append(EXTENSIONS_YML)
    if rmdir_if_empty(root / BACKUP / "ac"):
        removed.append(f"{BACKUP}/ac/")
    for rel in (BACKUP, EXTENSIONS, AGENTS):
        if not preexisting.get(rel) and rmdir_if_empty(root / rel):
            removed.append(rel + "/")
    return removed


def remove_agents(root: Path, recorded: dict, preexisting: dict, written=None):
    """Delete deployed agents that are unchanged; keep changed and pre-existing ones. Returns (removed, kept)."""
    removed, kept = [], []
    for rel in AGENT_FILES:
        path = root / rel
        if not path.is_file() or preexisting.get(rel) or (written is not None and rel not in written):
            continue
        if rel in recorded and content_hash(path) != recorded[rel]:
            kept.append(rel)
            continue
        path.unlink()
        removed.append(rel)
    return removed, kept


def user_data(root: Path) -> list[str]:
    kept = []
    config = root / aclib.CONFIG
    if config.is_file():
        kept.append(aclib.CONFIG)
        try:
            cfg = aclib.validate_config(read_json(config))
            kept += [f"{cfg[k]}/" for k in ("acProjectDir", "refsDir") if (root / cfg[k]).exists()]
        except (OSError, ValueError, aclib.AcError):
            pass
    specs = root / "specs"
    if specs.is_dir():
        kept += sorted(aclib.rel_posix(root, p) for p in specs.glob("*/acceptance.md"))
        kept += sorted(aclib.rel_posix(root, p) + "/" for p in specs.glob("*/ac") if p.is_dir())
    if (root / ".workflow" / "guard.log").is_file():
        kept.append(".workflow/guard.log")
    return kept


def bullets(items) -> str:
    return "\n".join(f"  - {item}" for item in items)


# ---- commands -------------------------------------------------------------------------------------------------

def install(root: Path, host: Host | None = None, payload: Path | None = None) -> int:
    host, payload = host or Host(), payload or payload_dir()
    require_root(root)
    problems = prerequisites(root, host) + install_refusals(root, payload)
    if problems:
        raise DeployError("install stopped before any change:\n" + bullets(problems))
    preexisting = snapshot_preexisting(root)
    style = settings_style(root)
    specify_add(root, host, payload)
    done = {"agents": [], "block": False, "registered": None}
    step = "skills"
    try:
        skills = patch_skills(root)
        step = "agents"
        done["agents"], _ = deploy_agents(root)
        step = "CLAUDE.md block"
        done["block"] = write_claude_block(root)
        step = "guard self-test"
        problem = guard_self_test(root, host)
        if problem:
            raise DeployError(problem)
        step = "guard registration"
        done["registered"] = register_guard(root, style["newline"])
        step = "manifest"
        manifest = build_manifest(root, skills, preexisting, done["registered"]["createdKeys"], style)
        write_manifest(root, manifest)
    except (DeployError, aclib.AcError, OSError) as error:
        undo_problems = undo_install(root, host, preexisting, done, style)
        message = f"install failed at the {step} step: {error}\nEverything install did was undone."
        if undo_problems:
            message = (f"install failed at the {step} step: {error}\nUndoing it failed too:\n{bullets(undo_problems)}"
                       f"\n{MANUAL_STEPS}")
        raise DeployError(message) from None
    say(f"Installed spec-kit-ac {__version__}:")
    say(bullets([f"spec-kit extension `ac` ({EXT}/)",
                 f"{len(skills)} skills made real files with `{SKILL_FLAG}` ({SKILLS}/speckit-ac-*/)",
                 f"agents: {', '.join(AGENT_FILES)}",
                 "CLAUDE.md: speckit-ac block",
                 f"{SETTINGS}: guard registered (PreToolUse, matcher *, onFailure block, timeout {TIMEOUT} s)",
                 f"{MANIFEST}: deploy manifest"]))
    if style["reformatted"]:
        say(f"Note: {SETTINGS} was rewritten with 2-space JSON indentation (same content, new formatting).")
    say()
    say("Next steps:")
    say("  1. Start a NEW Claude Code session in this folder and trust it (agents and hooks load at session start).")
    say("  2. Run /speckit-ac-init.")
    say("  3. In another new session, run /speckit-ac-init smoke (live guard smoke test).")
    say(f"  4. Commit the deployed files, including the real {SKILLS}/speckit-ac-*/SKILL.md files and {MANIFEST}.")
    return 0


def undo_install(root: Path, host: Host, preexisting: dict, done: dict, style: dict) -> list[str]:
    """Reverse a partial install (guard first). Returns the problems hit while undoing."""
    problems = []
    actions = []
    if done["registered"] is not None:
        actions.append(lambda: unregister_guard(root, done["registered"]["createdFile"],
                                                done["registered"]["createdKeys"]))
    actions.append(lambda: remove_agents(root, {}, preexisting, written=done["agents"]))
    if done["block"]:
        actions.append(lambda: remove_claude_block(root))
    actions.append(lambda: specify_remove(root, host) if registry_lists_ac(root) else None)
    actions.append(lambda: remove_leftovers(root, preexisting))
    if preexisting.get(SETTINGS) and not style["reformatted"]:
        actions.append(lambda: restore_settings_style(root, style["newline"]))
    for action in actions:
        try:
            action()
        except (DeployError, aclib.AcError, OSError) as error:
            problems.append(str(error))
    return problems


def uninstall(root: Path, host: Host | None = None) -> int:
    host = host or Host()
    require_root(root)
    if not (root / MANIFEST).is_file():
        raise DeployError(f"no deploy manifest ({MANIFEST}), so uninstall cannot tell which files are ours.\n"
                          + MANUAL_STEPS)
    manifest = read_manifest(root)
    preexisting = manifest["preexisting"]
    recorded = {f["path"]: f["sha256"] for f in manifest["files"]}
    warnings = []
    if unregister_guard(root, not preexisting.get(SETTINGS), manifest["settingsCreatedKeys"]):
        say(f"Guard registration removed from {SETTINGS}.")
        if manifest["settingsReformatted"]:
            warnings.append(f"{SETTINGS} keeps the 2-space JSON formatting install gave it (same content).")
    removed, kept = remove_agents(root, recorded, preexisting)
    if removed:
        say(f"Agents removed: {', '.join(removed)}")
    warnings += [f"{rel} was changed after install, so it is kept" for rel in kept]
    if remove_claude_block(root):
        say("CLAUDE.md: speckit-ac block removed.")
    for name in (".gitignore", ".gitattributes"):
        path = root / name
        if aclib_call(aclib.remove_block, path):
            if path.stat().st_size == 0:
                path.unlink()
                say(f"{name}: speckit-ac block removed (the file was empty afterwards and is deleted).")
            else:
                say(f"{name}: speckit-ac block removed.")
    for rel, sha in recorded.items():
        path = root / rel
        if rel.startswith(SKILLS + "/") and path.is_file() and content_hash(path) != sha:
            warnings.append(f"{rel} was changed after install; spec-kit deletes it with the extension")
    if registry_lists_ac(root):
        specify_remove(root, host)
        say("spec-kit extension `ac` removed (specify extension remove ac --force).")
    remove_leftovers(root, preexisting)
    if preexisting.get(SETTINGS) and restore_settings_style(root, manifest["settingsNewline"]):
        say(f"{SETTINGS}: formatting restored after spec-kit rewrote it.")
    (root / MANIFEST).unlink()
    rmdir_if_empty(root / ".workflow")
    say(f"Deploy manifest {MANIFEST} removed.")
    for warning in warnings:
        say(f"warn: {warning}")
    kept_data = user_data(root)
    if kept_data:
        say("Kept (your data; delete by hand if you no longer need it):")
        say(bullets(kept_data))
    return 0


def upgrade(root: Path, host: Host | None = None, payload: Path | None = None) -> int:
    host, payload = host or Host(), payload or payload_dir()
    require_root(root)
    manifest = read_manifest(root)
    problems = prerequisites(root, host)
    if not registry_lists_ac(root):
        problems.append("the spec-kit extension `ac` is not installed (`.specify/extensions/.registry`)")
    try:
        read_settings(root)
    except DeployError as error:
        problems.append(str(error))
    problem = config_problem(root)
    if problem:
        problems.append(problem)
    if problems:
        raise DeployError("upgrade stopped before any change:\n" + bullets(problems))
    recorded = {f["path"]: f["sha256"] for f in manifest["files"]}
    unregister_guard(root)
    step = "spec-kit extension add --force"
    try:
        specify_add(root, host, payload, force=True)
        step = "skills"
        skills = patch_skills(root)
        step = "agents"
        _, kept = deploy_agents(root, recorded)
        step = "CLAUDE.md block"
        write_claude_block(root)
        step = "guard self-test"
        problem = guard_self_test(root, host)
        if problem:
            raise DeployError(problem)
        step = "guard registration"
        registered = register_guard(root, manifest["settingsNewline"])
        step = "manifest"
        created = set(manifest["settingsCreatedKeys"]) | set(registered["createdKeys"])
        style = {"newline": manifest["settingsNewline"], "reformatted": manifest["settingsReformatted"]}
        write_manifest(root, build_manifest(root, skills, manifest["preexisting"], created, style, kept_agents=kept))
    except (DeployError, aclib.AcError, OSError) as error:
        state = "The guard is NOT registered: run `speckit-ac upgrade` again, or see `speckit-ac doctor`."
        try:
            if guard_self_test(root, host) is None:
                register_guard(root, manifest["settingsNewline"])
                state = "The installed guard passed its self-test and is registered again."
        except (DeployError, aclib.AcError, OSError):
            pass
        raise DeployError(f"upgrade failed at the {step} step: {error}\n{state}") from None
    say(f"Upgraded spec-kit-ac to {__version__} (was {manifest['version']}); skills patched, guard registered.")
    for rel in kept:
        say(f"warn: {rel} was changed after install, so it is kept (compare it with {EXT}/agents/).")
    say("Start a new Claude Code session to load the new agents and guard.")
    return 0


def doctor(root: Path, host: Host | None = None) -> int:
    host = host or Host()
    require_root(root)
    counts = {"ok": 0, "warn": 0, "FAIL": 0}

    def line(status, text):
        counts[status] += 1
        say(f"[{status}] {text}")

    def check(function):
        try:
            function()
        except (DeployError, aclib.AcError, OSError, ValueError, KeyError, TypeError) as error:
            line("FAIL", f"{function.__doc__}: {error}")

    state = {"manifest": None, "command": None}

    def c_prerequisites():
        """prerequisites"""
        problems = prerequisites(root, host)
        for problem in problems:
            line("FAIL", f"prerequisite: {problem}")
        if not problems:
            line("ok", "prerequisites (Windows, uv, pwsh, specify >= 1.0.2, Python >= 3.11, ps scripts, CLAUDE.md, "
                       "solution, git)")

    def c_manifest():
        """deploy manifest"""
        state["manifest"] = read_manifest(root)
        line("ok", f"deploy manifest {MANIFEST} (version {state['manifest']['version']})")

    def c_registry():
        """spec-kit registry"""
        version = registry_version(root) if registry_lists_ac(root) else None
        if version is None:
            line("FAIL", "the spec-kit extension `ac` is not installed (.specify/extensions/.registry)")
        elif version != state["manifest"]["version"]:
            line("FAIL", f"spec-kit lists `ac` {version}, the manifest {state['manifest']['version']}: run "
                         "`speckit-ac upgrade`")
        else:
            line("ok", f"spec-kit extension `ac` {version} installed")

    def c_version():
        """CLI version"""
        if state["manifest"]["version"] != __version__:
            line("warn", f"deployed {state['manifest']['version']}, this speckit-ac is {__version__}: run "
                         "`speckit-ac upgrade`")
        else:
            line("ok", f"deployed version = speckit-ac {__version__}")

    def c_hashes():
        """file hashes"""
        bad = 0
        for entry in state["manifest"]["files"]:
            path = root / entry["path"]
            if not path.is_file():
                line("FAIL", f"missing: {entry['path']}")
                bad += 1
            elif content_hash(path) != entry["sha256"]:
                bad += 1
                if entry["kind"] == "agent":
                    line("warn", f"changed since deploy: {entry['path']}")
                else:
                    line("FAIL", f"changed since deploy: {entry['path']} (restore with `speckit-ac upgrade`)")
        if not bad:
            line("ok", f"{len(state['manifest']['files'])} deployed files match the manifest")

    def c_extra():
        """extra extension files"""
        recorded = {f["path"] for f in state["manifest"]["files"]}
        extra = [rel for rel in extension_files(root) if rel not in recorded]
        for rel in extra:
            line("warn", f"not in the manifest: {rel}")
        if not extra:
            line("ok", f"no extra files in {EXT}/")

    def c_skills():
        """skills"""
        skills = sorted({p.relative_to(root).as_posix() for p in skill_files(root)}
                        | {f["path"] for f in state["manifest"]["files"] if f["kind"] == "skill"})
        bad = 0
        for rel in skills:
            path = root / rel
            if path.is_symlink():
                line("FAIL", f"{rel} is a symlink (run `speckit-ac upgrade`)")
                bad += 1
            elif not path.is_file():
                continue  # reported by the hash check
            elif not has_skill_flag(path.read_bytes().decode("utf-8", "replace")):
                line("FAIL", f"{rel} lacks `{SKILL_FLAG}` (run `speckit-ac upgrade`)")
                bad += 1
        if not bad:
            line("ok", f"{len(skills)} skills are real files with `{SKILL_FLAG}`")

    def c_registration():
        """guard registration"""
        groups = registered_groups(root)
        if len(groups) == 1 and len(groups[0].get("hooks", [])) == 1:
            state["command"] = groups[0]["hooks"][0].get("command")
        if not groups:
            line("FAIL", f"the guard is not registered in {SETTINGS} (run `speckit-ac upgrade`)")
        elif len(groups) > 1:
            line("FAIL", f"the guard is registered {len(groups)} times in {SETTINGS}")
        elif groups[0] != guard_group():
            line("FAIL", f"the guard registration in {SETTINGS} differs from the expected one: "
                         f"{json.dumps(groups[0])}")
        else:
            line("ok", f"guard registered in {SETTINGS} (matcher *, onFailure block, timeout {TIMEOUT} s)")

    def c_self_test():
        """guard self-test"""
        problem = guard_self_test(root, host)
        if problem:
            line("FAIL", problem)
        else:
            line("ok", "guard self-test (main-agent Read allowed, Skill speckit-ac-init blocked)")

    def c_block():
        """CLAUDE.md block"""
        text = (root / "CLAUDE.md").read_bytes().decode("utf-8", "replace") if (root / "CLAUDE.md").is_file() else ""
        if MD_BEGIN in text and MD_END in text:
            line("ok", "CLAUDE.md has the speckit-ac block")
        else:
            line("FAIL", "CLAUDE.md has no speckit-ac block (run `speckit-ac upgrade`)")

    def c_config():
        """config"""
        path = root / aclib.CONFIG
        if not path.is_file():
            line("warn", f"no {aclib.CONFIG} yet: run /speckit-ac-init in Claude Code")
            return
        cfg = aclib.validate_config(read_json(path))
        command = state["command"]
        python = command[:-len(GUARD_SUFFIX)] if isinstance(command, str) and command.endswith(GUARD_SUFFIX) \
            else PYTHON
        if cfg["python"] != python:
            line("FAIL", f'config "python" is `{cfg["python"]}`, the guard runs with `{python}`')
        else:
            line("ok", f'{aclib.CONFIG} valid; "python" matches the guard command')
        for name in (".gitignore", ".gitattributes"):
            path = root / name
            text = path.read_bytes().decode("utf-8", "replace") if path.is_file() else ""
            if aclib.BLOCK_BEGIN in text and aclib.BLOCK_END in text:
                line("ok", f"{name} has the speckit-ac block")
            else:
                line("FAIL", f"{name} has no speckit-ac block (run /speckit-ac-init again to verify and repair)")

    check(c_prerequisites)
    check(c_manifest)
    if state["manifest"] is not None:
        for function in (c_registry, c_version, c_hashes, c_extra, c_skills):
            check(function)
    else:
        line("warn", "registry, version, hash, extra-file and skill checks skipped (no valid manifest)")
    for function in (c_registration, c_self_test, c_block, c_config):
        check(function)
    say(f"{counts['ok']} ok, {counts['warn']} warn, {counts['FAIL']} FAIL")
    say("The .NET side (build, reference assemblies, test run) is checked by /speckit-ac-init in Claude Code: with a "
        "config it only verifies.")
    return 1 if counts["FAIL"] else 0
