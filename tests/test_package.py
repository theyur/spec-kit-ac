import tomllib
from pathlib import Path

import speckit_ac
from speckit_ac.paths import payload_dir

ROOT = Path(__file__).resolve().parents[1]


def test_version_matches_pyproject():
    with (ROOT / "pyproject.toml").open("rb") as f:
        expected = tomllib.load(f)["project"]["version"]
    assert speckit_ac.__version__ == expected


def test_payload_dir_is_absolute_and_has_readme():
    path = payload_dir()
    assert path.is_absolute()
    assert path.is_dir()
    assert (path / "README.md").is_file()


def test_payload_is_not_a_python_package():
    assert not (payload_dir() / "__init__.py").exists()
