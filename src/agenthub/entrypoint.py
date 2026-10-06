from __future__ import annotations
import os
import sys

from rich.console import Console

from agenthub.version import APP_NAME, __version__


console = Console()


def _run_default() -> int:
    """Prefer the full-screen TUI on a real terminal.

    Set AGENTHUB_CLASSIC=1 when debugging terminal compatibility.
    """
    classic = os.environ.get("AGENTHUB_CLASSIC", "").strip() == "1"
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()

    if not classic and is_tty:
        try:
            from agenthub.storage import Storage

            enabled = (
                Storage().get_setting("tui_enabled", "true")
                or "true"
            ).lower() == "true"

            if enabled:
                from agenthub.tui import run_tui

                return run_tui()
        except Exception as exc:
            if os.environ.get("AGENTHUB_TUI_STRICT", "").strip() == "1":
                raise
            console.print(
                f"[yellow]JORE TUI unavailable:[/yellow] {exc}"
            )
            console.print(
                "[dim]Falling back to the classic Rich interface. "
                "Set AGENTHUB_TUI_STRICT=1 to debug the TUI exception.[/dim]"
            )

    from agenthub.interactive import run_app

    return run_app()


def main() -> None:
    command = sys.argv[1].lower() if len(sys.argv) >= 2 else None

    if command in {"-v", "--version", "version"}:
        console.print(f"{APP_NAME} {__version__}")
        raise SystemExit(0)

    if command in {"-h", "--help", "help"}:
        console.print(
            """
[bold]JORE[/bold]

Usage:
  jore                 Open the full-screen JORE TUI
  jore classic         Open the classic Rich interface
  jore doctor          Check runtime/providers/authentication
  jore history         Open saved session history
  jore models          Browse provider model catalogs
  jore settings        Open JORE settings
  jore project list    List JORE projects
  jore project create  Create a project (interactive args supported)
  jore project show    Show one project
  jore --version       Print JORE version

Compatibility:
  agenthub             Legacy WSL alias; Windows bridge is now `jore`

Environment:
  AGENTHUB_CLASSIC=1   Force the classic interface
  AGENTHUB_TUI_STRICT=1  Re-raise TUI startup errors instead of fallback
""".strip()
        )
        raise SystemExit(0)

    if command == "classic":
        from agenthub.interactive import run_app

        raise SystemExit(run_app())

    if command == "doctor":
        from agenthub.doctor import run_doctor

        raise SystemExit(run_doctor())

    if command == "history":
        from agenthub.interactive import run_history_menu
        from agenthub.storage import Storage

        result = run_history_menu(Storage(), direct=True)
        raise SystemExit(0 if result != "exit" else 0)

    if command == "models":
        from agenthub.interactive import run_models_menu
        from agenthub.storage import Storage

        run_models_menu(Storage(), direct=True)
        raise SystemExit(0)

    if command == "settings":
        from agenthub.interactive import run_settings_menu
        from agenthub.storage import Storage

        run_settings_menu(Storage(), direct=True)
        raise SystemExit(0)

    if command == "project":
        from agenthub.projects import PERMISSION_PRESETS, assert_workspace_isolated, ensure_workspace, normalize_workspace_path, slugify, write_workspace_marker
        from agenthub.storage import Storage
        storage = Storage()
        action = sys.argv[2].lower() if len(sys.argv) >= 3 else "list"
        if action == "list":
            projects = storage.list_projects()
            if not projects:
                console.print("[dim]No projects yet. Open `jore` and use /project new.[/dim]")
            for item in projects:
                console.print(f"[bold]{item.name}[/bold]  {item.id}  [dim]{item.workspace_path}[/dim]")
            raise SystemExit(0)
        if action == "create":
            if len(sys.argv) < 5:
                console.print("Usage: jore project create <name> <path> [ask|approve_for_me|full_access|custom]")
                raise SystemExit(2)
            name = sys.argv[3]
            workspace = ensure_workspace(normalize_workspace_path(sys.argv[4]), create=True)
            assert_workspace_isolated(storage, workspace)
            mode = sys.argv[5].lower() if len(sys.argv) >= 6 else "ask"
            if mode not in PERMISSION_PRESETS:
                console.print(f"[red]Unknown permission mode:[/red] {mode}")
                raise SystemExit(2)
            preset = PERMISSION_PRESETS[mode]
            base = slugify(name); slug = base; used = {p.slug for p in storage.list_projects(include_archived=True)}; n = 2
            while slug in used:
                slug = f"{base}-{n}"; n += 1
            project = storage.create_project(name=name, slug=slug, workspace_path=str(workspace),
                approval_mode=mode, sandbox_mode=preset["sandbox_mode"], approval_policy=preset["approval_policy"],
                approvals_reviewer=preset["approvals_reviewer"])
            write_workspace_marker(project.id, project.name, workspace)
            console.print(f"[green]Created[/green] {project.name}  {project.id}")
            console.print(f"Workspace: {project.workspace_path}")
            raise SystemExit(0)
        if action == "show":
            if len(sys.argv) < 4:
                console.print("Usage: jore project show <project-id|name|slug>"); raise SystemExit(2)
            key = sys.argv[3]
            project = next((p for p in storage.list_projects(include_archived=True) if key in {p.id,p.name,p.slug}), None)
            if project is None:
                console.print(f"[red]Project not found:[/red] {key}"); raise SystemExit(2)
            console.print(f"[bold]{project.name}[/bold]  {project.id}")
            console.print(f"Workspace: {project.workspace_path}")
            console.print(f"Isolation: {project.isolation_mode}")
            console.print(f"Permissions: {project.approval_mode} / {project.sandbox_mode} / {project.approvals_reviewer}")
            console.print(f"Agents: {len(storage.list_project_agents(project.id))}")
            console.print(f"Context docs: {len(storage.list_project_context(project.id))}")
            raise SystemExit(0)
        console.print(f"[red]Unknown project action:[/red] {action}")
        raise SystemExit(2)

    if command is not None:
        console.print(
            f"[red]Unknown command:[/red] {command}\n"
            "Run [bold]jore --help[/bold] for available commands."
        )
        raise SystemExit(2)

    raise SystemExit(_run_default())


if __name__ == "__main__":
    main()
