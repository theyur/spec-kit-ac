"""Command-line entry point for `speckit-ac`."""

from __future__ import annotations

import argparse
import sys

from speckit_ac import __version__

PROG = "speckit-ac"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Install and manage the spec-kit AC (acceptance-test) extension in a .NET project.",
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    return parser


def _exit_code(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    print(code, file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        parser.parse_args(argv)
    except SystemExit as exc:
        return _exit_code(exc)
    parser.print_help()
    return 0
