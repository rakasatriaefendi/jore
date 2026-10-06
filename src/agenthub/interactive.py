from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agenthub.codex_driver import CodexDriver
from agenthub.model_registry import ModelInfo, ModelRegistry
from agenthub.opencode_driver import OpenCodeDriver
from agenthub.doctor import run_doctor
from agenthub.driver import (
    JOREError,
    CaoDriver,
    build_review_prompt,
    parse_review,
)
from agenthub.storage import DATA_DIR, Storage
from agenthub.ui_common import (
    ActivityStatus,
    ask_text,
    ask_yes_no,
    console,
    human_time,
    notify_error,
    notify_info,
    notify_success,
    notify_warning,
    print_brand,
    render_input_hint,
    render_status_bar,
)


FREE_MODELS = {
    "nemotron": {
        "label": "Nemotron 3 Ultra Free",
        "profile": "nemotron-developer",
    },
    "mimo": {
        "label": "MiMo V2.6 Flash Free",
        "profile": "mimo-reviewer",
    },
}

MODEL_REGISTRY = ModelRegistry()
REASONING_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "xhigh": "Extra High",
    "max": "Max",
    "ultra": "Ultra",
}


def _main_help() -> None:
    console.print(
        """
[bold]Main menu commands[/bold]

  /help      Show this help
  /models    Browse models discovered from Codex/OpenCode
  /settings  Open JORE settings
  /doctor    Run JORE Doctor
  /exit      Exit JORE

Choose a numbered menu item to continue.
""".rstrip()
    )


def _workspace_help() -> None:
    console.print(
        """
[bold]Session commands[/bold]

  /help       Show session commands
  /new        Start a new session
  /model      Change provider/model for this session
  /models     Browse all models discovered from Codex/OpenCode
  /mode       Switch Auto / Single Agent
  /status     Show current session/provider/model status
  /settings   Open JORE settings
  /sessions   Open saved JORE sessions
  /clear      Clear the visible terminal (history remains stored)
  /attempts   View attempts for this session
  /review     View the latest reviewer result
  /history    View this session's conversation
  /export     Export session to Markdown + JSON
  /doctor     Run JORE Doctor
  /back       Return to the JORE home menu
  /exit       Exit JORE

Anything else is sent as the next instruction.
""".rstrip()
    )


def _choose(
    *,
    title: str,
    options: list[tuple[str, str]],
    default_key: str | None = None,
    allow_back: bool = True,
) -> str | None:
    lookup: dict[str, str] = {}
    default_number: str | None = None

    console.print(f"\n[bold]{title}[/bold]")
    for index, (key, label) in enumerate(options, start=1):
        number = str(index)
        lookup[number] = key
        lookup[key.lower()] = key

        selected = key == default_key
        marker = "[green]●[/green]" if selected else "[dim]○[/dim]"
        console.print(f"  {marker} [cyan]{number}.[/cyan] {label}")

        if selected:
            default_number = number

    while True:
        suffix = f" ({default_number})" if default_number else ""
        value = ask_text(f"Choose [1-{len(options)}]{suffix}:")
        if not value and default_number:
            return lookup[default_number]

        lowered = value.lower()

        if lowered == "/help":
            console.print(
                "[dim]Choose a number. /back returns to the previous menu.[/dim]"
            )
            continue

        if allow_back and lowered == "/back":
            return None

        if lowered in lookup:
            return lookup[lowered]

        console.print("[red]Please select one of the available options.[/red]")


def _catalog_model_options(models: list[ModelInfo]) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    for model in models:
        label = model.label
        if model.model_id != model.label:
            label = f"{label} [dim]({model.model_id})[/dim]"
        if model.free is True:
            label += " [green]Free[/green]"
        details: list[str] = []
        if model.description:
            details.append(model.description)
        if model.reasoning_levels:
            details.append("effort: " + ", ".join(model.reasoning_levels))
        if details:
            label += f"\n      [dim]{' · '.join(details)}[/dim]"
        options.append((model.model_id, label))
    return options


def _codex_catalog(*, refresh: bool = False):
    return MODEL_REGISTRY.codex_models(refresh=refresh)


def _opencode_catalog(*, refresh: bool = False):
    return MODEL_REGISTRY.opencode_models(refresh=refresh)


def _normalize_codex_model(value: str | None) -> str | None:
    catalog = _codex_catalog()
    if not catalog.models:
        return value
    if value and any(model.model_id == value for model in catalog.models):
        return value
    return catalog.models[0].model_id


def _normalize_opencode_model(value: str | None) -> str | None:
    catalog = _opencode_catalog()
    if not catalog.models:
        return value
    if value and any(model.model_id == value for model in catalog.models):
        return value
    configured = MODEL_REGISTRY.opencode_configured_model()
    if configured and any(model.model_id == configured for model in catalog.models):
        return configured
    preferred = next(
        (
            model.model_id
            for model in catalog.models
            if model.model_id.lower().endswith("nemotron-3-ultra-free")
        ),
        None,
    )
    return preferred or catalog.models[0].model_id


def _choose_codex_model(current: str | None = None) -> str | None:
    catalog = _codex_catalog()
    if catalog.warning:
        console.print(f"[yellow]! {catalog.warning}[/yellow]")
    if not catalog.models:
        console.print("[red]No selectable Codex models were discovered.[/red]")
        return None
    return _choose(
        title=f"Codex models · {catalog.source}",
        options=_catalog_model_options(catalog.models),
        default_key=_normalize_codex_model(current),
    )


def _choose_opencode_model(current: str | None = None) -> str | None:
    catalog = _opencode_catalog()
    if catalog.warning:
        console.print(f"[yellow]! {catalog.warning}[/yellow]")
    if not catalog.models:
        console.print("[red]No OpenCode models were discovered.[/red]")
        return None
    return _choose(
        title=f"OpenCode models · {catalog.source}",
        options=_catalog_model_options(catalog.models),
        default_key=_normalize_opencode_model(current),
    )


def _codex_model_info(model_id: str | None) -> ModelInfo | None:
    if not model_id:
        return None
    return next(
        (model for model in _codex_catalog().models if model.model_id == model_id),
        None,
    )


def _opencode_model_info(model_id: str | None) -> ModelInfo | None:
    if not model_id:
        return None
    return next(
        (model for model in _opencode_catalog().models if model.model_id == model_id),
        None,
    )


def _codex_model_label(model_id: str | None) -> str:
    info = _codex_model_info(model_id)
    if info:
        return f"{info.label} ({info.model_id})"
    return model_id or "Auto"


def _opencode_model_label(model_id: str | None) -> str:
    info = _opencode_model_info(model_id)
    if info:
        return f"{info.label} ({info.model_id})"
    return model_id or "Auto"


def _choose_codex_reasoning(model_id: str | None, current: str | None) -> str | None:
    info = _codex_model_info(model_id)
    levels = list(info.reasoning_levels) if info and info.reasoning_levels else [
        "low",
        "medium",
        "high",
        "xhigh",
    ]
    default = current if current in levels else None
    if default is None and info and info.default_reasoning in levels:
        default = info.default_reasoning
    if default is None:
        default = "medium" if "medium" in levels else levels[0]
    return _choose(
        title="Codex reasoning effort",
        options=[(level, REASONING_LABELS.get(level, level.title())) for level in levels],
        default_key=default,
    )


def _render_provider_models(provider: str, *, refresh: bool = False) -> None:
    if provider == "codex":
        catalog = _codex_catalog(refresh=refresh)
        title = "Codex models"
    else:
        catalog = _opencode_catalog(refresh=refresh)
        title = "OpenCode models"

    console.print(f"\n[bold]{title}[/bold]")
    console.print(f"[dim]Source: {catalog.source} · {len(catalog.models)} model(s)[/dim]")
    if catalog.warning:
        console.print(f"[yellow]! {catalog.warning}[/yellow]")
    if not catalog.models:
        console.print("[dim]No models available.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Model")
    table.add_column("Provider", style="dim")
    table.add_column("Reasoning / Access")
    for index, model in enumerate(catalog.models, start=1):
        extra = ""
        if provider == "codex":
            extra = ", ".join(model.reasoning_levels) or "provider default"
        elif model.free is True:
            extra = "Free"
        table.add_row(
            str(index),
            f"{model.label}\n[dim]{model.model_id}[/dim]",
            model.native_provider or provider,
            extra,
        )
    console.print(table)


def run_models_menu(storage: Storage, *, direct: bool = False) -> str:
    while True:
        codex = _codex_catalog()
        opencode = _opencode_catalog()
        body = Text()
        body.append(
            f"  ◈  1. Codex      ", style="bold bright_cyan"
        )
        body.append(f"{len(codex.models)} selectable model(s)\n", style="white")
        body.append(
            f"  ◇  2. OpenCode   ", style="bold dark_orange3"
        )
        body.append(f"{len(opencode.models)} available model(s)\n", style="white")
        body.append("  ↻  3. Refresh provider catalogs\n", style="white")
        body.append("  ←  4. Back", style="dim")
        console.print(
            Panel(
                body,
                title="[bold]◉ Provider Models[/bold]",
                subtitle="[dim]live catalogs from provider CLIs[/dim]",
                border_style="bright_black",
                padding=(1, 2),
            )
        )
        if codex.warning:
            console.print(f"[yellow]! Codex:[/yellow] [dim]{codex.warning}[/dim]")
        if opencode.warning:
            console.print(f"[yellow]! OpenCode:[/yellow] [dim]{opencode.warning}[/dim]")
        choice = ask_text("[bold bright_cyan]❯[/bold bright_cyan] [dim]Choose 1-4[/dim]").lower()
        if choice == "1":
            value = _choose_codex_model(storage.get_setting("codex_default_model"))
            if value:
                storage.set_setting("codex_default_model", value)
        elif choice == "2":
            value = _choose_opencode_model(storage.get_setting("opencode_default_model"))
            if value:
                storage.set_setting("opencode_default_model", value)
        elif choice == "3":
            with ActivityStatus("Refreshing provider model catalogs"):
                codex = _codex_catalog(refresh=True)
                opencode = _opencode_catalog(refresh=True)
            notify_success(
                f"Codex {len(codex.models)} models · OpenCode {len(opencode.models)} models",
                title="Catalog refreshed",
            )
        elif choice in {"4", "/back", "back", "b"}:
            return "back"
        else:
            console.print("[red]Please select 1-4.[/red]")


def _model_label(session) -> str:
    if session.primary_model == "codex":
        return f"Codex · {_codex_model_label(session.codex_model)}"
    if session.primary_model.startswith("opencode:"):
        model_id = session.primary_model.split(":", 1)[1]
        return f"OpenCode · {_opencode_model_label(model_id)}"
    return FREE_MODELS.get(
        session.primary_model,
        {"label": session.primary_model},
    )["label"]


def _reviewer_label(session) -> str:
    if not session.reviewer_model:
        return "Off"
    return FREE_MODELS.get(
        session.reviewer_model,
        {"label": session.reviewer_model},
    )["label"]


def _print_session_header(session) -> None:
    body = Text()
    body.append("◈ ", style="bright_cyan")
    body.append(f"{session.title}\n", style="bold white")
    body.append("mode  ", style="bright_black")
    body.append(f"{session.mode.title()}  ", style="white")
    body.append("model  ", style="bright_black")
    body.append(f"{_model_label(session)}\n", style="bright_cyan")
    body.append("review ", style="bright_black")
    if session.mode == "auto":
        body.append(_reviewer_label(session), style="dark_orange3")
    else:
        body.append("Off", style="bright_black")
    body.append("  cwd  ", style="bright_black")
    body.append(str(Path.cwd()), style="dim")
    console.print(
        Panel(
            body,
            title="[bold dark_orange3]✦ JORE Session[/bold dark_orange3]",
            subtitle="[dim]/status for details[/dim]",
            border_style="dark_orange3",
            padding=(1, 2),
        )
    )


def _build_prompt(storage: Storage, session_id: str, instruction: str) -> str:
    context = storage.build_recent_context(session_id)
    if not context:
        return instruction.strip()

    return f"""
Continue this JORE session using only the relevant context below.

RECENT SESSION CONTEXT:
{context}

CURRENT USER REQUEST:
{instruction.strip()}

Answer the current request. Do not repeat the context unless useful.
""".strip()


def _show_result(title: str, content: str, style: str = "cyan") -> None:
    icon = "✓" if style == "green" else "!" if style == "yellow" else "◆"
    console.print(
        Panel(
            Text(content),
            title=f"[bold {style}]{icon} {title}[/bold {style}]",
            border_style=style,
            padding=(1, 2),
        )
    )


def _run_free_agent(
    driver: CaoDriver,
    *,
    model_key: str,
    prompt: str,
    role_label: str,
):
    info = FREE_MODELS[model_key]
    with ActivityStatus(
        f"{info['label']} working",
        stages=(
            "preparing context",
            "starting agent",
            "waiting for model response",
            "finalizing response",
        ),
    ) as activity:
        result = driver.run_agent(
            profile=info["profile"],
            prompt=prompt,
            label=role_label,
        )
    notify_success(
        f"{info['label']} finished in {activity.elapsed}s",
        title="Agent complete",
    )
    return result


def _execute_turn(
    storage: Storage,
    session_id: str,
    instruction: str,
    *,
    cao_driver: CaoDriver | None,
) -> CaoDriver | None:
    session = storage.get_session(session_id)
    prompt = _build_prompt(storage, session_id, instruction)

    storage.ensure_title_from_first_prompt(session_id, instruction)
    storage.add_message(session_id, "user", instruction)
    attempt_number = storage.next_attempt_number(session_id)

    try:
        if session.primary_model == "codex":
            codex = CodexDriver(Path.cwd())
            model = _normalize_codex_model(session.codex_model)
            if not model:
                raise JOREError(
                    "No Codex model is available. Open /models or run agenthub doctor."
                )
            reasoning = session.codex_reasoning or "medium"
            info = _codex_model_info(model)
            if info and info.reasoning_levels and reasoning not in info.reasoning_levels:
                reasoning = info.default_reasoning or info.reasoning_levels[0]

            if session.codex_model != model or session.codex_reasoning != reasoning:
                storage.update_session(
                    session_id,
                    codex_model=model,
                    codex_reasoning=reasoning,
                )

            with ActivityStatus(
                f"Codex · {model}",
                stages=(
                    "preparing context",
                    f"starting {model}",
                    f"reasoning: {reasoning}",
                    "waiting for response",
                    "finalizing response",
                ),
            ) as activity:
                result = codex.run_agent(
                    prompt=prompt,
                    model=model,
                    reasoning=reasoning,
                    sandbox="read-only",
                    label="codex",
                )

            notify_success(
                f"Codex · {model} finished in {activity.elapsed}s",
                title="Provider complete",
            )
            storage.add_attempt(
                session_id=session_id,
                attempt_number=attempt_number,
                agent_role="primary",
                model=f"codex:{model}:{reasoning}",
                prompt=prompt,
                output=result.output,
                status="completed",
            )
            storage.add_message(session_id, "assistant", result.output)
            storage.update_session(session_id, last_verdict=None, status="active")
            _show_result(f"Codex · {model}", result.output)
            return cao_driver

        if session.primary_model.startswith("opencode:"):
            model = session.primary_model.split(":", 1)[1]
            driver = OpenCodeDriver(Path.cwd())
            with ActivityStatus(
                f"OpenCode · {model}",
                stages=(
                    "preparing context",
                    f"starting {model}",
                    "waiting for response",
                    "finalizing response",
                ),
            ) as activity:
                result = driver.run_agent(
                    prompt=prompt,
                    model=model,
                    label="opencode",
                )
            notify_success(
                f"OpenCode · {model} finished in {activity.elapsed}s",
                title="Provider complete",
            )
            storage.add_attempt(
                session_id=session_id,
                attempt_number=attempt_number,
                agent_role="primary",
                model=f"opencode:{model}",
                prompt=prompt,
                output=result.output,
                status="completed",
            )
            storage.add_message(session_id, "assistant", result.output)
            storage.update_session(session_id, last_verdict=None, status="active")
            _show_result(f"OpenCode · {model}", result.output)
            return cao_driver

        # Auto mode keeps the proven CAO/OpenCode profiles for orchestration.
        if session.primary_model not in FREE_MODELS:
            raise JOREError(f"Unknown JORE primary model: {session.primary_model}")

        if cao_driver is None:
            cao_driver = CaoDriver(Path.cwd())

        result = _run_free_agent(
            cao_driver,
            model_key=session.primary_model,
            prompt=prompt,
            role_label="primary",
        )

        primary_label = FREE_MODELS[session.primary_model]["label"]
        storage.add_attempt(
            session_id=session_id,
            attempt_number=attempt_number,
            agent_role="primary",
            model=primary_label,
            prompt=prompt,
            output=result.output,
            status="completed",
        )
        storage.add_message(session_id, "assistant", result.output)
        _show_result(primary_label, result.output)

        auto_review = (
            session.mode == "auto"
            and session.reviewer_model
            and storage.get_setting("automatic_review", "true") == "true"
        )

        if not auto_review:
            storage.update_session(session_id, last_verdict=None, status="active")
            return cao_driver

        review_key = session.reviewer_model
        review_prompt = build_review_prompt(instruction, result.output)
        reviewer = _run_free_agent(
            cao_driver,
            model_key=review_key,
            prompt=review_prompt,
            role_label="reviewer",
        )
        review = parse_review(reviewer.output)
        review_label = FREE_MODELS[review_key]["label"]
        storage.add_attempt(
            session_id=session_id,
            attempt_number=attempt_number,
            agent_role="reviewer",
            model=review_label,
            prompt=review_prompt,
            output=reviewer.output,
            status=review.verdict,
        )
        storage.add_message(session_id, "reviewer", reviewer.output)
        storage.update_session(
            session_id,
            last_verdict=review.verdict,
            status="active",
        )
        style = "green" if review.verdict == "PASS" else "yellow"
        _show_result(f"Review — {review.verdict}", review.review, style=style)
        return cao_driver

    except KeyboardInterrupt:
        storage.add_attempt(
            session_id=session_id,
            attempt_number=attempt_number,
            agent_role="primary",
            model=_model_label(session),
            prompt=prompt,
            output="",
            status="interrupted",
            error="Interrupted by user",
        )
        notify_warning(
            "Current run was interrupted. The session remains open.",
            title="Interrupted",
        )
        return cao_driver

    except Exception as exc:
        storage.add_attempt(
            session_id=session_id,
            attempt_number=attempt_number,
            agent_role="primary",
            model=_model_label(session),
            prompt=prompt,
            output="",
            status="failed",
            error=str(exc),
        )
        storage.update_session(session_id, status="failed")
        notify_error(
            str(exc),
            title="JORE run failed",
        )
        console.print(
            "[dim]Session preserved • use /model, /attempts, /status, or /back[/dim]"
        )
        return cao_driver


def _show_conversation(storage: Storage, session_id: str) -> None:
    messages = storage.get_messages(session_id)
    console.print(
        Panel(
            "[bold]Conversation timeline[/bold]",
            title="[bright_cyan]◈ History[/bright_cyan]",
            border_style="bright_black",
            padding=(0, 1),
        )
    )

    if not messages:
        notify_info("No messages yet.", title="Conversation is empty")
        return

    styles = {
        "user": "cyan",
        "assistant": "green",
        "reviewer": "yellow",
        "system": "bright_black",
    }

    for message in messages:
        title = message.role.title()
        console.print(
            Panel(
                Text(message.content),
                title=title,
                border_style=styles.get(message.role, "bright_black"),
                padding=(0, 1),
            )
        )


def _show_attempts(storage: Storage, session_id: str) -> None:
    attempts = storage.get_attempts(session_id)
    console.print(
        Panel(
            "[bold]Run attempts[/bold]",
            title="[bright_cyan]↻ Attempts[/bright_cyan]",
            border_style="bright_black",
            padding=(0, 1),
        )
    )
    if not attempts:
        notify_info("No attempts yet.", title="Nothing to show")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Role", width=10)
    table.add_column("Model")
    table.add_column("Status")
    table.add_column("When", style="dim")

    for item in attempts:
        status_style = (
            "green"
            if item.status in {"completed", "PASS"}
            else "yellow"
            if item.status in {"NEEDS_FIX", "interrupted"}
            else "red"
        )
        table.add_row(
            str(item.attempt_number),
            item.agent_role,
            item.model,
            f"[{status_style}]{item.status}[/{status_style}]",
            human_time(item.created_at),
        )

    console.print(table)

    failed = [x for x in attempts if x.error]
    if failed:
        console.print("\n[bold]Errors[/bold]")
        for item in failed[-3:]:
            console.print(
                f"  Attempt {item.attempt_number}: [red]{item.error}[/red]"
            )


def _show_latest_review(storage: Storage, session_id: str) -> None:
    reviews = [
        message
        for message in storage.get_messages(session_id)
        if message.role == "reviewer"
    ]
    if not reviews:
        console.print("[dim]No reviewer result yet.[/dim]")
        return
    _show_result("Latest Review", reviews[-1].content, style="yellow")


def _configure_model(storage: Storage, session_id: str) -> None:
    session = storage.get_session(session_id)

    if session.mode == "auto":
        selected = _choose(
            title="Auto primary model",
            options=[
                ("nemotron", "Nemotron 3 Ultra Free"),
                ("mimo", "MiMo V2.6 Flash Free"),
            ],
            default_key=(
                session.primary_model
                if session.primary_model in FREE_MODELS
                else "nemotron"
            ),
        )
        if selected:
            storage.update_session(session_id, primary_model=selected)
        return

    provider_default = "codex" if session.primary_model == "codex" else "opencode"
    provider = _choose(
        title="Single Agent provider",
        options=[
            ("opencode", "OpenCode — all models visible to your configured providers"),
            ("codex", "Codex — all models visible to your Codex account"),
        ],
        default_key=provider_default,
    )
    if provider is None:
        return

    if provider == "opencode":
        current = (
            session.primary_model.split(":", 1)[1]
            if session.primary_model.startswith("opencode:")
            else storage.get_setting("opencode_default_model")
        )
        model = _choose_opencode_model(current)
        if model is None:
            return
        storage.set_setting("opencode_default_model", model)
        storage.update_session(
            session_id,
            primary_model=f"opencode:{model}",
            codex_model=None,
            codex_reasoning=None,
        )
        return

    current_codex = (
        session.codex_model
        or storage.get_setting("codex_default_model")
    )
    model = _choose_codex_model(current_codex)
    if model is None:
        return
    reasoning = _choose_codex_reasoning(
        model,
        session.codex_reasoning
        or storage.get_setting("codex_default_reasoning", "medium"),
    )
    if reasoning is None:
        return
    storage.set_setting("codex_default_model", model)
    storage.set_setting("codex_default_reasoning", reasoning)
    storage.update_session(
        session_id,
        primary_model="codex",
        codex_model=model,
        codex_reasoning=reasoning,
    )


def _configure_mode(storage: Storage, session_id: str) -> None:
    session = storage.get_session(session_id)
    mode = _choose(
        title="Mode",
        options=[
            ("auto", "Auto — free primary + automatic reviewer"),
            ("single", "Single Agent — selected model only"),
        ],
        default_key=session.mode,
    )
    if mode is None:
        return

    if mode == "auto":
        primary = session.primary_model
        if primary not in FREE_MODELS:
            primary = (
                storage.get_setting("default_free_model", "nemotron")
                or "nemotron"
            )
        storage.update_session(
            session_id,
            mode="auto",
            primary_model=primary,
            reviewer_model=(
                storage.get_setting("reviewer_model", "mimo") or "mimo"
            ),
            codex_model=None,
            codex_reasoning=None,
        )
    else:
        storage.update_session(
            session_id,
            mode="single",
            reviewer_model=None,
        )

    _configure_model(storage, session_id)



def _estimate_context_tokens(storage: Storage, session_id: str) -> int:
    """Cheap local estimate for the status bar.

    Provider-native token usage is intentionally not fabricated. The "~" shown
    in the UI communicates that this is a local approximation.
    """
    total_chars = sum(
        len(message.content)
        for message in storage.get_messages(session_id)
    )
    return max(0, total_chars // 4)


def _session_elapsed_seconds(created_at: str) -> int:
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0, int((now - created.astimezone(timezone.utc)).total_seconds()))
    except (TypeError, ValueError):
        return 0


def _render_session_status_bar(storage: Storage, session_id: str) -> None:
    session = storage.get_session(session_id)
    render_status_bar(
        model=_model_label(session),
        mode=session.mode.title(),
        context_tokens=_estimate_context_tokens(storage, session_id),
        messages=len(storage.get_messages(session_id)),
        attempts=len(storage.get_attempts(session_id)),
        cost=None,
        elapsed_seconds=_session_elapsed_seconds(session.created_at),
        verdict=session.last_verdict,
    )


def _show_session_status(storage: Storage, session_id: str) -> None:
    session = storage.get_session(session_id)
    attempts = storage.get_attempts(session_id)
    messages = storage.get_messages(session_id)
    body = Text()
    body.append(f"{session.title}\n", style="bold white")
    body.append(f"Mode      {session.mode.title()}\n", style="white")
    body.append(f"Model     {_model_label(session)}\n", style="bright_cyan")
    body.append(
        f"Reviewer  {_reviewer_label(session) if session.mode == 'auto' else 'Off'}\n",
        style="dark_orange3",
    )
    body.append(f"Verdict   {session.last_verdict or '-'}\n")
    body.append(f"Messages  {len(messages)}\n")
    body.append(f"Runs      {len(attempts)}\n")
    body.append(f"Context   ~{_estimate_context_tokens(storage, session_id)} local-est. tokens\n")
    body.append(f"Updated   {human_time(session.updated_at)}\n", style="dim")
    body.append(f"Working   {Path.cwd()}\n", style="dim")
    body.append(f"SQLite    {storage.db_path}", style="dim")
    console.print(
        Panel(
            body,
            title="[bold bright_cyan]◆ Session Status[/bold bright_cyan]",
            border_style="bright_cyan",
            padding=(1, 2),
        )
    )


def session_workspace(storage: Storage, session_id: str) -> str:
    cao_driver: CaoDriver | None = None

    try:
        while True:
            session = storage.get_session(session_id)
            console.print()
            _print_session_header(session)
            _render_session_status_bar(storage, session_id)
            console.print(
                "[dim]/help  /model  /models  /status  /sessions  /export  /back  /exit[/dim]"
            )
            render_input_hint()
            console.print()

            try:
                value = ask_text("[bold bright_cyan]❯[/bold bright_cyan]")
            except KeyboardInterrupt:
                notify_warning(
                    "Nothing was sent. Use /back or /exit to leave the session.",
                    title="Input interrupted",
                )
                continue
            except EOFError:
                return "exit"

            if not value:
                continue

            command = value.strip().lower()

            if command == "/help":
                _workspace_help()
                continue
            if command == "/new":
                storage.update_session(session_id, status="active")
                return "new"
            if command == "/model":
                _configure_model(storage, session_id)
                continue
            if command == "/models":
                run_models_menu(storage)
                continue
            if command == "/mode":
                _configure_mode(storage, session_id)
                continue
            if command == "/status":
                _show_session_status(storage, session_id)
                continue
            if command == "/settings":
                run_settings_menu(storage)
                continue
            if command == "/sessions":
                run_history_menu(storage)
                continue
            if command == "/clear":
                console.clear()
                continue
            if command == "/attempts":
                _show_attempts(storage, session_id)
                continue
            if command == "/review":
                _show_latest_review(storage, session_id)
                continue
            if command == "/history":
                _show_conversation(storage, session_id)
                continue
            if command == "/export":
                md, js = storage.export_session(session_id)
                notify_success(
                    f"Markdown: {md}\nJSON: {js}",
                    title="Session exported",
                )
                continue
            if command == "/doctor":
                run_doctor()
                continue
            if command == "/back":
                storage.update_session(session_id, status="active")
                return "back"
            if command == "/exit":
                storage.update_session(session_id, status="active")
                return "exit"

            cao_driver = _execute_turn(
                storage,
                session_id,
                value,
                cao_driver=cao_driver,
            )

    finally:
        if cao_driver is not None:
            console.print("\n[dim]Cleaning up JORE runtime...[/dim]")
            cao_driver.close()


def run_new_session(storage: Storage) -> str:
    default_mode = storage.get_setting("default_mode", "auto") or "auto"
    mode = _choose(
        title="New session · Mode",
        options=[
            ("auto", "Auto — proven free primary + automatic reviewer"),
            ("single", "Single Agent — choose OpenCode or Codex + model"),
        ],
        default_key=default_mode,
    )
    if mode is None:
        return "back"

    default_free = storage.get_setting("default_free_model", "nemotron") or "nemotron"

    if mode == "auto":
        primary = _choose(
            title="Auto primary model",
            options=[
                ("nemotron", "Nemotron 3 Ultra Free"),
                ("mimo", "MiMo V2.6 Flash Free"),
            ],
            default_key=default_free,
        )
        if primary is None:
            return "back"

        reviewer = storage.get_setting("reviewer_model", "mimo") or "mimo"
        session = storage.create_session(
            mode="auto",
            primary_model=primary,
            reviewer_model=reviewer,
        )
        return session_workspace(storage, session.id)

    provider = _choose(
        title="Single Agent provider",
        options=[
            ("opencode", "OpenCode — use any model exposed by `opencode models`"),
            ("codex", "Codex — use any selectable model exposed by Codex"),
        ],
        default_key="codex",
    )
    if provider is None:
        return "back"

    if provider == "opencode":
        model = _choose_opencode_model(storage.get_setting("opencode_default_model"))
        if model is None:
            return "back"
        storage.set_setting("opencode_default_model", model)
        session = storage.create_session(
            mode="single",
            primary_model=f"opencode:{model}",
        )
        return session_workspace(storage, session.id)

    codex_model = _choose_codex_model(storage.get_setting("codex_default_model"))
    if codex_model is None:
        return "back"
    codex_reasoning = _choose_codex_reasoning(
        codex_model,
        storage.get_setting("codex_default_reasoning", "medium"),
    )
    if codex_reasoning is None:
        return "back"

    storage.set_setting("codex_default_model", codex_model)
    storage.set_setting("codex_default_reasoning", codex_reasoning)
    session = storage.create_session(
        mode="single",
        primary_model="codex",
        codex_model=codex_model,
        codex_reasoning=codex_reasoning,
    )
    return session_workspace(storage, session.id)


def _history_summary(session) -> str:
    if session.mode == "auto":
        primary = FREE_MODELS.get(
            session.primary_model,
            {"label": session.primary_model},
        )["label"]
        reviewer = _reviewer_label(session)
        return f"{primary} → {reviewer}"

    return _model_label(session)


def _session_detail_menu(storage: Storage, session_id: str) -> str:
    while True:
        session = storage.get_session(session_id)
        console.print()
        console.print(f"[bold]Session: {session.title}[/bold]")
        console.print(f"[dim]{_history_summary(session)} · {human_time(session.updated_at)}[/dim]\n")
        console.print("  [cyan]1.[/cyan] Continue")
        console.print("  [cyan]2.[/cyan] View conversation")
        console.print("  [cyan]3.[/cyan] View attempts")
        console.print("  [cyan]4.[/cyan] Export / Backup")
        console.print("  [cyan]5.[/cyan] Delete")
        console.print("  [cyan]6.[/cyan] Back")

        choice = ask_text("Choose [1-6]:")

        if choice == "1":
            return session_workspace(storage, session_id)
        if choice == "2":
            _show_conversation(storage, session_id)
        elif choice == "3":
            _show_attempts(storage, session_id)
        elif choice == "4":
            md, js = storage.export_session(session_id)
            notify_success(
                f"Markdown: {md}\nJSON: {js}",
                title="Session exported",
            )
        elif choice == "5":
            if ask_yes_no(
                f"Delete '{session.title}' and its stored conversation?",
                default_yes=False,
            ):
                storage.delete_session(session_id)
                notify_success("Session deleted.", title="History updated")
                return "back"
        elif choice == "6" or choice.lower() == "/back":
            return "back"
        else:
            console.print("[red]Please select 1-6.[/red]")


def run_history_menu(storage: Storage, *, direct: bool = False) -> str:
    while True:
        sessions = storage.list_sessions(limit=20)

        console.print(
            Panel(
                "[bold]Recent sessions[/bold]\n[dim]Resume, inspect, export, or remove saved JORE work.[/dim]",
                title="[bright_cyan]◷ History[/bright_cyan]",
                border_style="bright_black",
                padding=(0, 1),
            )
        )
        if not sessions:
            notify_info("No saved sessions yet.", title="History is empty")
            if direct:
                return "back"
            ask_text("Press Enter to go back")
            return "back"

        for index, session in enumerate(sessions, start=1):
            verdict = session.last_verdict or (
                "Single" if session.mode == "single" else "—"
            )
            verdict_style = (
                "green" if verdict == "PASS"
                else "yellow" if verdict == "NEEDS_FIX"
                else "bright_black"
            )
            console.print(
                f"[bright_cyan]◷ {index}.[/bright_cyan] [bold]{session.title}[/bold]\n"
                f"   [dim]{human_time(session.updated_at)}[/dim]  "
                f"[white]{_history_summary(session)}[/white]  "
                f"[{verdict_style}]{verdict}[/{verdict_style}]\n"
            )

        value = ask_text(
            f"Choose session [1-{len(sessions)}] or /back:"
        ).lower()

        if value in {"/back", "back", "b"}:
            return "back"

        try:
            index = int(value) - 1
        except ValueError:
            console.print("[red]Choose a session number or /back.[/red]")
            continue

        if not 0 <= index < len(sessions):
            console.print("[red]Session number is out of range.[/red]")
            continue

        action = _session_detail_menu(storage, sessions[index].id)
        if action in {"exit", "new"}:
            return action


def run_settings_menu(storage: Storage, *, direct: bool = False) -> str:
    while True:
        settings = storage.all_settings()

        codex_model = _normalize_codex_model(settings.get("codex_default_model"))
        if codex_model and settings.get("codex_default_model") != codex_model:
            storage.set_setting("codex_default_model", codex_model)
            settings["codex_default_model"] = codex_model

        opencode_model = _normalize_opencode_model(settings.get("opencode_default_model"))
        if opencode_model and settings.get("opencode_default_model") != opencode_model:
            storage.set_setting("opencode_default_model", opencode_model)
            settings["opencode_default_model"] = opencode_model

        console.print(
            Panel(
                "[bold]JORE preferences[/bold]\n"
                "[dim]Provider credentials stay owned by their native CLIs.[/dim]",
                title="[bright_cyan]⚙ Settings[/bright_cyan]",
                border_style="bright_black",
                padding=(0, 1),
            )
        )
        console.print(
            f"  [cyan]1.[/cyan] Default mode            : "
            f"{settings['default_mode'].title()}"
        )
        console.print(
            f"  [cyan]2.[/cyan] Auto primary            : "
            f"{FREE_MODELS[settings['default_free_model']]['label']}"
        )
        console.print(
            f"  [cyan]3.[/cyan] Auto reviewer           : "
            f"{FREE_MODELS[settings['reviewer_model']]['label']}"
        )
        console.print(
            f"  [cyan]4.[/cyan] Automatic review        : "
            f"{'Yes' if settings['automatic_review'] == 'true' else 'No'}"
        )
        console.print(
            f"  [cyan]5.[/cyan] OpenCode default model   : "
            f"{_opencode_model_label(settings.get('opencode_default_model'))}"
        )
        console.print(
            f"  [cyan]6.[/cyan] Codex default model      : "
            f"{_codex_model_label(settings.get('codex_default_model'))}"
        )
        console.print(
            f"  [cyan]7.[/cyan] Codex reasoning          : "
            f"{REASONING_LABELS.get(settings['codex_default_reasoning'], settings['codex_default_reasoning'].title())}"
        )
        console.print(
            f"  [cyan]8.[/cyan] Data directory           : {DATA_DIR}"
        )
        console.print("  [cyan]9.[/cyan] Back")
        console.print(
            "\n[dim]Model catalogs are discovered from the installed provider CLIs. "
            "Credentials remain owned by OpenCode/Codex.[/dim]"
        )

        choice = ask_text("Choose [1-9]:")

        if choice == "1":
            value = _choose(
                title="Default mode",
                options=[("auto", "Auto"), ("single", "Single Agent")],
                default_key=settings["default_mode"],
            )
            if value:
                storage.set_setting("default_mode", value)

        elif choice == "2":
            value = _choose(
                title="Auto primary",
                options=[
                    ("nemotron", "Nemotron 3 Ultra Free"),
                    ("mimo", "MiMo V2.6 Flash Free"),
                ],
                default_key=settings["default_free_model"],
            )
            if value:
                storage.set_setting("default_free_model", value)

        elif choice == "3":
            value = _choose(
                title="Auto reviewer",
                options=[
                    ("mimo", "MiMo V2.6 Flash Free"),
                    ("nemotron", "Nemotron 3 Ultra Free"),
                ],
                default_key=settings["reviewer_model"],
            )
            if value:
                storage.set_setting("reviewer_model", value)

        elif choice == "4":
            current = settings["automatic_review"] == "true"
            storage.set_setting(
                "automatic_review",
                "false" if current else "true",
            )

        elif choice == "5":
            value = _choose_opencode_model(settings.get("opencode_default_model"))
            if value:
                storage.set_setting("opencode_default_model", value)

        elif choice == "6":
            value = _choose_codex_model(settings.get("codex_default_model"))
            if value:
                storage.set_setting("codex_default_model", value)
                info = _codex_model_info(value)
                current_reasoning = settings.get("codex_default_reasoning")
                if info and info.reasoning_levels and current_reasoning not in info.reasoning_levels:
                    storage.set_setting(
                        "codex_default_reasoning",
                        info.default_reasoning or info.reasoning_levels[0],
                    )

        elif choice == "7":
            model = settings.get("codex_default_model")
            value = _choose_codex_reasoning(
                model,
                settings.get("codex_default_reasoning"),
            )
            if value:
                storage.set_setting("codex_default_reasoning", value)

        elif choice == "8":
            console.print(f"\n[bold]JORE data[/bold]\n{DATA_DIR}")
            console.print(f"SQLite: {storage.db_path}")
            console.print(f"Model cache: {MODEL_REGISTRY.cache_path}")

        elif choice == "9" or choice.lower() == "/back":
            return "back"

        else:
            console.print("[red]Please select 1-9.[/red]")


def run_app() -> int:
    storage = Storage()

    while True:
        console.clear()
        print_brand()
        console.print()
        menu = Text()
        menu.append("  ✦  1. New session\n", style="bold bright_cyan")
        menu.append("  ◷  2. History\n", style="white")
        menu.append("  ◉  3. Models\n", style="white")
        menu.append("  ⚙  4. Settings\n", style="white")
        menu.append("  ✚  5. Doctor\n", style="white")
        menu.append("  ↩  6. Exit", style="dim")
        console.print(
            Panel(
                menu,
                title="[bold]Workspace[/bold]",
                border_style="bright_black",
                padding=(1, 2),
            )
        )
        recent_sessions = storage.list_sessions(limit=1)
        if recent_sessions:
            recent = recent_sessions[0]
            console.print(
                f"[dim]recent[/dim]  [bold]{recent.title}[/bold]  "
                f"[bright_black]•[/bright_black] {_history_summary(recent)}  "
                f"[bright_black]•[/bright_black] {human_time(recent.updated_at)}"
            )
        else:
            console.print("[dim]recent  no sessions yet[/dim]")

        console.print(
            "[dim]/help  /models  /settings  /doctor  /exit[/dim]\n"
        )

        try:
            choice = ask_text("[bold bright_cyan]❯[/bold bright_cyan]").lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]JORE exited.[/dim]")
            return 0

        if choice in {"1", "new", "/new"}:
            action = run_new_session(storage)
            while action == "new":
                action = run_new_session(storage)
            if action == "exit":
                notify_success("Runtime cleaned up. See you next time.", title="JORE exited")
                return 0

        elif choice in {"2", "history", "/history", "/sessions"}:
            action = run_history_menu(storage)
            if action == "new":
                action = run_new_session(storage)
                while action == "new":
                    action = run_new_session(storage)
            if action == "exit":
                return 0

        elif choice in {"3", "models", "/models"}:
            run_models_menu(storage)

        elif choice in {"4", "settings", "/settings"}:
            run_settings_menu(storage)

        elif choice in {"5", "doctor", "/doctor"}:
            run_doctor()
            ask_text("Press Enter to return")

        elif choice in {"6", "exit", "/exit", "/quit"}:
            notify_success("Runtime cleaned up. See you next time.", title="JORE exited")
            return 0

        elif choice == "/help":
            _main_help()
            ask_text("Press Enter to return")

        else:
            notify_error("Choose 1-6 or use /help.", title="Unknown choice")
            ask_text("[dim]Press Enter to continue[/dim]")


def app() -> None:
    raise SystemExit(run_app())


if __name__ == "__main__":
    app()
