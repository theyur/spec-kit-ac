"""Command-line entry point for `speckit-ac`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from speckit_ac import __version__

PROG = "speckit-ac"
COMMANDS = {
    "install": "check the prerequisites, add the spec-kit extension and deploy the Claude-side files",
    "uninstall": "undo the deploy (keeping files you changed) and remove the spec-kit extension",
    "upgrade": "re-add the spec-kit extension from this speckit-ac and redeploy",
    "doctor": "check the deployed files, the guard registration and the Python command (writes nothing)",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Install and manage the spec-kit AC (acceptance-test) extension in a .NET project. "
                    "Run it from the project root (the folder with .specify/).",
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="{" + ",".join(COMMANDS) + "}")
    for name, text in COMMANDS.items():
        sub.add_parser(name, help=text, description=text[0].upper() + text[1:] + ".")
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
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return _exit_code(exc)
    if args.command is None:
        parser.print_help()
        return 0
    from speckit_ac import deploy  # loads the payload's aclib; not needed for --version / help

    try:
        return getattr(deploy, args.command)(Path.cwd())
    except deploy.DeployError as error:
        deploy.say(f"FAIL: {error}", err=True)
        return 1
