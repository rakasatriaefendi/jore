"""JORE release metadata resolution.

`release.json` is the release-time source of truth.
Installed runtimes persist the same metadata in `runtime.json`.

Compatibility exports intentionally remain available:
- APP_NAME
- APP_PRONUNCIATION
- VERSION
- __version__
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_DEFAULT_PRODUCT = "JORE"
_DEFAULT_PRONUNCIATION = "Yor-Eh"
_UNKNOWN_VERSION = "0+unknown"


def _read_metadata(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _candidate_manifests() -> list[Path]:
    candidates: list[Path] = []

    explicit_runtime = os.environ.get("JORE_RUNTIME_MANIFEST", "").strip()
    if explicit_runtime:
        candidates.append(Path(explicit_runtime))

    explicit_release = os.environ.get("JORE_RELEASE_MANIFEST", "").strip()
    if explicit_release:
        candidates.append(Path(explicit_release))

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / "runtime.json")
        candidates.append(parent / "release.json")

    return candidates


def get_release_metadata() -> dict[str, str]:
    # Build/install-time environment is authoritative while the frozen
    # runtime manifest has not been written yet.
    env_version = os.environ.get("JORE_VERSION", "").strip()
    env_product = os.environ.get("JORE_PRODUCT", "").strip()
    env_pronunciation = os.environ.get("JORE_PRONUNCIATION", "").strip()

    discovered: dict[str, Any] = {}
    for candidate in _candidate_manifests():
        data = _read_metadata(candidate)
        if data:
            discovered = data
            break

    product = (
        env_product
        or str(discovered.get("product") or discovered.get("app") or "").strip()
        or _DEFAULT_PRODUCT
    )
    version = (
        env_version
        or str(discovered.get("version") or "").strip()
        or _UNKNOWN_VERSION
    )
    pronunciation = (
        env_pronunciation
        or str(discovered.get("pronunciation") or "").strip()
        or _DEFAULT_PRONUNCIATION
    )

    return {
        "product": product,
        "version": version,
        "pronunciation": pronunciation,
    }


def get_version() -> str:
    return get_release_metadata()["version"]


_METADATA = get_release_metadata()

APP_NAME = _METADATA["product"]
APP_PRONUNCIATION = _METADATA["pronunciation"]
VERSION = _METADATA["version"]

# Backward-compatible public alias expected by entrypoint/TUI modules.
__version__ = VERSION
