"""Shared helpers for the `ac` workflow scripts (installed as .specify/extensions/ac/scripts/aclib.py).

Scripts run as `<python> -I .specify/extensions/ac/scripts/<name>.py`. `-I` keeps the script's own folder off
sys.path, so every script inserts it before `import aclib`. The guard does not use this module (it is standalone).
"""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
import sys
from dataclasses import dataclass
from pathlib import Path

CONFIG = ".workflow/config.json"
MARKER = ".workflow/active-run.json"
CONSTITUTION = ".specify/memory/constitution.md"
SCHEMA_VERSION = 1
STRING_KEYS = ("python", "solution", "acProjectDir", "acProject", "refsDir", "acRefBuildCommand",
               "unitTestCommand", "acTestCommand")
LIST_KEYS = ("specInputs", "acSurfaceProjects", "unitTestProjects")
ENUM_KEYS = {"testFramework": ("xunit2", "xunit3", "nunit", "mstest")}
TRANSLATOR, WRITER, JUDGE = "ac-feature-translator", "ac-test-writer", "ac-test-fail-judge"
ROLES = (TRANSLATOR, WRITER, JUDGE)
FEATURE_NAME = re.compile(r"^(\d{3,})-.+$")
TIMESTAMP_NAME = re.compile(r"^\d{8}-\d{6}-")
V1_LIMIT = ("spec-kit-ac v1.0 supports only sequentially numbered feature folders directly under specs/ "
            "(specs/NNN-name).")


class AcError(Exception):
    """A user-facing failure: printed as `FAIL: <message>`, exit code 1."""


def fail(message: str, code: int = 1):
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(code)


def run_main(main):
    """Run a script's main(), turning AcError into `FAIL: …` and exit code 1."""
    try:
        main()
    except AcError as error:
        fail(str(error))


def root(script: str) -> Path:
    """The project root for a script installed at <root>/.specify/extensions/ac/scripts/<name>.py."""
    path = Path(script).resolve()
    if len(path.parents) < 5 or path.parents[3].name != ".specify":
        raise AcError(f"{path} is not installed under <project>/.specify/extensions/ac/scripts/")
    return path.parents[4]


def rel_posix(root_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(root_dir.resolve()).as_posix()


def _relative_clean(value, key: str) -> str:
    """A config path in normalised project-relative posix form (the guard applies the same rule)."""
    if not isinstance(value, str) or not value.strip():
        raise AcError(f"{CONFIG}: key {key} must be a non-empty string")
    raw = value.strip().replace("\\", "/")
    posix = posixpath.normpath(raw)
    if (raw.startswith("/") or re.match(r"^[A-Za-z]:", raw) or posix in (".", "")
            or posix == ".." or posix.startswith("../")):
        raise AcError(f"{CONFIG}: key {key} must be a project-relative path below the project root: {value}")
    return posix


def load_config(root_dir: Path) -> dict:
    path = root_dir / CONFIG
    if not path.is_file():
        raise AcError(f"{CONFIG} not found. Run /speckit-ac-init first.")
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise AcError(f"{CONFIG} is not valid JSON: {error}") from None
    return validate_config(cfg)


def validate_config(cfg) -> dict:
    """Check a config (schema 1, docs/CONFIG.md) and return it with its paths normalised; AcError if invalid."""
    if not isinstance(cfg, dict) or cfg.get("schemaVersion") != SCHEMA_VERSION:
        raise AcError(f"{CONFIG}: schemaVersion must be {SCHEMA_VERSION}")
    for key in STRING_KEYS:
        if not isinstance(cfg.get(key), str) or not cfg[key].strip():
            raise AcError(f"{CONFIG}: missing or empty key {key}")
    for key in LIST_KEYS:
        if not isinstance(cfg.get(key), list) or not all(isinstance(v, str) and v.strip() for v in cfg[key]):
            raise AcError(f"{CONFIG}: key {key} must be a list of non-empty strings")
    for key, allowed in ENUM_KEYS.items():
        if cfg.get(key) not in allowed:
            raise AcError(f"{CONFIG}: missing or invalid key {key} (one of {', '.join(allowed)})")
    cfg["acProjectDir"] = _relative_clean(cfg["acProjectDir"], "acProjectDir")
    cfg["refsDir"] = _relative_clean(cfg["refsDir"], "refsDir")
    cfg["specInputs"] = [_relative_clean(v, "specInputs") for v in cfg["specInputs"]]
    protected = ["specs", ".specify", ".workflow", cfg["acProjectDir"], cfg["refsDir"]]
    for value in cfg["specInputs"]:
        for folder in protected:
            if _overlaps(value, folder):
                raise AcError(f"{CONFIG}: specInputs entry {value} overlaps {folder}; spec inputs must be extra "
                              "project documents outside specs/, .specify/, .workflow/, the AC project and refsDir")
    return cfg


def _overlaps(a: str, b: str) -> bool:
    """True if one project-relative path equals or contains the other (case-insensitive, as in the guard)."""
    a, b = a.lower(), b.lower()
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


@dataclass(frozen=True)
class Feature:
    dir: str  # project-relative posix, e.g. specs/001-login
    number: str  # 001
    ac_project: str  # config acProjectDir

    @property
    def tag(self) -> str:
        return f"F{self.number}"

    def paths(self) -> dict:
        ac, tag = self.ac_project, self.tag
        return {
            "featureDir": self.dir,
            "tag": tag,
            "number": self.number,
            "spec": f"{self.dir}/spec.md",
            "acceptance": f"{self.dir}/acceptance.md",
            "acDir": f"{self.dir}/ac",
            "runsDir": f"{self.dir}/ac/runs",
            "sourcesLock": f"{self.dir}/ac/sources.lock",
            "featuresLock": f"{self.dir}/ac/features.lock",
            "featuresDir": f"{ac}/Features/{tag}",
            "samplesDir": f"{ac}/Samples/{tag}",
            "stepDefinitionsDir": f"{ac}/StepDefinitions/{tag}",
            "supportDir": f"{ac}/Support/{tag}",
            "sharedSupportDir": f"{ac}/Support/Shared",
        }

    def path(self, root_dir: Path, key: str) -> Path:
        return root_dir / self.paths()[key]


def _feature_numbering(root_dir: Path):
    options = root_dir / ".specify" / "init-options.json"
    if not options.is_file():
        return None
    try:
        data = json.loads(options.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data.get("feature_numbering") or data.get("branch_numbering") if isinstance(data, dict) else None


def resolve_feature(root_dir: Path, arg: str | None, cfg: dict) -> Feature:
    """The feature folder named by `arg` (`specs/N-x`, `N-x`, `N`, `FN`, absolute path), default .specify/feature.json."""
    if _feature_numbering(root_dir) == "timestamp":
        raise AcError(f".specify/init-options.json uses timestamp feature numbering. {V1_LIMIT}")
    specs = root_dir / "specs"
    if arg is None:
        current = root_dir / ".specify" / "feature.json"
        try:
            arg = json.loads(current.read_text(encoding="utf-8"))["feature_directory"]
        except (OSError, ValueError, KeyError, TypeError):
            raise AcError("No current feature in .specify/feature.json. Pass --feature specs/NNN-name.") from None
        if not isinstance(arg, str):
            raise AcError("No current feature in .specify/feature.json. Pass --feature specs/NNN-name.")
    text = arg.strip().replace("\\", "/").rstrip("/")
    number_only = re.fullmatch(r"[Ff]?(\d+)", text)
    if number_only:
        digits = number_only[1]
        if len(digits) < 3:
            raise AcError(f"Feature number must have at least 3 digits: {arg}")
        candidates = sorted(d for d in specs.glob(f"{digits}-*") if d.is_dir()) if specs.is_dir() else []
        if not candidates:
            raise AcError(f"No feature folder specs/{digits}-* found.")
        name = candidates[0].name
    else:
        path = Path(text)
        if path.is_absolute():
            try:
                text = path.resolve().relative_to(root_dir.resolve()).as_posix()
            except ValueError:
                raise AcError(f"Feature folder is outside the project: {arg}") from None
        parts = [p for p in text.split("/") if p not in ("", ".")]
        if parts and parts[0] == "specs":
            parts = parts[1:]
        if len(parts) != 1 or parts[0] == "..":
            raise AcError(f"Not a feature folder directly under specs/: {arg}. {V1_LIMIT}")
        name = parts[0]
    if TIMESTAMP_NAME.match(name):
        raise AcError(f"specs/{name} is a timestamp feature folder. {V1_LIMIT}")
    match = FEATURE_NAME.match(name)
    if not match:
        raise AcError(f"specs/{name} does not start with a feature number. {V1_LIMIT}")
    if not (specs / name).is_dir():
        raise AcError(f"Feature folder specs/{name} not found.")
    digits = match[1]
    same = sorted(d.name for d in specs.glob(f"{digits}-*") if d.is_dir())
    if len(same) > 1:
        raise AcError(f"Feature number {digits} is used by more than one folder: {', '.join(same)}")
    return Feature(dir=f"specs/{name}", number=digits, ac_project=cfg["acProjectDir"])


def all_features(root_dir: Path, cfg: dict) -> list[Feature]:
    """Every feature folder directly under specs/, sorted by number. Any folder there that is not a valid v1.0
    feature folder (timestamp, no number, duplicate number) fails the listing."""
    specs = root_dir / "specs"
    folders = sorted(d.name for d in specs.iterdir() if d.is_dir()) if specs.is_dir() else []
    if _feature_numbering(root_dir) == "timestamp":
        raise AcError(f".specify/init-options.json uses timestamp feature numbering. {V1_LIMIT}")
    features = [resolve_feature(root_dir, f"specs/{name}", cfg) for name in folders]
    return sorted(features, key=lambda f: int(f.number))


def add_feature_arg(parser):
    parser.add_argument("--feature", help="specs/NNN-name, NNN-name, NNN or FNNN (default: .specify/feature.json)")


def glob_regex(pattern: str):
    # `**` crosses folders, `*` stays inside one path segment.
    return re.compile("^" + re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$", re.IGNORECASE)


def numbered(folder: Path, prefix: str) -> list[Path]:
    """Sub-folders `<prefix><digits>`, sorted by number."""
    if not folder.is_dir():
        return []
    found = [(int(p.name[len(prefix):]), p) for p in folder.glob(prefix + "*")
             if p.is_dir() and p.name[len(prefix):].isdigit()]
    return [p for _, p in sorted(found)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_marker(root_dir: Path, role: str, feature: Feature, run: str, analyze: str | None = None, **extra):
    marker = {"role": role, "feature": feature.dir, "tag": feature.tag, "run": run, "analyze": analyze, **extra}
    write_text(root_dir / MARKER, json.dumps(marker, indent=2) + "\n")


# Marked blocks in project files that the AC workflow owns: .gitignore / .gitattributes (written by /speckit-ac-init)
# and CLAUDE.md (written by `speckit-ac install`, with HTML-comment markers); all removed by `speckit-ac uninstall`.
# Everything outside the block is left byte for byte.
BLOCK_BEGIN = "# >>> speckit-ac (managed; do not edit)"
BLOCK_END = "# <<< speckit-ac"


def _block_span(text: str, begin: str = BLOCK_BEGIN, end_marker: str = BLOCK_END):
    """(start, end) of the managed block in `text` including its trailing line break, or None."""
    start = text.find(begin)
    if start == -1:
        return None
    if start > 0 and text[start - 1] != "\n":
        raise AcError(f"the {begin!r} line must start a line")
    end = text.find(end_marker, start)
    if end == -1:
        raise AcError(f"{begin!r} without {end_marker!r}")
    end += len(end_marker)
    if text.startswith("\r\n", end):
        end += 2
    elif text.startswith("\n", end):
        end += 1
    return start, end


def write_block(path: Path, lines: list[str], begin: str = BLOCK_BEGIN, end: str = BLOCK_END) -> bool:
    """Write the managed block into `path` (created if missing): replaced in place if present, else appended after
    one blank line. Uses the file's line ending (CRLF if its first line break is CRLF). True if the file changed.
    `begin` / `end` are the marker lines: `#` comments by default, HTML comments for the CLAUDE.md block that
    `speckit-ac install` writes."""
    old = path.read_bytes().decode("utf-8") if path.is_file() else ""
    newline = "\r\n" if "\n" in old and old.split("\n", 1)[0].endswith("\r") else "\n"
    block = newline.join([begin, *lines, end]) + newline
    span = _block_span(old, begin, end)
    if span:
        new = old[:span[0]] + block + old[span[1]:]
    elif not old:
        new = block
    else:
        new = old + ("" if old.endswith("\n") else newline) + newline + block
    if new == old:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(new.encode("utf-8"))
    return True


def remove_block(path: Path, begin: str = BLOCK_BEGIN, end: str = BLOCK_END) -> bool:
    """Remove the managed block (and one blank line before it) from `path`. True if the file changed."""
    if not path.is_file():
        return False
    old = path.read_bytes().decode("utf-8")
    span = _block_span(old, begin, end)
    if not span:
        return False
    before = old[:span[0]]
    for gap in ("\r\n\r\n", "\n\n"):
        if before.endswith(gap):
            before = before[:-len(gap) // 2]
            break
    path.write_bytes((before + old[span[1]:]).encode("utf-8"))
    return True


def read_marker(root_dir: Path) -> dict:
    try:
        marker = json.loads((root_dir / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise AcError(f"No active run ({MARKER}). Start the run with new_run.py or new_analyze.py.") from None
    if not isinstance(marker, dict) or marker.get("role") not in ROLES:
        raise AcError(f"{MARKER} is not a valid active-run marker.")
    return marker


def may_change(path: str, marker: dict, cfg: dict) -> bool:
    """True if the active run's role may change `path` (project-relative posix): the guard's write rules."""
    ac, tag, run_dir = cfg["acProjectDir"], marker["tag"], f"{marker['feature']}/ac/runs/{marker['run']}"
    feature_file = path.lower().endswith(".feature")
    if marker["role"] == TRANSLATOR:
        return ((feature_file and glob_regex(f"{ac}/Features/{tag}/**").match(path) is not None)
                or glob_regex(f"{run_dir}/translation-report.md").match(path) is not None)
    if marker["role"] == WRITER:
        # Never a .feature file: Reqnroll compiles every one, so it would add scenarios nobody locked.
        in_code = any(glob_regex(f"{ac}/{folder}/**").match(path) for folder in ("StepDefinitions", "Support"))
        return (in_code and not feature_file) or glob_regex(f"{run_dir}/writer-report.md").match(path) is not None
    return glob_regex(f"{run_dir}/{marker['analyze']}/judge-report.md").match(path) is not None


TASK_MESSAGE_SECTION = "## Your task message"


def camel(name: str) -> str:
    """UPPER_SNAKE placeholder name -> camelCase key (`AC_PROJECT_DIR` -> `acProjectDir`)."""
    first, *rest = name.lower().split("_")
    return first + "".join(part.title() for part in rest)


def template_lines(agent_file: Path) -> list[tuple[str, str]]:
    """[(label, raw value)] of the ```text template in an agent file's `## Your task message` section."""
    text = agent_file.read_text(encoding="utf-8").replace("\r\n", "\n")
    start = text.find("\n" + TASK_MESSAGE_SECTION + "\n")
    if start == -1:
        raise AcError(f"{agent_file.name}: no `{TASK_MESSAGE_SECTION}` section")
    end = text.find("\n## ", start + len(TASK_MESSAGE_SECTION) + 2)
    match = re.search(r"```text\n(.*?)\n```", text[start:end if end != -1 else len(text)], re.DOTALL)
    if not match:
        raise AcError(f"{agent_file.name}: no ```text template in `{TASK_MESSAGE_SECTION}`")
    lines = []
    for line in match[1].split("\n"):
        if ": " not in line:
            raise AcError(f"{agent_file.name}: template line without `Label: value`: {line}")
        label, raw = line.split(": ", 1)
        lines.append((label, raw))
    return lines
