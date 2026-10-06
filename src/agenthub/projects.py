from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from agenthub.storage import DATA_DIR, Storage


PROJECTS_DIR = DATA_DIR / "projects"
COMMON_CONTEXT_FILES = (
    "AGENTS.md",
    "PRD.md",
    "PLANNING.md",
    "MEMORY.md",
    "GEMINI.md",
    "README.md",
    "CONTRIBUTING.md",
)

PERMISSION_PRESETS: dict[str, dict[str, str]] = {
    "ask": {
        "label": "Ask for Approval",
        "sandbox_mode": "workspace-write",
        "approval_policy": "on-request",
        "approvals_reviewer": "user",
    },
    "approve_for_me": {
        "label": "Approve for Me",
        "sandbox_mode": "workspace-write",
        "approval_policy": "on-request",
        "approvals_reviewer": "auto_review",
    },
    "full_access": {
        "label": "Full Access",
        "sandbox_mode": "danger-full-access",
        "approval_policy": "never",
        "approvals_reviewer": "none",
    },
    "custom": {
        "label": "Custom",
        "sandbox_mode": "workspace-write",
        "approval_policy": "on-request",
        "approvals_reviewer": "user",
    },
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "project"


_WINDOWS_DRIVE_PATH = re.compile(r"^([A-Za-z]):[\\/](.*)$")
_WSL_DRIVE_PATH = re.compile(r"^/mnt/([A-Za-z])(?:/(.*))?$")


def _findmnt(path: Path) -> tuple[str, str, str] | None:
    """Return SOURCE/FSTYPE/OPTIONS for the mount containing *path*."""
    try:
        result = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE,FSTYPE,OPTIONS", "-T", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    line = (result.stdout or "").strip()
    if result.returncode != 0 or not line:
        return None

    parts = line.split(None, 2)
    if len(parts) == 2:
        parts.append("")
    if len(parts) < 2:
        return None
    return parts[0], parts[1], parts[2]


def windows_drive_bridge_status(drive: str) -> tuple[bool, str]:
    """Verify that /mnt/<drive> is really backed by the Windows drive.

    JORE never accepts a plain Linux/ext4 directory that only happens to be
    named /mnt/c or /mnt/d as a Windows workspace.
    """
    letter = drive.lower().rstrip(":")
    mountpoint = Path("/mnt") / letter

    info = _findmnt(mountpoint)
    if info is None:
        return False, f"{mountpoint} is not mounted"

    source, fstype, options = info
    source_lower = source.lower()
    options_lower = options.lower()

    expected = f"{letter}:"
    source_matches = (
        source_lower == expected
        or source_lower.startswith(expected + "\\")
        or source_lower.startswith(expected + "/")
    )
    drvfs_like = (
        fstype.lower() in {"9p", "drvfs"}
        and (
            source_matches
            or "drvfs" in options_lower
            or f"path={letter}:" in options_lower
        )
    )

    if not drvfs_like:
        return (
            False,
            f"{mountpoint} resolves to {source} ({fstype}), not Windows {letter.upper()}:",
        )

    return True, f"{mountpoint} -> {source} ({fstype})"


def assert_windows_drive_bridge(drive: str) -> None:
    ok, detail = windows_drive_bridge_status(drive)
    if ok:
        return

    letter = drive.upper().rstrip(":")
    raise ValueError(
        f"Windows workspace bridge is unavailable for {letter}: drive. "
        f"{detail}. JORE refused to create or run the project so files are not "
        "written into a fake Linux /mnt directory. Enable WSL automount or mount "
        f"{letter}: with drvfs, restart the AgentHub distro, then retry."
    )


def assert_workspace_bridge(path: Path | str) -> Path:
    """Fail closed when a /mnt/<drive> workspace is not Windows-backed."""
    candidate = Path(path).expanduser().resolve()
    match = _WSL_DRIVE_PATH.match(candidate.as_posix())
    if match:
        assert_windows_drive_bridge(match.group(1))
    return candidate


def startup_workspace_cwd() -> Path:
    """Return the real current workspace, including Windows launcher cwd."""
    windows_cwd = os.environ.get("JORE_WINDOWS_CWD", "").strip()
    if windows_cwd:
        try:
            return normalize_workspace_path(windows_cwd)
        except (ValueError, OSError):
            # Home remains usable even when the Windows bridge is unhealthy.
            # Project creation/run will still fail closed with a specific error.
            pass
    return Path.cwd().expanduser().resolve()


def windows_to_wsl_path(raw: str) -> str | None:
    value = raw.strip().strip('"')
    match = _WINDOWS_DRIVE_PATH.match(value)
    if match:
        drive = match.group(1).lower()
        assert_windows_drive_bridge(drive)
        tail = match.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{tail}"
    if value.lower().startswith("\\\\wsl.localhost\\"):
        parts = value.split("\\")
        # \\wsl.localhost\Distro\home\user -> /home/user
        if len(parts) >= 5:
            return "/" + "/".join(p for p in parts[4:] if p)
    return None


def normalize_workspace_path(raw: str | None, *, cwd: Path | None = None) -> Path:
    value = (raw or "").strip().strip('"')
    base = (cwd or Path.cwd()).expanduser()
    if not value or value == ".":
        windows_cwd = os.environ.get("JORE_WINDOWS_CWD", "").strip()
        if windows_cwd:
            mapped = windows_to_wsl_path(windows_cwd)
            if mapped:
                return assert_workspace_bridge(Path(mapped))
        return assert_workspace_bridge(base.resolve())

    mapped = windows_to_wsl_path(value)
    if mapped:
        return Path(mapped).expanduser().resolve()

    # Prefer wslpath for unusual Windows forms if available.
    if re.match(r"^[A-Za-z]:", value):
        try:
            result = subprocess.run(
                ["wslpath", "-a", value],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip()).resolve()
        except (OSError, subprocess.TimeoutExpired):
            pass

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def ensure_workspace(path: Path, *, create: bool = True) -> Path:
    path = assert_workspace_bridge(path)
    if path.exists() and not path.is_dir():
        raise ValueError(f"Workspace is not a directory: {path}")
    if not path.exists():
        if not create:
            raise FileNotFoundError(path)
        path.mkdir(parents=True, exist_ok=True)
    return path




def assert_workspace_isolated(storage: Storage, workspace: Path) -> None:
    candidate = workspace.expanduser().resolve()
    for project in storage.list_projects():
        existing = Path(project.workspace_path).expanduser().resolve()
        if candidate == existing:
            raise ValueError(
                f"Workspace is already owned by JORE project '{project.name}': {existing}"
            )
        try:
            candidate.relative_to(existing)
            raise ValueError(
                f"Workspace overlaps parent project '{project.name}': {existing}"
            )
        except ValueError as exc:
            if str(exc).startswith("Workspace overlaps"):
                raise
        try:
            existing.relative_to(candidate)
            raise ValueError(
                f"Workspace contains another project '{project.name}': {existing}"
            )
        except ValueError as exc:
            if str(exc).startswith("Workspace contains"):
                raise



def write_workspace_marker(project_id: str, project_name: str, workspace: Path) -> Path:
    marker_dir = workspace.expanduser().resolve() / ".jore"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / "project.json"
    marker.write_text(
        json.dumps({
            "project_id": project_id,
            "name": project_name,
            "format": "jore-project-v1",
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    return marker


def find_workspace_project_id(start: Path | None = None) -> str | None:
    current = (start or Path.cwd()).expanduser().resolve()
    candidates = [current, *current.parents]
    for directory in candidates:
        marker = directory / ".jore" / "project.json"
        if not marker.is_file():
            continue
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        project_id = str(payload.get("project_id") or "").strip()
        if project_id:
            return project_id
    return None

def project_data_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def context_dir(project_id: str) -> Path:
    path = project_data_dir(project_id) / "context"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_filename(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)
    return clean or "context.md"


def import_context_file(
    storage: Storage,
    project_id: str,
    source: str | Path,
    *,
    kind: str = "document",
    agent_scope: list[str] | None = None,
) -> str:
    source_path = normalize_workspace_path(str(source))
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    content = source_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    dest = context_dir(project_id) / _safe_filename(source_path.name)
    if dest.exists() and dest.read_bytes() != content:
        dest = dest.with_name(f"{dest.stem}-{digest[:8]}{dest.suffix}")
    shutil.copy2(source_path, dest)
    return storage.add_project_context(
        project_id=project_id,
        name=source_path.name,
        kind=kind,
        source_path=str(source_path),
        stored_path=str(dest),
        content_hash=digest,
        agent_scope=agent_scope or [],
    ).id


def create_context_text(
    storage: Storage,
    project_id: str,
    name: str,
    content: str,
    *,
    kind: str = "document",
    agent_scope: list[str] | None = None,
) -> str:
    encoded = content.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    dest = context_dir(project_id) / _safe_filename(name)
    dest.write_text(content, encoding="utf-8")
    return storage.add_project_context(
        project_id=project_id,
        name=Path(name).name,
        kind=kind,
        source_path=None,
        stored_path=str(dest),
        content_hash=digest,
        agent_scope=agent_scope or [],
    ).id


def auto_import_common_context(storage: Storage, project_id: str, workspace: Path) -> list[str]:
    imported: list[str] = []
    known = {item.name.lower() for item in storage.list_project_context(project_id)}
    for name in COMMON_CONTEXT_FILES:
        path = workspace / name
        if path.is_file() and name.lower() not in known:
            try:
                imported.append(import_context_file(storage, project_id, path))
            except (OSError, ValueError):
                continue
    return imported


def context_for_agent(
    storage: Storage,
    project_id: str,
    agent_name: str,
    *,
    max_chars: int = 24000,
) -> str:
    blocks: list[str] = []
    used = 0
    for item in storage.list_project_context(project_id):
        if item.agent_scope and agent_name not in item.agent_scope:
            continue
        path = Path(item.stored_path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        block = f"## {item.name}\n{text.strip()}"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining > 200:
                blocks.append(block[:remaining] + "\n...[context truncated]")
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


def workspace_contains(workspace: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False
