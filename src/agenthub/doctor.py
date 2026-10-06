from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

from rich.console import Console
from rich.table import Table

from agenthub.dependencies import check_all, install_managed
from agenthub.model_registry import ModelRegistry
from agenthub.projects import windows_drive_bridge_status


console = Console()


def _resolve_runtime_tool(name: str) -> str | None:
    candidates = [
        shutil.which(name),
        str(Path.home() / ".local" / "bin" / name),
        str(Path.home() / ".cargo" / "bin" / name),
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
    ]

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path.resolve())

    return None


def _version(path: str, *args: str) -> str | None:
    try:
        result = subprocess.run(
            [path, *args],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0] if text else None


def _yes_no(prompt: str, default_yes: bool) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        answer = input(f"{prompt} {suffix}: ").strip().lower()
    except EOFError:
        return False

    if not answer:
        return default_yes

    return answer in {"y", "yes"}


def run_doctor(*, allow_repair: bool = True) -> int:
    console.print("\n[bold green]JORE Doctor[/bold green]\n")

    runtime_ok = True

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("State", width=2)
    table.add_column("Tool", width=12)
    table.add_column("Version")
    table.add_column("Path", style="dim")

    python_path = sys.executable
    table.add_row("✓", "Python", sys.version.split()[0], python_path)

    try:
        tui_version = package_version("prompt-toolkit")
        table.add_row("✓", "TUI", f"prompt-toolkit {tui_version}", "full-screen frontend")
    except PackageNotFoundError:
        table.add_row("✗", "TUI", "prompt-toolkit missing", "")
        runtime_ok = False

    uv_path = _resolve_runtime_tool("uv")
    if uv_path:
        table.add_row("✓", "uv", _version(uv_path, "--version") or "installed", uv_path)
    else:
        table.add_row("✗", "uv", "missing", "")
        runtime_ok = False

    tmux_path = _resolve_runtime_tool("tmux")
    if tmux_path:
        table.add_row("✓", "tmux", _version(tmux_path, "-V") or "installed", tmux_path)
    else:
        table.add_row("✗", "tmux", "missing", "")
        runtime_ok = False

    runtime_home = Path(
        os.environ.get(
            "JORE_RUNTIME_HOME",
            str(Path.home() / ".local" / "share" / "jore" / "runtime" / "current"),
        )
    ).expanduser()
    frozen_app = runtime_home / "app" / ".venv" / "bin" / "jore"
    if frozen_app.is_file():
        table.add_row(
            "✓",
            "Runtime",
            "frozen clean release",
            str(runtime_home),
        )
    else:
        table.add_row(
            "✗",
            "Runtime",
            "frozen runtime missing",
            str(runtime_home),
        )
        runtime_ok = False

    launcher = Path.home() / ".local" / "bin" / "jore"
    if launcher.exists():
        table.add_row("✓", "Launcher", "jore", str(launcher))
    else:
        table.add_row("✗", "Launcher", "missing", str(launcher))
        runtime_ok = False

    windows_cwd = os.environ.get("JORE_WINDOWS_CWD", "").strip()
    match = __import__("re").match(r"^([A-Za-z]):", windows_cwd)
    if match:
        ok, detail = windows_drive_bridge_status(match.group(1))
        table.add_row(
            "✓" if ok else "!",
            "Win bridge",
            "Windows-backed" if ok else "unavailable",
            detail,
        )
    else:
        conf = Path("/etc/wsl.conf")
        conf_text = conf.read_text(encoding="utf-8", errors="replace") if conf.is_file() else ""
        if __import__("re").search(r"(?mi)^\s*enabled\s*=\s*false\s*$", conf_text):
            table.add_row(
                "!",
                "Win bridge",
                "automount disabled",
                "Windows-path projects require drvfs/9p mount",
            )
        else:
            table.add_row("·", "Win bridge", "not tested", "launch JORE from a Windows folder")

    console.print(table)

    console.print("\n[bold]Providers[/bold]")
    tools = check_all()

    opencode = tools["opencode"]
    if opencode.found:
        source = "JORE-managed" if opencode.managed else opencode.source
        console.print(
            f"[green]✓[/green] OpenCode    {opencode.version or 'installed'}"
        )
        console.print(f"  [dim]{opencode.path} ({source})[/dim]")
    else:
        console.print("[red]✗[/red] OpenCode    missing")
        if allow_repair and sys.stdin.isatty():
            if _yes_no(
                "OpenCode is required for Auto/free-agent workflows. "
                "Install an JORE-managed copy now?",
                True,
            ):
                try:
                    opencode = install_managed("opencode")
                    console.print(
                        f"[green]✓[/green] OpenCode installed at {opencode.path}"
                    )
                except Exception as exc:
                    console.print(f"[red]Install failed:[/red] {exc}")

    codex = check_all()["codex"]
    if codex.found:
        source = "JORE-managed" if codex.managed else codex.source
        console.print(
            f"[green]✓[/green] Codex       {codex.version or 'installed'}"
        )
        console.print(f"  [dim]{codex.path} ({source})[/dim]")
    else:
        console.print(
            "[yellow]![/yellow] Codex       missing "
            "[dim](optional until Single Agent / escalation)[/dim]"
        )
        if allow_repair and sys.stdin.isatty():
            if _yes_no(
                "Install an JORE-managed Codex CLI now?",
                False,
            ):
                try:
                    codex = install_managed("codex")
                    console.print(
                        f"[green]✓[/green] Codex installed at {codex.path}"
                    )
                except Exception as exc:
                    console.print(f"[red]Install failed:[/red] {exc}")

    tools = check_all()
    opencode = tools["opencode"]
    codex = tools["codex"]

    console.print("\n[bold]Authentication[/bold]")
    if opencode.found:
        if opencode.authenticated:
            console.print(
                f"[green]✓[/green] OpenCode    {opencode.auth_detail}"
            )
        else:
            console.print(
                f"[yellow]![/yellow] OpenCode    "
                f"{opencode.auth_detail or 'not configured'}"
            )

    if codex.found:
        if codex.authenticated:
            console.print(
                f"[green]✓[/green] Codex       {codex.auth_detail}"
            )
        else:
            console.print(
                f"[yellow]![/yellow] Codex       "
                f"{codex.auth_detail or 'not logged in'}"
            )

    console.print(
        "\n[dim]Credentials remain owned by OpenCode/Codex. "
        "JORE never stores provider tokens.[/dim]"
    )

    console.print("\n[bold]Models[/bold]")
    registry = ModelRegistry()
    if opencode.found and opencode.authenticated:
        opencode_catalog = registry.opencode_models(refresh=False)
        console.print(
            f"[green]✓[/green] OpenCode    {len(opencode_catalog.models)} model(s) discovered "
            f"[dim]({opencode_catalog.source})[/dim]"
        )
        if opencode_catalog.warning:
            console.print(f"  [yellow]! {opencode_catalog.warning}[/yellow]")
    else:
        console.print("[yellow]![/yellow] OpenCode models require OpenCode auth")

    if codex.found and codex.authenticated:
        codex_catalog = registry.codex_models(refresh=False)
        console.print(
            f"[green]✓[/green] Codex       {len(codex_catalog.models)} selectable model(s) discovered "
            f"[dim]({codex_catalog.source})[/dim]"
        )
        if codex_catalog.warning:
            console.print(f"  [yellow]! {codex_catalog.warning}[/yellow]")
    else:
        console.print("[dim]· Codex optional[/dim]")

    ready = (
        runtime_ok
        and opencode.found
        and bool(opencode.authenticated)
    )

    console.print("\n[bold]Status[/bold]")
    if ready:
        console.print("[bold green]✓ Ready[/bold green]")
        return 0

    console.print("[bold red]✗ Not ready[/bold red]")
    return 1


def main() -> None:
    raise SystemExit(run_doctor())


if __name__ == "__main__":
    main()
