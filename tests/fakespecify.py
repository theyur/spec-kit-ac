"""A fake `Host` for deploy tests: spec-kit's `extension add --dev` / `remove` as probed with specify 1.0.2
(docs/steps/06-cli-deploy.spec.md, Context), `uv run --no-project python -I` mapped to this interpreter, git stubbed.

It records every call, and for each call whether our guard group was in .claude/settings.json at that moment, so tests
can check the order by state (S06-A04)."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAYLOAD = REPO / "src" / "speckit_ac" / "payload"
GUARD_REL = ".specify/extensions/ac/hooks/guard.py"
EMPTY_YML = "installed: []\r\nsettings:\r\n  auto_execute_hooks: true\r\nhooks: {}\r\n"


def write(path: Path, text: str = "x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def make_project(base: Path, name: str = "proj") -> Path:
    """The files a fresh `specify init --integration claude --script ps` project has that deploy looks at, plus the
    CLAUDE.md and solution the prerequisites need."""
    root = base / name
    write(root / ".specify/init-options.json", json.dumps(
        {"ai": "claude", "integration": "claude", "script": "ps", "speckit_version": "1.0.2"}, indent=2) + "\n")
    write(root / ".specify/memory/constitution.md", "# Constitution\n")
    write(root / ".claude/skills/speckit-plan/SKILL.md", "---\nname: speckit-plan\n---\n\nPlan.\n")
    write(root / "CLAUDE.md", "# Project\n\nHouse rules.\n")
    write(root / "App.slnx", "<Solution />\n")
    return root


def copy_payload(target: Path) -> Path:
    shutil.copytree(PAYLOAD, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target


def snapshot(root: Path) -> dict:
    """Every file (bytes, or the link target for a symlink) and every empty folder below `root`, `.git` excluded."""
    out = {}
    for folder, dirs, files in os.walk(root):
        rel = Path(folder).relative_to(root)
        if rel.parts[:1] == (".git",):
            dirs[:] = []
            continue
        for name in dirs:
            path = Path(folder, name)
            if path.is_symlink() or not any(path.iterdir()):
                out[(rel / name).as_posix() + "/"] = "empty"
        for name in files:
            path = Path(folder, name)
            out[(rel / name).as_posix()] = ("link:" + os.readlink(path)) if path.is_symlink() else path.read_bytes()
    return out


def guard_registered(root: Path) -> bool:
    path = root / ".claude/settings.json"
    return path.is_file() and GUARD_REL in path.read_text(encoding="utf-8")


class FakeHost:
    def __init__(self, root: Path):
        self.root = root
        self.calls = []  # (command list, guard registered at that moment)
        self.missing = set()
        self.os = "Windows"
        self.specify_version = "specify 1.0.2"
        self.python_version = "3.14"
        self.git = "true"
        self.fail = {}  # command prefix -> (code, output)
        self.symlinks = True

    def which(self, tool):
        return None if tool in self.missing else f"C:/tools/{tool}.exe"

    def system(self):
        return self.os

    def commands(self, prefix: str):
        return [(cmd, registered) for cmd, registered in self.calls if " ".join(cmd).startswith(prefix)]

    def run(self, cmd, cwd, stdin=None, env=None, timeout=60):
        cmd = [str(c) for c in cmd]
        self.calls.append((cmd, guard_registered(self.root)))
        line = " ".join(cmd)
        for prefix, result in self.fail.items():
            if line.startswith(prefix):
                return result
        if cmd[:2] == ["specify", "--version"]:
            return 0, self.specify_version + "\n"
        if cmd[:3] == ["specify", "extension", "add"]:
            self.add(Path(cmd[4]), "--force" in cmd)
            return 0, "Extension installed\n"
        if cmd[:3] == ["specify", "extension", "remove"]:
            self.remove()
            return 0, "Extension removed\n"
        if cmd[:3] == ["uv", "run", "--no-project"]:
            rest = cmd[cmd.index("-I") + 1:]
            if rest[:1] == ["-c"]:
                return 0, self.python_version + "\n"
            result = subprocess.run([sys.executable, "-I", *rest], cwd=cwd, input=stdin, capture_output=True,
                                    text=True, env={**os.environ, **(env or {})})
            return result.returncode, result.stdout + result.stderr
        if cmd[:2] == ["git", "rev-parse"]:
            return 0, self.git + "\n"
        raise AssertionError(f"unexpected command: {cmd}")

    def rewrite_settings(self):
        """spec-kit's event-config merge rewrites an existing settings.json: json.dumps(indent=2) in text mode
        (CRLF on Windows), non-ASCII escaped (specify_cli/events.py, _safe_write_json)."""
        path = self.root / ".claude/settings.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            path.write_bytes((json.dumps(data, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))

    # ---- spec-kit, as probed ----------------------------------------------------------------------------------

    def add(self, payload: Path, force: bool):
        root = self.root
        ext = root / ".specify/extensions/ac"
        if ext.exists():
            if not force:
                raise AssertionError("add without --force over an installed extension")
            shutil.rmtree(ext)
            (root / ".specify/extensions/.backup").mkdir(parents=True, exist_ok=True)
        ignore_file = payload / ".extensionignore"
        patterns = [p.strip().rstrip("/") for p in ignore_file.read_text(encoding="utf-8").splitlines()
                    if p.strip() and not p.startswith("#")] if ignore_file.is_file() else []
        shutil.copytree(payload, ext, ignore=shutil.ignore_patterns(*patterns, ".extensionignore"))
        for command in sorted((ext / "commands").glob("speckit.ac.*.md")):
            name = "speckit-ac-" + command.stem.split(".", 2)[2]
            text = command.read_text(encoding="utf-8")
            description = re.search(r"^description: (.*)$", text, re.MULTILINE).group(1)
            body = text.split("\n---\n", 1)[1]
            skill = (f"---\nname: {name}\ndescription: {description}\ncompatibility: Requires spec-kit project "
                     f"structure with .specify/ directory\nmetadata:\n  author: github-spec-kit\n  source: "
                     f"ac:commands/{command.name}\n---\n{body}")
            dev = ext / ".specify-dev/agent-commands/claude" / name / "SKILL.md"
            write(dev, skill)
            link = root / ".claude/skills" / name / "SKILL.md"
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.is_symlink() or link.exists():
                link.unlink()
            if self.symlinks:
                os.symlink(os.path.relpath(dev, link.parent), link)
            else:
                write(link, skill)
        version = re.search(r'^  version: "(.*)"$', (ext / "extension.yml").read_text(encoding="utf-8"),
                            re.MULTILINE).group(1)
        registry = {"schema_version": "1.0", "extensions": {"ac": {"version": version, "source": "local"}}}
        write(root / ".specify/extensions/.registry", json.dumps(registry, indent=2).replace("\n", "\r\n"))
        write(root / ".specify/extensions.yml", "installed:\r\n- ac\r\nsettings:\r\n  auto_execute_hooks: true\r\n")
        self.rewrite_settings()

    def remove(self):
        root = self.root
        ext = root / ".specify/extensions/ac"
        if ext.exists():
            shutil.rmtree(ext)
        for folder in (root / ".claude/skills").glob("speckit-ac-*"):
            shutil.rmtree(folder)
        write(root / ".specify/extensions/.registry",
              json.dumps({"schema_version": "1.0", "extensions": {}}, indent=2).replace("\n", "\r\n"))
        write(root / ".specify/extensions.yml", EMPTY_YML)
        (root / ".specify/extensions/.backup/ac").mkdir(parents=True, exist_ok=True)
        self.rewrite_settings()
