import subprocess
import sys

from speckit_ac import __version__
from speckit_ac.cli import main

EXPECTED_VERSION_LINE = f"speckit-ac {__version__}\n"


def test_version_in_process(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out == EXPECTED_VERSION_LINE


def test_no_arguments_prints_help(capsys):
    assert main([]) == 0
    assert "usage: speckit-ac" in capsys.readouterr().out


def test_help_exits_zero(capsys):
    assert main(["--help"]) == 0
    assert "usage: speckit-ac" in capsys.readouterr().out


def test_unknown_argument_is_an_error(capsys):
    assert main(["--no-such-option"]) == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_version_via_python_m():
    result = subprocess.run(
        [sys.executable, "-m", "speckit_ac", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.replace("\r\n", "\n") == EXPECTED_VERSION_LINE
