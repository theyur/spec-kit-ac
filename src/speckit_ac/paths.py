"""Locations of files bundled with the package."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def payload_dir() -> Path:
    """Absolute path of the bundled spec-kit extension folder (`payload/`).

    It must be a real directory on disk: it is handed to `specify extension add --dev`.
    """
    resource = files("speckit_ac") / "payload"
    if not isinstance(resource, Path):
        raise RuntimeError(f"speckit-ac payload is not on the file system: {resource!r}")
    path = resource.resolve()
    if not path.is_dir():
        raise RuntimeError(f"speckit-ac payload folder is missing: {path}")
    return path


def payload_module(name: str, payload: Path | None = None):
    """Import a payload script module (`aclib`, `init_config`) for the CLI, writing no `__pycache__` into the payload.

    `aclib` is loaded first and registered as `sys.modules["aclib"]`, so a script's own `import aclib` reuses it
    and there is one `AcError` class. The scripts folder is put on `sys.path` for that import (the scripts expect it).
    """
    import importlib
    import sys

    scripts = str((payload or payload_dir()) / "scripts")
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        importlib.import_module("aclib")
        return importlib.import_module(name)
    finally:
        sys.dont_write_bytecode = previous
