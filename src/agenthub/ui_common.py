from __future__ import annotations
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.text import Text

from agenthub.version import __version__


console = Console()

ACCENT = "#FF4FA3"
ACCENT_2 = "#FF8BC7"
MUTED = "#A4899A"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
ERROR = "#EF4444"

VERSION = __version__

JORE_ART = (
    "      ██╗ ██████╗ ██████╗ ███████╗\n"
    "      ██║██╔═══██╗██╔══██╗██╔════╝\n"
    "      ██║██║   ██║██████╔╝█████╗\n"
    " ██   ██║██║   ██║██╔══██╗██╔══╝\n"
    " ╚█████╔╝╚██████╔╝██║  ██║███████╗\n"
    "  ╚════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝\n"
    "          ♛  Y O R - E H  ♛\n"
    "       — AI TERMINAL COMPANION —"
)



def _terminal_width() -> int:
    return max(48, min(console.width or 100, 140))


def _trim(value: str, max_len: int) -> str:
    value = str(value or "")
    if len(value) <= max_len:
        return value
    if max_len <= 1:
        return value[:max_len]
    return value[: max_len - 1] + "…"


def format_duration(seconds: int | float) -> str:
    total = max(0, int(seconds))
    if total < 60:
        return f"{total}s"
    minutes, seconds_left = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {seconds_left:02d}s"
    hours, minutes_left = divmod(minutes, 60)
    return f"{hours}h {minutes_left:02d}m"


def print_brand(*, compact: bool = False) -> None:
    """JORE welcome/header surface.

    Uses only terminal-native Rich rendering so it stays portable across
    Windows Terminal, WSL, PowerShell and ordinary ANSI terminals.
    """
    width = _terminal_width()

    if compact or width < 76:
        title = Text()
        title.append("✦ JORE ", style=f"bold {ACCENT}")
        title.append(f"v{VERSION}", style=MUTED)
        title.append("\n")
        title.append("Yor-Eh · multi-agent terminal", style=MUTED)
        console.print(
            Panel(
                title,
                border_style=ACCENT,
                padding=(0, 1),
                width=min(width, 62),
            )
        )
        return

    art = Text(JORE_ART, style=f"bold {ACCENT}")
    subtitle = Text()
    subtitle.append("JORE multi-agent terminal", style="bold white")
    subtitle.append("  ·  Build. Explore. Create. Together.\n", style=MUTED)
    subtitle.append("Codex  •  OpenCode  •  Auto", style=ACCENT_2)
    subtitle.append(f"     JORE v{VERSION}", style=MUTED)

    body = Text()
    body.append_text(art)
    body.append("\n\n")
    body.append_text(subtitle)

    console.print(
        Panel(
            Align.left(body),
            title=f"[bold {ACCENT_2}]✦ Welcome to JORE[/bold {ACCENT_2}]",
            subtitle="[dim]type /help anytime[/dim]",
            border_style=ACCENT_2,
            padding=(1, 2),
            width=min(width, 86),
        )
    )


def ask_text(prompt: str, default: str | None = None) -> str:
    suffix = f" [dim]({default})[/dim]" if default is not None else ""
    try:
        value = console.input(f"{prompt}{suffix} ").strip()
    except (EOFError, KeyboardInterrupt):
        raise
    if not value and default is not None:
        return default
    return value


def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    while True:
        value = ask_text(
            f"[bold]{prompt}[/bold] [dim]{suffix}[/dim]"
        ).lower()
        if not value:
            return default_yes
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        notify_error("Please answer y or n.", title="Invalid input")


def notify_success(message: str, *, title: str = "Done") -> None:
    console.print(
        Panel(
            f"[bold {SUCCESS}]✓[/bold {SUCCESS}] {message}",
            title=f"[{SUCCESS}] {title} [/{SUCCESS}]",
            border_style=SUCCESS,
            padding=(0, 1),
        )
    )


def notify_error(message: str, *, title: str = "Error") -> None:
    console.print(
        Panel(
            f"[bold {ERROR}]✕[/bold {ERROR}] {message}",
            title=f"[{ERROR}] {title} [/{ERROR}]",
            border_style=ERROR,
            padding=(0, 1),
        )
    )


def notify_warning(message: str, *, title: str = "Warning") -> None:
    console.print(
        Panel(
            f"[bold {WARNING}]![/bold {WARNING}] {message}",
            title=f"[{WARNING}] {title} [/{WARNING}]",
            border_style=WARNING,
            padding=(0, 1),
        )
    )


def notify_info(message: str, *, title: str = "Info") -> None:
    console.print(
        Panel(
            f"[bold {ACCENT}]i[/bold {ACCENT}] {message}",
            title=f"[{ACCENT}] {title} [/{ACCENT}]",
            border_style=ACCENT,
            padding=(0, 1),
        )
    )


def human_time(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value

    now = datetime.now(timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    seconds = max(0, int(delta.total_seconds()))

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 172800:
        return "Yesterday"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"

    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def render_status_bar(
    *,
    model: str,
    mode: str,
    context_tokens: int | None = None,
    messages: int | None = None,
    attempts: int | None = None,
    cost: str | None = None,
    elapsed_seconds: int | float = 0,
    verdict: str | None = None,
) -> None:
    """Render an adaptive local session status bar.

    Context is explicitly shown as an estimate because provider-native token
    usage is not yet available from every backend.
    """
    width = _terminal_width()
    model = _trim(model, 34 if width >= 100 else 22)

    pieces: list[str] = [
        f"[bold {ACCENT}]◆ {model}[/bold {ACCENT}]",
        f"[white]{mode}[/white]",
    ]

    if width >= 62 and context_tokens is not None:
        if context_tokens >= 1000:
            token_label = f"~{context_tokens / 1000:.1f}K ctx"
        else:
            token_label = f"~{context_tokens} ctx"
        pieces.append(f"[dim]{token_label}[/dim]")

    if width >= 76 and messages is not None:
        pieces.append(f"[dim]{messages} msg[/dim]")

    if width >= 88 and attempts is not None:
        pieces.append(f"[dim]{attempts} run[/dim]")

    if width >= 100:
        pieces.append(f"[dim]$ {cost or 'n/a'}[/dim]")

    pieces.append(f"[dim]{format_duration(elapsed_seconds)}[/dim]")

    if verdict and width >= 78:
        verdict_style = SUCCESS if verdict == "PASS" else WARNING
        pieces.append(f"[{verdict_style}]{verdict}[/{verdict_style}]")

    line = " [bright_black]│[/bright_black] ".join(pieces)
    console.print(
        Panel(
            line,
            border_style="bright_black",
            padding=(0, 1),
            title="[dim]status[/dim]",
            title_align="left",
        )
    )


def render_input_hint() -> None:
    width = _terminal_width()
    if width >= 76:
        console.print(
            "[dim]✎ message[/dim]  "
            "[bright_black]•[/bright_black] [cyan]/[/cyan][dim] commands[/dim]  "
            "[bright_black]•[/bright_black] [dim]Ctrl+C interrupt[/dim]"
        )
    else:
        console.print("[dim]✎ message  •  / commands[/dim]")


class ActivityStatus:
    """Animated, staged agent progress state.

    Rich owns the spinner while a compact progress bar and elapsed clock tell
    the user that the provider is still alive.
    """

    def __init__(
        self,
        label: str,
        stages: Iterable[str] | None = None,
    ) -> None:
        self.label = label
        self.stages = list(
            stages
            or [
                "preparing context",
                "contacting provider",
                "thinking",
                "waiting for response",
                "finalizing",
            ]
        )
        self.started = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status: Status | None = None
        self._stage_index = 0

    def _bar(self, index: int) -> str:
        slots = 10
        if not self.stages:
            filled = 1
        else:
            # Never show 100% until the operation actually completes.
            fraction = min(0.9, (index + 1) / max(2, len(self.stages) + 1))
            filled = max(1, int(slots * fraction))
        return "█" * filled + "░" * (slots - filled)

    def _message(self, stage: str, index: int) -> str:
        elapsed = max(0, int(time.monotonic() - self.started))
        bar = self._bar(index)
        return (
            f"[bold {ACCENT}]✦ {self.label}[/bold {ACCENT}]  "
            f"[{ACCENT_2}]{stage}[/{ACCENT_2}]  "
            f"[dim][{bar}] {elapsed}s[/dim]"
        )

    def _loop(self) -> None:
        index = 0
        while not self._stop.wait(2.2):
            if self._status is None:
                return
            index = min(index + 1, len(self.stages) - 1)
            self._stage_index = index
            self._status.update(
                self._message(self.stages[index], index)
            )

    def __enter__(self) -> "ActivityStatus":
        self.started = time.monotonic()
        first = self.stages[0] if self.stages else "working"
        self._status = console.status(
            self._message(first, 0),
            spinner="dots12",
            spinner_style=ACCENT,
        )
        self._status.start()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.25)
        if self._status:
            self._status.stop()

    @property
    def elapsed(self) -> int:
        return max(0, int(time.monotonic() - self.started))
