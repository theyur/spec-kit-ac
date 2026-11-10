"""Release checks for spec-kit-ac (stdlib only; used by .github/workflows/release.yml).

    python tools/release_check.py check <tag>            # tag == v<version>, both version fields match, not a dev version
    python tools/release_check.py notes <version> <out>  # write the CHANGELOG.md section of <version> to <out>
    python tools/release_check.py latest                 # print the newest released (dated) CHANGELOG version

Exit 0 on success, 1 with a message on stderr otherwise.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRERELEASE = re.compile(r"(\.dev|a|b|rc)\d*$")
SECTION = re.compile(r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?[ \t]*$", re.MULTILINE)


class ReleaseError(Exception):
    pass


def package_version(root: Path | None = None) -> str:
    root = root or ROOT
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def manifest_version(root: Path | None = None) -> str:
    root = root or ROOT
    text = (root / "src" / "speckit_ac" / "payload" / "extension.yml").read_text(encoding="utf-8")
    found = re.search(r'^  version: "([^"]+)"$', text, re.MULTILINE)
    if not found:
        raise ReleaseError("extension.yml has no extension version line")
    return found.group(1)


def check(tag: str, root: Path | None = None) -> str:
    root = root or ROOT
    version, manifest = package_version(root), manifest_version(root)
    if manifest != version:
        raise ReleaseError(f"pyproject.toml says {version}, extension.yml says {manifest}")
    if PRERELEASE.search(version):
        raise ReleaseError(f"{version} is a pre-release version; release a final version")
    if tag != f"v{version}":
        raise ReleaseError(f"tag {tag} does not match the package version (expected v{version})")
    return version


def sections(root: Path | None = None) -> list[tuple[str, str | None, str]]:
    """(version, date or None, body) for every `## [x]` section of CHANGELOG.md, in file order."""
    root = root or ROOT
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    heads = list(SECTION.finditer(text))
    out = []
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[head.end():end]
        body = re.split(r"^\[[^\]]+\]: ", body, flags=re.MULTILINE)[0]  # drop trailing link definitions
        out.append((head.group("version"), head.group("date"), body.strip()))
    return out


def notes(version: str, root: Path | None = None) -> str:
    root = root or ROOT
    for found, date, body in sections(root):
        if found == version:
            if not date:
                raise ReleaseError(f"CHANGELOG.md section {version} has no release date")
            if not body:
                raise ReleaseError(f"CHANGELOG.md section {version} is empty")
            return body + "\n"
    raise ReleaseError(f"CHANGELOG.md has no section for {version}")


def latest(root: Path | None = None) -> str:
    root = root or ROOT
    for version, date, _ in sections(root):
        if date:
            return version
    raise ReleaseError("CHANGELOG.md has no released (dated) section")


def main(argv: list[str]) -> int:
    try:
        match argv:
            case ["check", tag]:
                print(f"release {check(tag)}: tag and version fields match")
            case ["notes", version, out]:
                Path(out).write_text(notes(version), encoding="utf-8", newline="\n")
            case ["latest"]:
                print(latest())
            case _:
                print(__doc__, file=sys.stderr)
                return 1
    except (ReleaseError, OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        print(f"release_check: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
