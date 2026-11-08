"""Fail-closed PreToolUse guard of the spec-kit `ac` extension (docs/WORKFLOW.md §3).

Registered once in .claude/settings.json with matcher "*" (installed as .specify/extensions/ac/hooks/guard.py).
Hooks from settings also fire inside subagents, so the policy is picked from `agent_type`: the three AC roles get
default-deny allowlists pinned to the active run (.workflow/active-run.json), everything else (main agent and every
other subagent type) gets the main rules.

Block = reason on stderr + exit 2. Allow = exit 0, no output. Any error = exit 2 (fail closed).
This file is self-contained on purpose: it is the security boundary and imports no project code.
"""
import json
import os
import posixpath
import re
import sys
from pathlib import Path

TRANSLATOR, WRITER, JUDGE = "ac-feature-translator", "ac-test-writer", "ac-test-fail-judge"
AC_ROLES = (TRANSLATOR, WRITER, JUDGE)
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")  # main agent only; the AC roles have no PowerShell, and only one Bash command
HANDBACK = "SubagentHandback"  # how a subagent delivers its final message to the main agent
CODE = re.compile(r"```|\[(Binding|Given|When|Then|StepArgumentTransformation)\b")
AC_ROLE_SUFFIX = (" This restriction is intentional. Do not try to work around it."
                  " If you cannot continue, record the problem in your report.")
CONSTITUTION = ".specify/memory/constitution.md"
MARKER = ".workflow/active-run.json"
CONFIG = ".workflow/config.json"
SCHEMA_VERSION = 1
STRING_KEYS = ("python", "solution", "acProjectDir", "acProject", "refsDir", "acRefBuildCommand",
               "unitTestCommand", "acTestCommand")
LIST_KEYS = ("specInputs", "acSurfaceProjects", "unitTestProjects")
ENUM_KEYS = {"testFramework": ("xunit2", "xunit3", "nunit", "mstest")}
FEATURE_DIR = re.compile(r"^specs/(\d{3,})-[^/\\]+$")
TIMESTAMP_NAME = re.compile(r"^\d{8}-\d{6}-")
RUN_ID = {TRANSLATOR: re.compile(r"^translate-\d{3,}$"), WRITER: re.compile(r"^run-\d{3,}$"),
          JUDGE: re.compile(r"^run-\d{3,}$")}
ANALYZE_ID = re.compile(r"^analyze-\d+$")
SKILL_PREFIXES = ("speckit-ac-", "speckit.ac.")


class Deny(Exception):
    pass


def norm(path):
    """Absolute, symlink-free, case-folded on Windows, forward slashes."""
    return os.path.normcase(os.path.realpath(path)).replace("\\", "/")


def fold(path):
    """A project-relative path in the same case and slash form as norm() output."""
    return os.path.normcase(path).replace("\\", "/").strip("/")


def project_root(project, cwd):
    """The worktree under <project>/.claude/worktrees/ that holds `cwd`, else `project` itself.

    CLAUDE_PROJECT_DIR stays the main checkout when a session runs in a worktree, so without this every worktree
    path would be `.claude/worktrees/<name>/...` and match none of the project-relative rules.
    """
    prefix = project + "/.claude/worktrees/"
    if cwd.startswith(prefix):
        candidate = prefix + cwd[len(prefix):].split("/")[0]
        if Path(candidate, CONFIG).is_file():
            return candidate
    return project


def installed_root():
    """The project root for a guard installed at <root>/.specify/extensions/ac/hooks/guard.py."""
    path = Path(__file__).resolve()
    if len(path.parents) < 5 or path.parents[3].name != ".specify":
        raise ValueError(f"CLAUDE_PROJECT_DIR is not set and {path} is not under <project>/.specify/extensions/ac/")
    return path.parents[4]


def timestamp_numbering(root):
    try:
        options = json.loads(Path(root, ".specify", "init-options.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(options, dict) and (options.get("feature_numbering") or options.get("branch_numbering")) == "timestamp"


def glob_regex(pattern):
    # `**` crosses folders, `*` stays inside one path segment.
    return re.compile("^" + re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$", re.IGNORECASE)


def relative_clean(value, key):
    """A config path in normalised project-relative posix form; anything else is an error (fail closed)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"config key {key} must be a non-empty string")
    raw = value.strip().replace("\\", "/")
    posix = posixpath.normpath(raw)
    if (raw.startswith("/") or re.match(r"^[A-Za-z]:", raw) or posix in (".", "")
            or posix == ".." or posix.startswith("../")):
        raise ValueError(f"config key {key} must be a project-relative path below the project root: {value}")
    return posix


def load_config(root):
    """The validated config, or None when the AC workflow is not initialised yet (no config file)."""
    path = Path(root, CONFIG)
    if not path.exists():
        return None
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict) or cfg.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"{CONFIG}: schemaVersion must be {SCHEMA_VERSION}")
    for key in STRING_KEYS:
        if not isinstance(cfg.get(key), str) or not cfg[key].strip():
            raise ValueError(f"{CONFIG}: missing or empty key {key}")
    for key in LIST_KEYS:
        if not isinstance(cfg.get(key), list) or not all(isinstance(v, str) and v.strip() for v in cfg[key]):
            raise ValueError(f"{CONFIG}: key {key} must be a list of non-empty strings")
    for key, allowed in ENUM_KEYS.items():
        if cfg.get(key) not in allowed:
            raise ValueError(f"{CONFIG}: missing or invalid key {key} (one of {', '.join(allowed)})")
    for key in ("acProjectDir", "refsDir"):
        cfg[key] = relative_clean(cfg[key], key)
    cfg["specInputs"] = [relative_clean(value, "specInputs") for value in cfg["specInputs"]]
    protected = ["specs", ".specify", ".workflow", cfg["acProjectDir"], cfg["refsDir"]]
    for value in cfg["specInputs"]:
        for folder in protected:
            if overlaps(value, folder):
                raise ValueError(f"{CONFIG}: specInputs entry {value} overlaps {folder}; spec inputs must be extra "
                                 "project documents outside specs/, .specify/, .workflow/, the AC project and refsDir")
    return cfg


def overlaps(a, b):
    """True if one project-relative path equals or contains the other (case-insensitive)."""
    a, b = a.lower(), b.lower()
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


class Guard:
    def __init__(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("hook input is not a JSON object")
        project = norm(os.environ.get("CLAUDE_PROJECT_DIR") or installed_root())
        self.cwd = payload.get("cwd") or project
        self.root = project_root(project, norm(self.cwd))
        self.cfg = load_config(self.root)
        self.tool = payload.get("tool_name") or ""
        self.input = payload.get("tool_input") or {}
        if not isinstance(self.input, dict):
            raise ValueError("tool_input is not a JSON object")
        if self.cfg is None:
            return
        self.ac = fold(self.cfg["acProjectDir"])
        self.refs = fold(self.cfg["refsDir"])
        self.spec_inputs = [fold(p) for p in self.cfg["specInputs"]]
        self.features = f"{self.ac}/features"
        self.samples = f"{self.ac}/samples"
        self.isolated = [f"{self.ac}/stepdefinitions", f"{self.ac}/support"]
        self.isolated_text = re.compile(
            re.escape(self.ac.split("/")[-1]) + r"/+(stepdefinitions|support)(?![a-z0-9_.])", re.IGNORECASE)

    # ---- paths -------------------------------------------------------------------------------------------------

    def rel(self, path):
        """Project-relative, case-folded posix path, or raise Deny if outside the project."""
        if not isinstance(path, str) or not path.strip():
            raise Deny("Missing path.")
        full = norm(os.path.join(self.cwd, path))
        if full != self.root and not full.startswith(self.root + "/"):
            raise Deny(f"Path is outside the project directory: {path}")
        return full[len(self.root) + 1:] if full != self.root else ""

    def project_rel(self, path):
        """Like rel(), but None for a missing path or one outside the project."""
        try:
            return self.rel(path)
        except Deny:
            return None

    @staticmethod
    def under(rel, folder):
        folder = fold(folder)
        return rel == folder or rel.startswith(folder + "/")

    @staticmethod
    def matches(rel, pattern):
        return bool(glob_regex(fold(pattern)).match(rel))

    def exists(self, rel):
        return Path(self.root, rel).is_file()

    def path_field(self):
        return self.input.get("file_path") or self.input.get("notebook_path")

    def strings(self, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for v in value.values():
                yield from self.strings(v)
        elif isinstance(value, list):
            for v in value:
                yield from self.strings(v)

    # ---- main policy ------------------------------------------------------------------------------------------

    def skill_rule(self):
        if self.tool != "Skill":
            return
        name = self.input.get("skill")
        name = name.strip().lstrip("/").lower() if isinstance(name, str) else ""
        if name.startswith(SKILL_PREFIXES):
            raise Deny(f"/{name} is started only by the user. Ask the user to type /{name} themselves.")

    def sources_locked(self, number):
        """True if any feature folder numbered `number` has its sources lock."""
        specs = Path(self.root, "specs")
        return specs.is_dir() and any(Path(d, "ac", "sources.lock").is_file()
                                      for d in specs.glob(f"{number}-*") if d.is_dir())

    def main_writes(self, rel):
        if self.matches(rel, "specs/*/ac/*.lock"):
            raise Deny(f"{rel} is written only by the lock script (ac_lock.py).")
        if self.matches(rel, "specs/*/ac/runs/**") or self.under(rel, self.refs) or rel == fold(MARKER):
            raise Deny(f"{rel} is produced only by the workflow scripts and AC subagents. Do not write it.")
        match = re.match(r"^specs/([^/]+)/acceptance\.md$", rel)
        if match and self.exists(f"specs/{match[1]}/ac/sources.lock"):
            raise Deny(f"{rel} is locked (sources). It changes only after the user asks for an unlock.")
        match = re.match(re.escape(self.samples) + r"/f(\d{3,})(/|$)", rel)
        if match and self.sources_locked(match[1]):
            raise Deny(f"{rel} is locked (sources). It changes only after the user asks for an unlock.")
        # G3: Reqnroll compiles every .feature in the AC project, so none may come from the main agent.
        if self.under(rel, self.features) or (self.under(rel, self.ac) and rel.lower().endswith(".feature")):
            raise Deny("Feature files are generated by ac-feature-translator. Change the feature's acceptance.md "
                       "and run /speckit-ac-translate again.")

    def main(self):
        self.skill_rule()
        if self.cfg is None:
            return  # AC workflow not initialised: nothing else to protect yet

        # Writes outside the project (scratchpad, memory, …) are none of this guard's business for the main agent.
        rel = self.project_rel(self.path_field()) if self.tool in WRITE_TOOLS else None
        if rel is not None:
            self.main_writes(rel)

        # G2: step definitions are hidden from the main agent.
        message = ("Main agent must not look at AC step definitions (isolation rule). "
                   "Use test results and the judge report instead.")
        if self.tool in WRITE_TOOLS:
            texts = [self.path_field() or ""]  # file content may legitimately mention the folders
        elif self.tool in SHELL_TOOLS:
            texts = [self.input.get("command") or ""]
            # Inside the AC project folder, a bare `StepDefinitions/…` or `Support/…` is enough to reach them.
            cwd = norm(self.cwd)
            ac_dir = norm(os.path.join(self.root, self.ac))
            if (cwd == ac_dir or cwd.startswith(ac_dir + "/")) and re.search(
                    r"stepdefinitions|support", texts[0], re.IGNORECASE):
                raise Deny(message)
        else:
            texts = list(self.strings(self.input))
            if self.tool == "Glob":
                texts.append(os.path.join(self.input.get("path") or self.cwd, self.input.get("pattern") or ""))

        for text in texts:
            if isinstance(text, str) and self.isolated_text.search(text.replace("\\", "/")):
                raise Deny(message)
        for key in ("file_path", "notebook_path", "path"):
            value = self.input.get(key)
            if isinstance(value, str) and value.strip():
                rel = self.project_rel(value)
                if rel is None:
                    continue  # outside the project: not this rule's concern
                # A search rooted at the AC project folder itself would read StepDefinitions/ and Support/ too.
                if any(self.under(rel, f) for f in self.isolated) or (key == "path" and rel == self.ac):
                    raise Deny(message)

    # ---- AC roles ---------------------------------------------------------------------------------------------

    def load_marker(self, role):
        try:
            marker = json.loads(Path(self.root, MARKER).read_text(encoding="utf-8"))
            feature, tag, run, analyze = marker["feature"], marker["tag"], marker["run"], marker.get("analyze")
            match = FEATURE_DIR.match(feature) if isinstance(feature, str) else None
            ok = (marker.get("role") == role and match is not None and ".." not in feature
                  and not TIMESTAMP_NAME.match(feature[len("specs/"):])
                  and Path(self.root, feature).is_dir()
                  and len([d for d in Path(self.root, "specs").glob(f"{match[1]}-*") if d.is_dir()]) == 1
                  and not timestamp_numbering(self.root)
                  and tag == "F" + match[1]
                  and isinstance(run, str) and RUN_ID[role].match(run)
                  and ((isinstance(analyze, str) and ANALYZE_ID.match(analyze)) if role == JUDGE else analyze is None))
        except (OSError, ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            raise Deny(f"No valid active run for {role} ({MARKER}). AC subagents run only inside the AC commands.")
        self.feature, self.tag = fold(feature), fold(tag)
        self.run_dir = f"{self.feature}/ac/runs/{fold(run)}"
        self.analyze_dir = f"{self.run_dir}/{fold(analyze)}" if analyze else None

    def folders(self, role):
        """Folders the role may read and search (search roots)."""
        if role == TRANSLATOR:
            return self.spec_inputs + [f"{self.samples}/{self.tag}", f"{self.features}/{self.tag}"]
        return self.spec_inputs + [self.features, self.samples, *self.isolated, self.refs]

    def readable_file(self, rel, role):
        files = [fold(CONSTITUTION)]
        if role == JUDGE:
            if self.matches(rel, "specs/*/spec.md") or self.matches(rel, "specs/*/acceptance.md"):
                return True
            files += [f"{self.run_dir}/writer-report.md", f"{self.analyze_dir}/ac-results.md"]
        else:
            files += [f"{self.feature}/spec.md", f"{self.feature}/acceptance.md"]
            files += ([f"{self.run_dir}/translation-report.md"] if role == TRANSLATOR else
                      [f"{self.run_dir}/input-feedback.md", f"{self.run_dir}/writer-report.md"])
        if rel in files:
            return True
        # Project files directly in the AC project root (csproj, reqnroll.json, Directory.Build.props); never the
        # folders there (bin/, obj/ hold the real assemblies and generated code).
        return (role != TRANSLATOR and rel.startswith(self.ac + "/") and "/" not in rel[len(self.ac) + 1:]
                and self.exists(rel))

    def readable(self, rel, role):
        return any(self.under(rel, f) for f in self.folders(role)) or self.readable_file(rel, role)

    def writable(self, rel, role):
        if role == TRANSLATOR:
            if self.under(rel, f"{self.features}/{self.tag}") and rel.lower().endswith(".feature"):
                if self.exists(f"{self.feature}/ac/features.lock"):
                    raise Deny(f"{rel} is locked (features). It changes only after the user asks for an unlock.")
                return True
            return rel == f"{self.run_dir}/translation-report.md"
        if role == WRITER:
            # Never a .feature file: Reqnroll compiles every one, so it would add scenarios nobody locked.
            return ((any(self.under(rel, f) for f in self.isolated) and not rel.lower().endswith(".feature"))
                    or rel == f"{self.run_dir}/writer-report.md")
        return self.tool == "Write" and rel == f"{self.analyze_dir}/judge-report.md"

    def ac_role(self, role):
        if self.cfg is None:
            raise Deny(f"The AC workflow is not initialised ({CONFIG} is missing).")
        self.load_marker(role)
        tool = self.tool
        if tool == "Read":
            rel = self.rel(self.input.get("file_path"))
            if not self.readable(rel, role):
                raise Deny(f"{role} may not read {rel}.")
        elif tool in ("Grep", "Glob"):
            if not self.input.get("path"):
                raise Deny(f"{tool} needs an explicit `path` inside a readable folder.")
            rel = self.rel(self.input["path"])
            if rel == self.ac or not (any(self.under(rel, f) for f in self.folders(role))
                                      or self.readable_file(rel, role)):
                raise Deny(f"{role} may not search {rel or '.'}.")
            pattern = self.input.get("pattern" if tool == "Glob" else "glob") or ""
            if not isinstance(pattern, str) or ".." in pattern or os.path.isabs(pattern) \
                    or pattern.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", pattern):
                raise Deny(f"{tool} pattern must be relative and must not contain '..'.")
        elif tool in ("Write", "Edit", "MultiEdit"):
            rel = self.rel(self.path_field())
            if not self.writable(rel, role):
                raise Deny(f"{role} may not write {rel}.")
        elif tool == "Bash" and role in (TRANSLATOR, WRITER):
            allowed = " ".join(self.cfg["acRefBuildCommand"].split())
            command = self.input.get("command")
            if not isinstance(command, str) or " ".join(command.split()) != allowed:
                raise Deny(f"The only allowed Bash command is: {allowed}")
        elif tool == HANDBACK:
            # The final message reaches the main agent, which must never see step-definition code.
            if any(CODE.search(text) for text in self.strings(self.input)):
                raise Deny("Hand back a short summary without code. Details belong in your report file.")
        else:
            raise Deny(f"{role} may not use the {tool} tool.")


def log(root, agent_type, tool, decision):
    try:
        with open(os.path.join(root, ".workflow", "guard.log"), "a", encoding="utf-8") as f:
            f.write(f"{agent_type}\t{tool}\t{decision}\n")
    except OSError:
        pass


def main():
    payload = json.loads(sys.stdin.read())
    guard = Guard(payload)
    agent_type = payload.get("agent_type") or ""
    role = agent_type if agent_type in AC_ROLES else "main"
    try:
        guard.main() if role == "main" else guard.ac_role(role)
    except Deny as deny:
        reason = str(deny) + (AC_ROLE_SUFFIX if role != "main" else "")
        if agent_type:
            log(guard.root, agent_type, guard.tool, "deny")
        print(reason, file=sys.stderr)
        sys.exit(2)
    if agent_type:
        log(guard.root, agent_type, guard.tool, "allow")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as error:  # fail closed
        print(f"AC guard error, call blocked: {error!r}", file=sys.stderr)
        sys.exit(2)
