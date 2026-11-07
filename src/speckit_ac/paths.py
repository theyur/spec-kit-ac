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
