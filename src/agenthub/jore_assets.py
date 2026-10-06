from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parent / "assets" / "jore"
VALID_ASSETS = {
    "logo",
    "mascot",
    "welcome",
    "loading",
    "success",
    "error",
    "goodbye",
    "session",
    "model_icons",
}


def width_bucket(columns: int) -> int:
    columns = max(1, int(columns))
    if columns < 64:
        return 48
    if columns < 100:
        return 80
    return 120


def _clean_plain(text: str) -> str:
    # The source pack intentionally contains a few render-token placeholders.
    # The TUI uses prompt_toolkit styling, so strip those placeholders here.
    text = re.sub(r"\[\[(?:RESET|RES)?\|?", "", text)
    text = text.replace("[[|", "")
    return "\n".join(line.rstrip() for line in text.splitlines()).strip("\n")


@lru_cache(maxsize=64)
def _read_asset(name: str, bucket: int) -> str:
    if name not in VALID_ASSETS:
        raise ValueError(f"Unknown JORE asset: {name}")
    path = ASSET_ROOT / "plain" / str(bucket) / f"{name}.txt"
    if not path.is_file():
        return ""
    return _clean_plain(path.read_text(encoding="utf-8"))


def asset(name: str, columns: int) -> str:
    return _read_asset(name, width_bucket(columns))


def loading_frames(columns: int) -> list[str]:
    raw = asset("loading", columns)
    if not raw:
        return ["[|] JORE is thinking"]
    frames: list[str] = []
    for chunk in raw.split("===FRAME==="):
        lines = [
            line.rstrip()
            for line in chunk.strip().splitlines()
            if not line.lstrip().startswith("# frame")
        ]
        body = "\n".join(line for line in lines if line.strip()).strip()
        if body:
            frames.append(body)
    return frames or ["[|] JORE is thinking"]


def mascot(columns: int) -> str:
    return asset("mascot", columns)


def logo(columns: int) -> str:
    return asset("logo", columns)
