from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "agenthub"
TOOLS_CONFIG = CONFIG_DIR / "tools.json"

DATA_DIR = Path.home() / ".local" / "share" / "agenthub"
MANAGED_PREFIX = DATA_DIR / "tools"
MANAGED_BIN = MANAGED_PREFIX / "node_modules" / ".bin"

TOOL_SPECS = {
    "opencode": {
        "package": "@opencode/cli",
        "required": True,
        "fallbacks": [
            Path.home() / ".local" / "npm" / "bin" / "opencode",
            Path.home() / ".local" / "npm" / "lib" / "node_modules" / "@opencode" / "cli" / "bin" / "opencode.exe",
            Path.home() / ".local" / "bin" / "opencode",
        ],
    },
    "codex": {
        "package": "@openai/codex",
        "required": False,
        "fallbacks": [
            Path.home() / ".local" / "npm" / "bin" / "codex",
            Path.home() / ".local" / "npm" / "lib" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js",
            Path.home() / ".local" / "bin" / "codex",
        ],
    },
}


@dataclass
class ToolStatus:
    name: str
    found: bool
    path: str | None = None
    source: str = "missing"
    managed: bool = False
    version: str | None = None
    authenticated: bool | None = None
    auth_detail: str | None = None


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _load_config() -> dict[str, Any]:
    if not TOOLS_CONFIG.exists():
        return {}

    try:
        value = json.loads(TOOLS_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return value if isinstance(value, dict) else {}


def _configured_path(name: str) -> Path | None:
    item = _load_config().get(name)

    if isinstance(item, str):
        return Path(item).expanduser()

    if isinstance(item, dict):
        path = item.get("path")
        if isinstance(path, str) and path:
            return Path(path).expanduser()

    return None


def _managed_path(name: str) -> Path:
    return MANAGED_BIN / name


def _is_managed_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(MANAGED_PREFIX.resolve())
        return True
    except (OSError, ValueError):
        return False


def resolve_tool(name: str) -> ToolStatus:
    if name not in TOOL_SPECS:
        raise ValueError(f"Unknown tool: {name}")

    candidates: list[tuple[str, Path]] = []

    configured = _configured_path(name)
    if configured:
        candidates.append(("config", configured))

    candidates.append(("agenthub-managed", _managed_path(name)))

    which = shutil.which(name)
    if which:
        candidates.append(("path", Path(which)))

    for path in TOOL_SPECS[name]["fallbacks"]:
        candidates.append(("fallback", path))

    seen: set[str] = set()

    for source, path in candidates:
        expanded = path.expanduser()
        key = str(expanded)

        if key in seen:
            continue

        seen.add(key)

        if _is_executable(expanded):
            resolved = expanded.resolve()
            return ToolStatus(
                name=name,
                found=True,
                path=str(resolved),
                source=source,
                managed=_is_managed_path(resolved),
            )

    return ToolStatus(name=name, found=False)


def _run(
    command: list[str],
    *,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
    )


def _version(status: ToolStatus) -> str | None:
    if not status.found or not status.path:
        return None

    try:
        result = _run([status.path, "--version"], timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None

    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0] if text else None


def _opencode_auth(path: str) -> tuple[bool, str]:
    try:
        result = _run(
            [path, "auth", "list", "--format", "json"],
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, "unable to query OpenCode authentication"

    if result.returncode != 0:
        return False, "OpenCode authentication not configured"

    raw = result.stdout.strip()

    if not raw:
        return False, "no OpenCode accounts configured"

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Do not inspect or expose credential contents.
        return True, "OpenCode reports configured authentication"

    if isinstance(payload, list):
        ok = len(payload) > 0
    elif isinstance(payload, dict):
        ok = len(payload) > 0
    else:
        ok = bool(payload)

    return (
        (True, "OpenCode reports configured authentication")
        if ok
        else (False, "no OpenCode accounts configured")
    )


def _codex_auth(path: str) -> tuple[bool, str]:
    try:
        result = _run([path, "login", "status"], timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False, "unable to query Codex login"

    text = "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part
    )

    ok = result.returncode == 0 and "logged in" in text.lower()

    if ok:
        if "chatgpt" in text.lower():
            return True, "Logged in using ChatGPT"
        return True, "Codex reports an active login"

    return False, "Codex is not logged in"


def inspect_tool(name: str) -> ToolStatus:
    status = resolve_tool(name)

    if not status.found:
        return status

    status.version = _version(status)

    if name == "opencode":
        status.authenticated, status.auth_detail = _opencode_auth(status.path or "")
    elif name == "codex":
        status.authenticated, status.auth_detail = _codex_auth(status.path or "")

    return status


def check_all() -> dict[str, ToolStatus]:
    return {
        name: inspect_tool(name)
        for name in ("opencode", "codex")
    }


def _resolve_npm() -> str | None:
    candidates = [
        shutil.which("npm"),
        str(Path.home() / ".local" / "npm" / "bin" / "npm"),
        "/usr/bin/npm",
        "/usr/local/bin/npm",
    ]

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if _is_executable(path):
            return str(path.resolve())

    return None


def install_managed(name: str) -> ToolStatus:
    if name not in TOOL_SPECS:
        raise ValueError(f"Unknown tool: {name}")

    npm = _resolve_npm()

    if not npm:
        raise RuntimeError(
            "npm is required to install JORE-managed AI CLIs."
        )

    MANAGED_PREFIX.mkdir(parents=True, exist_ok=True)

    package = str(TOOL_SPECS[name]["package"])

    result = subprocess.run(
        [
            npm,
            "install",
            "--prefix",
            str(MANAGED_PREFIX),
            package,
        ],
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to install {name}.")

    status = inspect_tool(name)

    if not status.found or not status.managed:
        raise RuntimeError(
            f"{name} installation completed but JORE could not resolve "
            "the managed executable."
        )

    return status


def build_runtime_env(
    base: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(base or os.environ)

    directories: list[str] = [
        str(MANAGED_BIN),
        str(Path.home() / ".local" / "npm" / "bin"),
        str(Path.home() / ".local" / "bin"),
    ]

    for name in ("opencode", "codex"):
        status = resolve_tool(name)
        if status.found and status.path:
            directories.insert(0, str(Path(status.path).parent))

            if name == "opencode":
                env["AGENTHUB_OPENCODE_BIN"] = status.path
            elif name == "codex":
                env["AGENTHUB_CODEX_BIN"] = status.path

    existing = env.get("PATH", "").split(os.pathsep)

    merged: list[str] = []
    seen: set[str] = set()

    for item in directories + existing:
        if not item or item in seen:
            continue
        seen.add(item)
        merged.append(item)

    env["PATH"] = os.pathsep.join(merged)
    env.setdefault("CAO_MCP_REQUEST_TIMEOUT", "120")
    env.setdefault("CAO_PROVIDER_INIT_TIMEOUT", "120")

    return env


def _json_payload() -> dict[str, Any]:
    return {
        name: asdict(status)
        for name, status in check_all().items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--json", action="store_true")

    install = sub.add_parser("install")
    install.add_argument("tool", choices=["opencode", "codex"])

    args = parser.parse_args()

    if args.command == "check":
        payload = _json_payload()

        if args.json:
            print(json.dumps(payload))
        else:
            for name, item in payload.items():
                state = "FOUND" if item["found"] else "MISSING"
                print(f"{name}: {state}")
                if item["path"]:
                    print(f"  path: {item['path']}")
                if item["version"]:
                    print(f"  version: {item['version']}")
                if item["authenticated"] is not None:
                    print(f"  authenticated: {item['authenticated']}")

        return 0

    if args.command == "install":
        status = install_managed(args.tool)
        print(status.path)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
