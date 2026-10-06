from __future__ import annotations
import asyncio
import os
import re
import time
from datetime import datetime, timezone
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Awaitable, Callable

from prompt_toolkit import Application
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    Float,
    FloatContainer,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.styles import DynamicStyle, Style
from prompt_toolkit.widgets import Frame

from agenthub.doctor import run_doctor
from agenthub.dependencies import resolve_tool
from agenthub.jore_assets import asset as jore_asset, loading_frames as jore_loading_frames, logo as jore_logo, mascot as jore_mascot
from agenthub.model_registry import ModelInfo, ModelRegistry
from agenthub.storage import Storage
from agenthub.projects import (
    PERMISSION_PRESETS,
    auto_import_common_context,
    assert_workspace_isolated,
    create_context_text,
    ensure_workspace,
    find_workspace_project_id,
    import_context_file,
    normalize_workspace_path,
    startup_workspace_cwd,
    slugify,
    write_workspace_marker,
)
from agenthub.project_runtime import ProjectTurnResult, execute_project_team
from agenthub.version import __version__
from agenthub.tui_runtime import (
    AUTO_MODELS,
    CodexEscalationResult,
    TurnResult,
    execute_codex_escalation,
    execute_repair_turn,
    execute_turn,
)


VERSION = __version__


APP_NAME = "JORE"
APP_TAGLINE = "multi-agent terminal"
APP_PRONUNCIATION = "Yor-Eh"

SLASH_COMMANDS: dict[str, str] = {
    "/help": "show JORE TUI commands and keybindings",
    "/new": "create a quick JORE chat session",
    "/projects": "open project picker",
    "/project": "project hub; use /project new to create",
    "/agents": "list agents in the active project",
    "/agent": "add/configure project agents",
    "/context": "manage project context documents",
    "/run": "run one approved goal across the project team",
    "/model": "change the current provider/model",
    "/models": "browse live Codex/OpenCode catalogs",
    "/sessions": "open the arrow-key session picker",
    "/status": "show local session + persisted RunState",
    "/runstate": "show persisted RunState / cooldown details",
    "/history": "show the conversation timeline",
    "/attempts": "show run attempts",
    "/export": "export this session to Markdown + JSON",
    "/bg": "run a prompt as a background task",
    "/tasks": "open the live/background task picker",
    "/queue": "queue a follow-up prompt",
    "/busy": "show or change busy-input behavior",
    "/dock": "toggle the live work dock",
    "/stop": "request stop for the foreground run",
    "/escalate": "open NEEDS_FIX repair / Codex escalation options",
    "/theme": "switch JORE skin/theme",
    "/settings": "change TUI behavior",
    "/doctor": "run JORE Doctor",
    "/clear": "clear transient TUI notices/events",
    "/home": "return to JORE home",
    "/back": "return to JORE home",
    "/exit": "exit JORE",
}


THEMES: dict[str, dict[str, str]] = {
    "jore": {
        "": "bg:#090C10 #FBF2EF",
        "header": "bold #FF8BC7",
        "header-area": "bg:#090C10 #FBF2EF",
        "accent": "bold #FF4FA3",
        "accent2": "#FF8BC7",
        "brand-deep": "bold #9D174D",
        "brand-mid": "bold #C2185B",
        "brand-hot": "bold #FF4FA3",
        "brand-soft": "bold #FF8BC7",
        "brand-white": "bold #FBF2EF",
        "text": "#FBF2EF",
        "soft": "#CEB5C0",
        "muted": "#A4899A",
        "disabled": "#555058",
        "border": "#3A3139",
        "frame.border": "#3A3139",
        "frame.label": "#CEB5C0",
        "status": "bg:#141014 #CEB5C0",
        "composer": "bg:#0A0D11 #FBF2EF",
        "composer-prefix": "bold #FF4FA3",
        "event": "#CEB5C0",
        "success": "bold #22C55E",
        "warning": "bold #F59E0B",
        "error": "bold #EF4444",
        "info": "#38BDF8",
        "picker": "bg:#141014 #FBF2EF",
        "picker-selected": "bg:#FF4FA3 #090C10 bold",
        "completion-menu": "bg:#141014 #FBF2EF",
        "completion-menu.completion.current": "bg:#FF4FA3 #090C10 bold",
        "completion-menu.meta.completion.current": "bg:#C2185B #FBF2EF",
        "scrollbar.background": "bg:#141014",
        "scrollbar.button": "bg:#B25888",
    },
    "claude-warm": {
        "": "bg:#090C10 #FBF2EF",
        "header": "bold #e9865b", "accent": "#e9865b", "accent2": "#d8b26e",
        "muted": "#A4899A", "border": "#704a3a", "frame.border": "#704a3a", "frame.label": "#d8b26e",
        "status": "bg:#171311 #e6dfda", "composer": "bg:#15110f #f2e8e2", "composer-prefix": "bold #e9865b",
        "event": "#d6ccc6", "success": "#22C55E", "warning": "#F59E0B", "error": "#EF4444", "info": "#38BDF8",
        "picker": "bg:#1b1512 #efe5df", "picker-selected": "bg:#6d3d2d #ffffff bold",
        "completion-menu": "bg:#1b1512 #e8dfda", "completion-menu.completion.current": "bg:#6d3d2d #ffffff",
        "completion-menu.meta.completion.current": "bg:#6d3d2d #f0d8cb", "scrollbar.background": "bg:#241b17", "scrollbar.button": "bg:#67483b",
    },
    "gemini-night": {
        "": "bg:#090C10 #FBF2EF",
        "header": "bold #8ab4f8", "accent": "#8ab4f8", "accent2": "#c58af9",
        "muted": "#A4899A", "border": "#3f4a5f", "frame.border": "#3f4a5f", "frame.label": "#8ab4f8",
        "status": "bg:#10131a #dce7ff", "composer": "bg:#0f131a #edf3ff", "composer-prefix": "bold #8ab4f8",
        "event": "#c4d5f4", "success": "#22C55E", "warning": "#F59E0B", "error": "#EF4444", "info": "#38BDF8",
        "picker": "bg:#121722 #edf3ff", "picker-selected": "bg:#334f78 #ffffff bold",
        "completion-menu": "bg:#121722 #dce7ff", "completion-menu.completion.current": "bg:#334f78 #ffffff",
        "completion-menu.meta.completion.current": "bg:#334f78 #dce7ff", "scrollbar.background": "bg:#1d2430", "scrollbar.button": "bg:#4f6380",
    },
    "mono": {
        "": "", "header": "bold", "accent": "bold", "accent2": "underline", "muted": "#777777",
        "border": "#666666", "frame.border": "#666666", "frame.label": "bold", "status": "reverse", "composer": "",
        "composer-prefix": "bold", "event": "", "success": "bold", "warning": "underline", "error": "bold reverse", "info": "underline",
        "picker": "", "picker-selected": "reverse bold", "completion-menu": "", "completion-menu.completion.current": "reverse",
        "completion-menu.meta.completion.current": "reverse", "scrollbar.background": "", "scrollbar.button": "reverse",
    },
}



@dataclass(slots=True)
class EventLine:
    timestamp: float
    kind: str
    text: str
    task_id: int | None = None


@dataclass(slots=True)
class TaskState:
    task_id: int
    label: str
    prompt: str
    background: bool
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    status: str = "running"
    detail: str = "queued"
    cancel_event: Event = field(default_factory=Event)
    output: str = ""
    error: str = ""

    @property
    def elapsed(self) -> int:
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return max(0, int(end - self.started_at))


class SlashCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/") or " " in text:
            return

        lowered = text.lower()
        for command, description in SLASH_COMMANDS.items():
            if command.startswith(lowered):
                yield Completion(
                    command,
                    start_position=-len(text),
                    display=command,
                    display_meta=description,
                )


class AgentHubTUI:
    def __init__(self) -> None:
        self.storage = Storage()
        self.registry = ModelRegistry()
        self.session_id: str | None = None
        self.active_project_id: str | None = None
        self.form_state: dict[str, str] | None = None
        self.view_mode = "home"
        marker_project = find_workspace_project_id(startup_workspace_cwd())
        if marker_project:
            try:
                self.storage.get_project(marker_project)
                self.active_project_id = marker_project
                self.view_mode = "project"
            except KeyError:
                pass

        self.events: deque[EventLine] = deque(maxlen=80)
        self.tasks: dict[int, TaskState] = {}
        self.pending_prompts: deque[str] = deque()
        self.foreground_task_id: int | None = None
        self._next_task_id = 1

        self.loop: asyncio.AbstractEventLoop | None = None
        self.last_ctrl_c = 0.0
        self.dock_visible = True
        self.dock_compact = False
        self.closed = False

        # Conversation viewport state.
        # None means follow the newest page. An integer is an absolute logical
        # line offset, so new output will not yank the user while reading back.
        self.conversation_scroll_start: int | None = None
        self.last_needs_fix_task: str | None = None
        self.last_needs_fix_result: TurnResult | None = None

        self.picker_visible = False
        self.picker_title = ""
        self.picker_options: list[tuple[str, str, str]] = []
        self.picker_index = 0
        self.picker_future: asyncio.Future[str | None] | None = None

        saved_theme = self.storage.get_setting("theme", "jore") or "jore"
        if saved_theme == "agenthub":
            saved_theme = "jore"
        self.storage.set_setting("theme", saved_theme)
        try:
            self.provider_ready = {
                "codex": resolve_tool("codex").found,
                "opencode": resolve_tool("opencode").found,
            }
        except Exception:
            self.provider_ready = {"codex": False, "opencode": False}
        self.storage.set_setting(
            "busy_input_mode",
            self.storage.get_setting("busy_input_mode", "queue") or "queue",
        )

        self.composer = Buffer(
            multiline=True,
            completer=SlashCompleter(),
            complete_while_typing=True,
        )

        self.kb = self._build_keybindings()
        self.layout = self._build_layout()
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            # Keep terminal-native mouse selection/copy available.
            # Conversation scrolling is handled by JORE keybindings.
            mouse_support=False,
            style=DynamicStyle(self._current_style),
            refresh_interval=None,
        )

        self._append_event(
            "info",
            "JORE TUI ready · /help for commands",
        )

    # ---------- styling / text ----------

    def _current_theme_name(self) -> str:
        value = self.storage.get_setting("theme", "jore") or "jore"
        return value if value in THEMES else "jore"

    def _current_style(self) -> Style:
        return Style.from_dict(THEMES[self._current_theme_name()])

    def _viewport_size(self) -> tuple[int, int]:
        app = getattr(self, "app", None)
        try:
            if app is not None:
                size = app.output.get_size()
                return max(40, int(size.columns)), max(12, int(size.rows))
        except Exception:
            pass
        try:
            size = os.get_terminal_size()
            return max(40, size.columns), max(12, size.lines)
        except OSError:
            return 100, 32

    def _home_brand_block(self) -> str:
        cols, _rows = self._viewport_size()
        return jore_logo(cols) or f"J O R E\n{APP_PRONUNCIATION} // AI TERMINAL COMPANION"

    def _brand_logo_fragments(self) -> list[tuple[str, str]]:
        lines = self._home_brand_block().splitlines()
        gradient = [
            "class:brand-deep", "class:brand-mid", "class:brand-hot",
            "class:brand-hot", "class:brand-soft", "class:brand-white",
            "class:brand-soft", "class:soft",
        ]
        return [(gradient[min(i, len(gradient) - 1)], line + "\n") for i, line in enumerate(lines)]

    def _provider_home_lines(self) -> list[tuple[str, str]]:
        codex = "ready" if self.provider_ready.get("codex") else "missing"
        opencode = "ready" if self.provider_ready.get("opencode") else "missing"
        return [
            ("class:soft", "  JORE Agent\n"),
            ("class:muted", f"  {APP_PRONUNCIATION} // AI Terminal Companion\n\n"),
            ("class:accent", "  Build. Explore. Create. Together.\n\n"),
            ("class:soft", "  Available agents\n"),
            ("class:success" if codex == "ready" else "class:disabled", f"  ◇ Codex      {codex}\n"),
            ("class:success" if opencode == "ready" else "class:disabled", f"  ◆ OpenCode   {opencode}\n"),
            ("class:success", "  ◈ Auto       ready\n\n"),
            ("class:muted", "  /help  commands\n"),
            ("class:muted", "  /new   new session\n"),
        ]

    @staticmethod
    def _plain_lines(text: str) -> list[str]:
        return text.splitlines() if text else []

    def _is_narrow(self) -> bool:
        cols, _rows = self._viewport_size()
        return cols < 88

    def _is_short(self) -> bool:
        _cols, rows = self._viewport_size()
        return rows < 28

    def _show_expanded_dock(self) -> bool:
        return self.dock_visible and not self.dock_compact and not self._is_short()

    def _show_compact_dock(self) -> bool:
        return self.dock_visible and (self.dock_compact or self._is_short())

    def _show_footer(self) -> bool:
        _cols, rows = self._viewport_size()
        return rows >= 22

    @staticmethod
    def _short(value: str, limit: int = 42) -> str:
        value = str(value or "")
        return value if len(value) <= limit else value[: limit - 1] + "…"

    @staticmethod
    def _duration(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        minutes, seconds_left = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m{seconds_left:02d}s"
        hours, minutes_left = divmod(minutes, 60)
        return f"{hours}h{minutes_left:02d}m"

    def _session(self):
        if not self.session_id:
            return None
        try:
            return self.storage.get_session(self.session_id)
        except KeyError:
            self.session_id = None
            return None

    def _model_label(self) -> str:
        session = self._session()
        if session is None:
            return "no session"
        if session.primary_model == "codex":
            return f"Codex · {session.codex_model or 'default'}"
        if session.primary_model.startswith("opencode:"):
            return "OpenCode · " + session.primary_model.split(":", 1)[1]
        return AUTO_MODELS.get(
            session.primary_model,
            {"label": session.primary_model},
        )["label"]

    def _header_fragments(self):
        session = self._session()
        cols, _rows = self._viewport_size()
        providers = (
            "Codex  •  OpenCode  •  Auto"
            if cols < 96
            else "Codex  •  OpenCode  •  Auto Orchestration"
        )
        cwd_source = Path.cwd()
        if session is not None and getattr(session, "project_id", None):
            try:
                cwd_source = Path(self.storage.get_project(session.project_id).workspace_path)
            except (KeyError, TypeError):
                pass
        cwd_label = self._short(str(cwd_source), 54 if cols < 110 else 78)
        if self.view_mode == "project" and self._active_project() is not None:
            project = self._active_project()
            return FormattedText([
                ("class:header", f" ✦ {APP_NAME} "), ("class:muted", f"v{VERSION}"),
                ("", "   "), ("class:brand-hot", self._short(project.name, 42)),
                ("", "\n "), ("class:muted", "project  "), ("class:accent", "isolated workspace"),
                ("", "\n "), ("class:muted", f"cwd  {self._short(project.workspace_path, 76)}"),
            ])
        if session is None:
            return FormattedText(
                [
                    ("class:header", f" ✦ {APP_NAME} "),
                    ("class:muted", f"v{VERSION}"),
                    ("", "\n "),
                    ("class:accent2", APP_TAGLINE),
                    ("class:muted", f"  ·  {providers}"),
                    ("", "\n "),
                    ("class:muted", f"cwd  {cwd_label}"),
                ]
            )

        return FormattedText(
            [
                ("class:header", f" ✦ {APP_NAME} "),
                ("class:muted", f"v{VERSION}"),
                ("", "   "),
                ("", self._short(session.title, 36 if cols < 110 else 46)),
                ("", "\n "),
                ("class:muted", "mode "),
                ("class:accent", session.mode.title()),
                ("class:muted", "   model "),
                ("class:accent2", self._short(self._model_label(), 36 if cols < 110 else 58)),
                ("", "\n "),
                ("class:muted", f"cwd  {cwd_label}"),
            ]
        )

    def _home_fragments(self):
        recent = self.storage.list_sessions(limit=3)
        cols, rows = self._viewport_size()
        compact = cols < 86 or rows < 26
        wide = cols >= 112 and rows >= 32

        parts: list[tuple[str, str]] = [("", "\n")]
        parts.extend(self._brand_logo_fragments())
        parts.append(("", "\n"))

        if wide:
            mascot_lines = self._plain_lines(jore_mascot(cols))
            info_lines = self._fragments_to_lines(FormattedText(self._provider_home_lines()))
            left_width = max((len(line) for line in mascot_lines), default=0)
            total = max(len(mascot_lines), len(info_lines))
            for index in range(total):
                left = mascot_lines[index] if index < len(mascot_lines) else ""
                parts.append(("class:soft", "  " + left.ljust(left_width) + "    "))
                if index < len(info_lines):
                    parts.extend(info_lines[index])
                else:
                    parts.append(("", "\n"))
            parts.append(("", "\n"))
        else:
            parts.extend([
                ("class:accent", f"  {APP_NAME} · {APP_TAGLINE} · {APP_PRONUNCIATION}\n"),
                ("class:muted", "  Build. Explore. Create. Together.\n\n"),
            ])

        parts.extend([
            ("class:brand-hot", "  ❯  1  New chat\n"),
            ("class:text", "     2  Projects / teams\n"),
            ("class:text", "     3  Sessions / history\n"),
            ("class:text", "     4  Provider models\n"),
            ("class:text", "     5  Settings / theme\n"),
            ("class:text", "     6  Doctor\n"),
            ("class:disabled", "     7  Exit\n"),
        ])

        if not compact:
            parts.append(("", "\n"))
            if recent:
                parts.append(("class:muted", "  recent activity\n"))
                recent_limit = 2 if rows < 38 else 3
                for index, session in enumerate(recent[:recent_limit], start=1):
                    parts.extend([
                        ("class:soft", f"    {index}. "),
                        ("class:accent2", self._short(session.title, 34 if cols < 110 else 48)),
                        ("class:muted", f"  ·  {session.mode}\n"),
                    ])
            parts.extend([
                ("", "\n"),
                ("class:muted", "  Type / for commands · Ctrl+J newline · PgUp/PgDn history · Ctrl+C interrupt\n"),
            ])
        return FormattedText(parts)

    @staticmethod
    def _fragments_to_lines(
        fragments: list[tuple[str, str]] | FormattedText,
    ) -> list[list[tuple[str, str]]]:
        lines: list[list[tuple[str, str]]] = [[]]
        for style, text in fragments:
            remaining = text
            while True:
                head, sep, tail = remaining.partition("\n")
                if head:
                    lines[-1].append((style, head))
                if not sep:
                    break
                lines[-1].append((style, "\n"))
                lines.append([])
                remaining = tail
        if len(lines) > 1 and not lines[-1]:
            lines.pop()
        return lines or [[("", "")]]

    def _active_project(self):
        if not self.active_project_id:
            return None
        try:
            return self.storage.get_project(self.active_project_id)
        except KeyError:
            self.active_project_id = None
            return None

    def _project_fragments(self):
        project = self._active_project()
        if project is None:
            return FormattedText([
                ("class:warning", "\n  No active project. Use /projects or /project new.\n"),
            ])
        agents = self.storage.list_project_agents(project.id)
        docs = self.storage.list_project_context(project.id)
        sessions = self.storage.list_sessions(limit=3, project_id=project.id)
        cols, _rows = self._viewport_size()
        path_limit = 62 if cols < 105 else 92
        parts: list[tuple[str, str]] = [
            ("", "\n"),
            ("class:brand-hot", f"  ♛ JORE // PROJECT  {project.name}\n"),
            ("class:muted", f"  id          {project.id}\n"),
            ("class:muted", "  workspace   "),
            ("class:accent2", self._short(project.workspace_path, path_limit) + "\n"),
            ("class:muted", f"  isolation   {project.isolation_mode}\n"),
            ("class:muted", "  permissions "),
            ("class:accent", f"{project.approval_mode} · {project.sandbox_mode} · {project.approvals_reviewer}\n"),
            ("", "\n"),
            ("class:soft", f"  TEAM  {len(agents)} agent(s)\n"),
        ]
        if agents:
            for item in agents[:8]:
                marker = "◆" if item.provider == "opencode" else "◇"
                parts.extend([
                    ("class:brand-hot", f"    {marker} {item.name:<16}"),
                    ("class:soft", f" {self._short(item.role, 20):<20}"),
                    ("class:muted", f" {item.provider} / {self._short(item.model_id, 34)}\n"),
                ])
        else:
            parts.append(("class:muted", "    no agents yet · /agent add\n"))

        parts.extend([("", "\n"), ("class:soft", f"  CONTEXT  {len(docs)} document(s)\n")])
        if docs:
            for item in docs[:7]:
                scope = "all" if not item.agent_scope else ",".join(item.agent_scope[:3])
                parts.append(("class:muted", f"    • {self._short(item.name, 34):<35} scope:{scope}\n"))
        else:
            parts.append(("class:muted", "    no registered docs · /context add <path>\n"))

        if sessions:
            parts.extend([("", "\n"), ("class:soft", "  RECENT PROJECT RUNS\n")])
            for item in sessions:
                parts.append(("class:muted", f"    • {self._short(item.title, 55)} · {item.last_verdict or item.status}\n"))

        parts.extend([
            ("", "\n"),
            ("class:muted", "  /run <goal>   /agents   /context   /project permissions   /home\n"),
            ("class:muted", "  Every team run pauses for explicit approval before agents start.\n"),
        ])
        return FormattedText(parts)

    def _conversation_page_size(self) -> int:
        _cols, rows = self._viewport_size()
        reserved = 13 if self._show_compact_dock() else 18
        if not self.dock_visible:
            reserved = 10
        return max(5, min(36, rows - reserved))

    def _conversation_raw_fragments(self) -> FormattedText:
        if self.view_mode == "project":
            return self._project_fragments()
        if self.view_mode == "home" or not self.session_id:
            return self._home_fragments()

        session = self._session()
        if session is None:
            return self._home_fragments()

        parts: list[tuple[str, str]] = []
        messages = self.storage.get_messages(session.id)

        if not messages:
            parts.extend(
                [
                    ("class:muted", "\n  New session ready.\n"),
                    (
                        "",
                        "  Write a prompt below. Slash commands stay local to JORE.\n\n",
                    ),
                ]
            )

        role_style = {
            "user": "class:accent",
            "assistant": "",
            "reviewer": "class:warning",
            "system": "class:muted",
        }
        role_icon = {
            "user": "❯",
            "assistant": "◆",
            "reviewer": "!",
            "system": "i",
        }

        for message in messages:
            style = role_style.get(message.role, "")
            icon = role_icon.get(message.role, "•")
            label = (
                "you"
                if message.role == "user"
                else "review"
                if message.role == "reviewer"
                else self._model_label()
                if message.role == "assistant"
                else message.role
            )
            parts.append((style, f"\n  {icon} {label}\n"))
            content = message.content.rstrip()
            for line in content.splitlines() or [""]:
                parts.append(("", f"    {line}\n"))

        if self.pending_prompts:
            parts.append(
                (
                    "class:muted",
                    f"\n  queue  {len(self.pending_prompts)} follow-up prompt(s) waiting\n",
                )
            )

        return FormattedText(parts)

    def _conversation_bounds(self) -> tuple[int, int, int]:
        lines = self._fragments_to_lines(self._conversation_raw_fragments())
        page = self._conversation_page_size()
        max_start = max(0, len(lines) - page)
        current = (
            max_start
            if self.conversation_scroll_start is None
            else max(0, min(self.conversation_scroll_start, max_start))
        )
        return len(lines), page, current

    def _conversation_scroll(self, delta: int) -> None:
        if self.view_mode == "home" or (self.view_mode != "project" and not self.session_id):
            return
        total, page, current = self._conversation_bounds()
        max_start = max(0, total - page)
        target = max(0, min(max_start, current + delta))
        self.conversation_scroll_start = None if target >= max_start else target

    def _conversation_to_latest(self) -> None:
        self.conversation_scroll_start = None

    def _conversation_to_oldest(self) -> None:
        if self.view_mode == "home" or (self.view_mode != "project" and not self.session_id):
            return
        self.conversation_scroll_start = 0

    def _conversation_fragments(self):
        if self.view_mode == "project":
            raw = self._project_fragments()
        elif self.view_mode == "home" or not self.session_id:
            return self._home_fragments()
        else:
            raw = self._conversation_raw_fragments()

        lines = self._fragments_to_lines(raw)
        page = self._conversation_page_size()
        max_start = max(0, len(lines) - page)
        start = (
            max_start
            if self.conversation_scroll_start is None
            else max(0, min(self.conversation_scroll_start, max_start))
        )
        if self.conversation_scroll_start is not None:
            self.conversation_scroll_start = start

        selected = lines[start : start + page]
        parts: list[tuple[str, str]] = []
        if start > 0:
            parts.append(("class:muted", f"  ↑ older conversation · {start} line(s) above · PgUp\n"))
        for line in selected:
            parts.extend(line)
        if start + page < len(lines):
            parts.append(("class:muted", "  ↓ newer conversation · PgDn / End for latest\n"))
        return FormattedText(parts)

    def _event_fragments(self):
        parts: list[tuple[str, str]] = []
        icons = {
            "tool": "⌘",
            "provider": "◇",
            "provider_output": "┊",
            "orchestrator": "♛",
            "agent": "◇",
            "review": "!",
            "success": "✓",
            "warning": "!",
            "error": "✕",
            "queued": "↻",
            "context": "⋯",
            "info": "i",
        }
        styles = {
            "success": "class:success",
            "warning": "class:warning",
            "error": "class:error",
            "review": "class:warning",
            "tool": "class:accent2",
            "provider": "class:accent2",
            "info": "class:info",
        }

        rows = list(self.events)[-3 if self.dock_compact else -7 :]
        for item in rows:
            elapsed = max(0, int(time.monotonic() - item.timestamp))
            task = f"#{item.task_id} " if item.task_id else ""
            parts.extend(
                [
                    (
                        styles.get(item.kind, "class:event"),
                        f" {icons.get(item.kind, '•')} {task}{self._short(item.text, 96)}",
                    ),
                    ("class:muted", f"  {elapsed}s\n"),
                ]
            )

        if not parts:
            parts.append(("class:muted", " i no live events yet\n"))
        return FormattedText(parts)

    def _loading_label(self, elapsed: int) -> str:
        frames = ["◐", "◓", "◑", "◒"]
        return f"{frames[elapsed % len(frames)]} JORE is thinking"

    def _task_fragments(self):
        parts: list[tuple[str, str]] = []
        active = [t for t in self.tasks.values() if t.status in {"running", "cancel-requested"}]
        done = [t for t in self.tasks.values() if t.status not in {"running", "cancel-requested"}]

        if self.dock_compact or self._is_short():
            if active:
                task = active[-1]
                parts.extend([
                    ("class:brand-hot", f" {self._loading_label(task.elapsed)}  "),
                    ("class:soft", f"#{task.task_id} {self._short(task.label, 28)}  "),
                    ("class:muted", self._duration(task.elapsed)),
                ])
            elif done:
                task = done[-1]
                if task.status == "done":
                    parts.extend([("class:success", " ✓ JORE COMPLETE  "), ("class:soft", self._short(task.label, 34))])
                elif task.status in {"failed", "error"}:
                    parts.extend([("class:error", " ✕ JORE ERROR  "), ("class:soft", self._short(task.error or task.label, 42))])
                else:
                    parts.append(("class:muted", " • no active background work"))
            else:
                parts.append(("class:muted", " • no active background work"))
            return FormattedText(parts)

        if active:
            task = active[-1]
            session = self._session()
            model = self._model_label() if session else "provider"
            detail = task.detail or "working"
            spin = ["◐", "◓", "◑", "◒"][task.elapsed % 4]
            parts.extend([
                ("class:brand-hot", "  ╭──────╮   "), ("class:brand-hot", f"{spin} JORE is thinking...\n"),
                ("class:soft",      "  │ ●  ● │   "), ("class:muted", "model   "), ("class:text", f"{self._short(model, 46)}\n"),
                ("class:soft",      "  │  ▾   │   "), ("class:muted", "elapsed "), ("class:text", f"{self._duration(task.elapsed)}\n"),
                ("class:soft",      "  ╰──┬───╯   "), ("class:muted", "stage   "), ("class:text", f"{self._short(detail, 60)}\n"),
                ("class:brand-hot", "    [>_]\n"),
            ])
            return FormattedText(parts)

        if done:
            task = done[-1]
            if task.status == "done":
                parts.extend([
                    ("class:success", "  ╭──────╮   ✓ JORE COMPLETE\n"),
                    ("class:success", "  │  ✓   │   "), ("class:soft", f"{self._short(task.label, 62)}\n"),
                    ("class:success", "  ╰──┬───╯   "), ("class:muted", f"{self._duration(task.elapsed)} · Nailed it.\n"),
                    ("class:brand-hot", "    [>_]\n"),
                ])
            elif task.status == "cancelled":
                parts.extend([
                    ("class:warning", "  ╭──────╮   ■ JORE STOPPED\n"),
                    ("class:warning", "  │  ■   │   "), ("class:soft", f"{self._short(task.label, 62)}\n"),
                    ("class:warning", "  ╰──┬───╯\n"),
                ])
            else:
                parts.extend([
                    ("class:error", "  ╭──────╮   ✕ JORE ERROR\n"),
                    ("class:error", "  │  ×   │   "), ("class:soft", f"{self._short(task.error or task.label, 62)}\n"),
                    ("class:error", "  ╰──┬───╯   "), ("class:muted", "/tasks details · retry/change model\n"),
                    ("class:brand-hot", "    /!\\\n"),
                ])
            return FormattedText(parts)

        return FormattedText([("class:muted", " • no background tasks\n")])

    def _estimate_context_tokens(self) -> int:
        session = self._session()
        if session is None:
            return 0
        return sum(
            len(item.content)
            for item in self.storage.get_messages(session.id)
        ) // 4

    def _status_fragments(self):
        session = self._session()
        active_tasks = sum(
            1
            for task in self.tasks.values()
            if task.status in {"running", "cancel-requested"}
        )
        theme = self._current_theme_name()

        if session is None:
            project = self._active_project() if self.view_mode == "project" else None
            if project is not None:
                agents = len(self.storage.list_project_agents(project.id))
                docs = len(self.storage.list_project_context(project.id))
                return FormattedText(
                    [
                        ("class:status", " ◆ JORE "),
                        ("class:status", f"│ project {self._short(project.name, 24)} "),
                        ("class:status", f"│ {agents} agent "),
                        ("class:status", f"│ {docs} ctx "),
                        ("class:status", f"│ ▶ {active_tasks} "),
                        ("class:status", "│ project "),
                    ]
                )
            return FormattedText(
                [
                    ("class:status", " ◆ JORE "),
                    ("class:status", f"│ theme {theme} "),
                    ("class:status", f"│ ▶ {active_tasks} "),
                    ("class:status", "│ home "),
                ]
            )

        messages = len(self.storage.get_messages(session.id))
        attempts = len(self.storage.get_attempts(session.id))
        created = session.created_at
        try:
            from datetime import datetime, timezone

            start = datetime.fromisoformat(created.replace("Z", "+00:00"))
            elapsed = int(
                (
                    datetime.now(timezone.utc)
                    - start.astimezone(timezone.utc)
                ).total_seconds()
            )
        except Exception:
            elapsed = 0

        verdict = f" │ {session.last_verdict}" if session.last_verdict else ""
        return FormattedText(
            [
                ("class:status", f" ◆ {self._short(self._model_label(), 32)} "),
                ("class:status", f"│ {session.mode.title()} "),
                ("class:status", f"│ ~{self._estimate_context_tokens()} ctx "),
                ("class:status", f"│ {messages} msg "),
                ("class:status", f"│ {attempts} run "),
                ("class:status", f"│ ▶ {active_tasks} "),
                ("class:status", f"│ $ n/a "),
                ("class:status", f"│ {self._duration(max(0, elapsed))}{verdict} "),
            ]
        )

    def _footer_fragments(self):
        busy_mode = self.storage.get_setting(
            "busy_input_mode",
            "queue",
        ) or "queue"
        cols, _rows = self._viewport_size()
        if cols < 88:
            return FormattedText(
                [
                    ("class:muted", " Enter send"),
                    ("class:muted", " · Ctrl+J newline"),
                    ("class:muted", " · Ctrl+C stop"),
                ]
            )
        cols, _rows = self._viewport_size()
        parts = [
            ("class:muted", " Enter send"),
            ("class:muted", "  ·  Ctrl+J newline"),
            ("class:muted", "  ·  PgUp/PgDn scroll"),
        ]
        if cols >= 92:
            parts.extend(
                [
                    ("class:muted", "  ·  End latest"),
                    ("class:muted", "  ·  Ctrl+Shift+C/V copy/paste"),
                    ("class:muted", "  ·  Ctrl+C interrupt"),
                    ("class:muted", f"  ·  busy:{busy_mode}"),
                ]
            )
        else:
            parts.extend(
                [
                    ("class:muted", "  ·  End latest"),
                    ("class:muted", "  ·  Ctrl+C interrupt"),
                ]
            )
        return FormattedText(parts)

    def _picker_fragments(self):
        cols, _rows = self._viewport_size()
        parts: list[tuple[str, str]] = []
        is_sessions = "SESSIONS" in self.picker_title.upper()
        if is_sessions:
            parts.extend([("class:brand-hot", " ♛ JORE // SESSIONS\n"), ("class:muted", " Continue where we left off.\n\n")])
        else:
            parts.extend([("class:brand-hot", f" ♛ {self.picker_title}\n"), ("class:muted", " ↑/↓ navigate · Enter select · Esc back\n\n")])

        if not self.picker_options:
            parts.append(("class:muted", "  No options available.\n"))
            return FormattedText(parts)

        visible = 11 if self._is_short() else 17
        half = max(1, visible // 2)
        start = max(0, self.picker_index - half)
        start = min(start, max(0, len(self.picker_options) - visible))
        end = min(len(self.picker_options), start + visible)

        for index in range(start, end):
            _, label, description = self.picker_options[index]
            selected = index == self.picker_index
            prefix = " ❯ " if selected else "   "
            style = "class:picker-selected" if selected else "class:picker"
            parts.append((style, f"{prefix}{self._short(label, 58 if cols < 100 else 78)}\n"))
            if selected and description:
                parts.append(("class:muted", f"     {self._short(description, 76 if cols < 100 else 100)}\n"))

        if is_sessions:
            parts.extend([("", "\n"), ("class:muted", f" {len(self.picker_options)} saved session(s) · Enter resume · Esc back")])
        return FormattedText(parts)

    # ---------- layout ----------

    def _build_layout(self) -> Layout:
        self.header_window = Window(
            FormattedTextControl(self._header_fragments),
            height=3,
            style="class:header-area",
        )

        self.conversation_window = Window(
            FormattedTextControl(
                self._conversation_fragments,
                show_cursor=False,
            ),
            wrap_lines=True,
            always_hide_cursor=True,
            right_margins=[],
        )

        self.event_window = Window(
            FormattedTextControl(self._event_fragments),
            height=Dimension(min=1, preferred=4, max=7),
            wrap_lines=True,
        )
        self.task_window = Window(
            FormattedTextControl(self._task_fragments),
            height=Dimension(min=1, preferred=2, max=5),
            wrap_lines=True,
        )

        expanded_dock = HSplit(
            [
                Frame(self.event_window, title="live events", style="class:frame"),
                Frame(self.task_window, title="work dock", style="class:frame"),
            ]
        )
        compact_dock = Frame(
            Window(
                FormattedTextControl(self._task_fragments),
                height=1,
                wrap_lines=False,
            ),
            title="work",
            style="class:frame",
        )

        self.dock_container = ConditionalContainer(
            HSplit(
                [
                    ConditionalContainer(
                        expanded_dock,
                        filter=Condition(
                            self._show_expanded_dock
                        ),
                    ),
                    ConditionalContainer(
                        compact_dock,
                        filter=Condition(
                            self._show_compact_dock
                        ),
                    ),
                ]
            ),
            filter=Condition(lambda: self.dock_visible),
        )

        self.status_window = Window(
            FormattedTextControl(self._status_fragments),
            height=1,
            style="class:status",
        )

        self.composer_control = BufferControl(
            buffer=self.composer,
            focusable=True,
        )
        self.composer_window = Window(
            self.composer_control,
            height=Dimension(min=1, preferred=3, max=6),
            wrap_lines=True,
            style="class:composer",
            get_line_prefix=lambda lineno, wrap_count: FormattedText(
                [
                    (
                        "class:composer-prefix",
                        " ❯ " if lineno == 0 and wrap_count == 0 else "   ",
                    )
                ]
            ),
        )

        self.footer_window = Window(
            FormattedTextControl(self._footer_fragments),
            height=1,
        )
        self.footer_container = ConditionalContainer(
            self.footer_window,
            filter=Condition(self._show_footer),
        )

        body = HSplit(
            [
                self.header_window,
                Frame(
                    self.conversation_window,
                    title="conversation",
                    style="class:frame",
                ),
                self.dock_container,
                self.status_window,
                self.composer_window,
                self.footer_container,
            ]
        )

        self.picker_container = ConditionalContainer(
            Frame(
                Window(
                    FormattedTextControl(self._picker_fragments),
                    wrap_lines=False,
                ),
                title="select",
                style="class:picker",
            ),
            filter=Condition(lambda: self.picker_visible),
        )

        root = FloatContainer(
            content=body,
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(
                        max_height=10,
                        scroll_offset=1,
                    ),
                ),
                Float(
                    top=1,
                    left=1,
                    right=1,
                    bottom=3,
                    content=self.picker_container,
                ),
            ],
        )
        return Layout(root, focused_element=self.composer_window)

    # ---------- keybindings ----------

    def _build_keybindings(self) -> KeyBindings:
        kb = KeyBindings()
        picker = Condition(lambda: self.picker_visible)
        normal = ~picker

        @kb.add("up", filter=picker, eager=True)
        def _picker_up(event):
            if self.picker_options:
                self.picker_index = (
                    self.picker_index - 1
                ) % len(self.picker_options)
                event.app.invalidate()

        @kb.add("down", filter=picker, eager=True)
        def _picker_down(event):
            if self.picker_options:
                self.picker_index = (
                    self.picker_index + 1
                ) % len(self.picker_options)
                event.app.invalidate()

        @kb.add("enter", filter=picker, eager=True)
        def _picker_enter(event):
            self._finish_picker(
                self.picker_options[self.picker_index][0]
                if self.picker_options
                else None
            )

        @kb.add("escape", filter=picker, eager=True)
        def _picker_escape(event):
            self._finish_picker(None)

        @kb.add("enter", filter=normal)
        def _submit(event):
            buffer = self.composer
            if buffer.complete_state:
                completion = buffer.complete_state.current_completion
                if completion is not None:
                    buffer.apply_completion(completion)
                    return

            text = buffer.text
            if not text.strip():
                return

            buffer.reset()
            event.app.create_background_task(
                self._handle_submit(text)
            )

        @kb.add("c-j", filter=normal)
        def _newline(event):
            self.composer.insert_text("\n")

        @kb.add("tab", filter=normal)
        def _tab(event):
            buffer = self.composer
            if buffer.complete_state:
                completion = buffer.complete_state.current_completion
                if completion is not None:
                    buffer.apply_completion(completion)
                    return
            buffer.start_completion(select_first=False)

        @kb.add("c-c", eager=True)
        def _ctrl_c(event):
            now = time.monotonic()
            double = now - self.last_ctrl_c <= 2.0
            self.last_ctrl_c = now

            if self.picker_visible:
                self._finish_picker(None)
                return

            foreground = self._foreground_task()
            if foreground and foreground.status == "running":
                foreground.status = "cancel-requested"
                foreground.cancel_event.set()
                self._append_event(
                    "warning",
                    "interrupt requested · Ctrl+C again within 2s to force exit",
                    foreground.task_id,
                )
                event.app.invalidate()
                return

            if self.composer.text:
                self.composer.reset()
                self._append_event(
                    "info",
                    "composer cleared · Ctrl+C again within 2s to exit",
                )
                return

            if double:
                self._cancel_all()
                event.app.exit(result=0)
            else:
                self._append_event(
                    "warning",
                    "press Ctrl+C again within 2s to exit JORE",
                )

        @kb.add("c-d", filter=normal)
        def _ctrl_d(event):
            if self.composer.text:
                return
            if self._active_task_count():
                self._append_event(
                    "warning",
                    "active tasks remain · use /stop or Ctrl+C first",
                )
                return
            event.app.exit(result=0)

        @kb.add("pageup", filter=normal, eager=True)
        def _page_up(event):
            self._conversation_scroll(-self._conversation_page_size())
            event.app.invalidate()

        @kb.add("pagedown", filter=normal, eager=True)
        def _page_down(event):
            self._conversation_scroll(self._conversation_page_size())
            event.app.invalidate()

        @kb.add("c-up", filter=normal, eager=True)
        def _line_up(event):
            self._conversation_scroll(-3)
            event.app.invalidate()

        @kb.add("c-down", filter=normal, eager=True)
        def _line_down(event):
            self._conversation_scroll(3)
            event.app.invalidate()

        @kb.add("home", filter=normal, eager=True)
        def _oldest(event):
            if self.composer.text:
                self.composer.cursor_position = 0
                return
            self._conversation_to_oldest()
            event.app.invalidate()

        @kb.add("end", filter=normal, eager=True)
        def _latest(event):
            if self.composer.text:
                self.composer.cursor_position = len(self.composer.text)
                return
            self._conversation_to_latest()
            event.app.invalidate()

        @kb.add("c-t", filter=normal)
        @kb.add("f6", filter=normal)
        def _toggle_dock(event):
            self.dock_visible = not self.dock_visible
            event.app.invalidate()

        @kb.add("c-r", filter=normal)
        @kb.add("f7", filter=normal)
        def _compact_dock(event):
            self.dock_visible = True
            self.dock_compact = not self.dock_compact
            event.app.invalidate()

        return kb

    # ---------- events / tasks ----------

    def _append_event(
        self,
        kind: str,
        text: str,
        task_id: int | None = None,
    ) -> None:
        self.events.append(
            EventLine(
                timestamp=time.monotonic(),
                kind=kind,
                text=str(text),
                task_id=task_id,
            )
        )
        try:
            self.app.invalidate()
        except Exception:
            pass

    @staticmethod
    def _public_event_text(text: str) -> str:
        value = str(text)
        value = re.sub(
            r"(?i)\\bCAO(?:-server)?\\b",
            "JORE Runtime",
            value,
        )
        value = re.sub(
            r"(?i)cli-agent-orchestrator",
            "JORE Runtime",
            value,
        )
        value = value.replace(
            "nemotron-developer",
            "primary agent",
        )
        value = value.replace(
            "mimo-reviewer",
            "reviewer agent",
        )
        return value

    def _thread_event_callback(self, task_id: int):
        def callback(kind: str, text: str) -> None:
            if self.loop is None:
                return
            self.loop.call_soon_threadsafe(
                self._append_event,
                kind,
                self._public_event_text(text),
                task_id,
            )

        return callback

    def _new_task(
        self,
        label: str,
        prompt: str,
        *,
        background: bool,
    ) -> TaskState:
        task = TaskState(
            task_id=self._next_task_id,
            label=label,
            prompt=prompt,
            background=background,
        )
        self._next_task_id += 1
        self.tasks[task.task_id] = task
        return task

    def _foreground_task(self) -> TaskState | None:
        if self.foreground_task_id is None:
            return None
        return self.tasks.get(self.foreground_task_id)

    def _active_task_count(self) -> int:
        return sum(
            1
            for task in self.tasks.values()
            if task.status in {"running", "cancel-requested"}
        )

    def _cancel_all(self) -> None:
        for task in self.tasks.values():
            if task.status in {"running", "cancel-requested"}:
                task.status = "cancel-requested"
                task.cancel_event.set()

    async def _execute_task(
        self,
        task: TaskState,
    ) -> None:
        if self.session_id is None:
            task.status = "failed"
            task.error = "No active session"
            return

        session_id = self.session_id
        callback = self._thread_event_callback(task.task_id)
        try:
            result: TurnResult = await asyncio.to_thread(
                execute_turn,
                storage=self.storage,
                registry=self.registry,
                session_id=session_id,
                instruction=task.prompt,
                event_callback=callback,
                cancel_event=task.cancel_event,
                background=task.background,
                working_directory=Path.cwd(),
            )
            task.status = "done"
            task.output = result.primary_output
            task.detail = (
                f"{result.primary_label}"
                + (
                    f" · {result.verdict}"
                    if result.verdict
                    else ""
                )
            )
            self._append_event(
                "success",
                f"JORE complete · {task.label}",
                task.task_id,
            )
            if not task.background and result.verdict == "NEEDS_FIX":
                self.last_needs_fix_task = task.prompt
                self.last_needs_fix_result = result
            elif not task.background and result.verdict == "PASS":
                self.last_needs_fix_task = None
                self.last_needs_fix_result = None
        except Exception as exc:
            task.error = str(exc)
            if task.cancel_event.is_set():
                task.status = "cancelled"
                self._append_event(
                    "warning",
                    f"{task.label} cancelled",
                    task.task_id,
                )
            else:
                task.status = "failed"
                self._append_event(
                    "error",
                    f"JORE error · {exc}",
                    task.task_id,
                )
        finally:
            task.finished_at = time.monotonic()
            if not task.background:
                if self.conversation_scroll_start is None:
                    self._conversation_to_latest()
                self.foreground_task_id = None
                if (
                    self.last_needs_fix_task == task.prompt
                    and self.last_needs_fix_result is not None
                    and self.last_needs_fix_result.verdict == "NEEDS_FIX"
                ):
                    await self._needs_fix_flow(
                        task.prompt,
                        self.last_needs_fix_result,
                    )
                if self.pending_prompts and self.foreground_task_id is None:
                    next_prompt = self.pending_prompts.popleft()
                    await self._start_foreground(next_prompt)
            self.app.invalidate()

    async def _start_foreground(self, prompt: str) -> None:
        if self.session_id is None:
            self._append_event("warning", "create or resume a session first")
            return

        if self.foreground_task_id is not None:
            busy_mode = self.storage.get_setting(
                "busy_input_mode",
                "queue",
            ) or "queue"

            if busy_mode == "interrupt":
                current = self._foreground_task()
                if current:
                    current.status = "cancel-requested"
                    current.cancel_event.set()
                self.pending_prompts.appendleft(prompt)
                self._append_event(
                    "warning",
                    "current run interrupted; new prompt will start next",
                )
            else:
                self.pending_prompts.append(prompt)
                self._append_event(
                    "queued",
                    f"follow-up queued · {len(self.pending_prompts)} waiting",
                )
            return

        task = self._new_task(
            self._short(prompt, 36),
            prompt,
            background=False,
        )
        self.foreground_task_id = task.task_id
        self._append_event(
            "queued",
            "foreground prompt queued",
            task.task_id,
        )
        self.app.create_background_task(
            self._execute_task(task)
        )

    async def _start_background(self, prompt: str) -> None:
        session = self._session()
        if session is None:
            self._append_event("warning", "create or resume a session first")
            return

        # The internal Auto runtime stays single-lane because service ownership
        # is not yet shared safely between concurrent AgentHub jobs.
        if session.mode == "auto":
            self._append_event(
                "warning",
                "/bg is currently enabled for Single Agent sessions only",
            )
            return

        task = self._new_task(
            "bg · " + self._short(prompt, 30),
            prompt,
            background=True,
        )
        self._append_event(
            "queued",
            "background task queued",
            task.task_id,
        )
        self.app.create_background_task(
            self._execute_task(task)
        )

    # ---------- picker ----------

    async def _pick(
        self,
        title: str,
        options: list[tuple[str, str, str]],
        *,
        default_key: str | None = None,
    ) -> str | None:
        if not options:
            self._append_event("warning", f"{title}: no options available")
            return None

        if self.picker_future is not None and not self.picker_future.done():
            return None

        self.picker_title = title
        self.picker_options = options
        self.picker_index = 0
        if default_key is not None:
            for index, item in enumerate(options):
                if item[0] == default_key:
                    self.picker_index = index
                    break

        self.picker_visible = True
        self.picker_future = asyncio.get_running_loop().create_future()
        self.app.invalidate()
        result = await self.picker_future
        return result

    def _finish_picker(self, value: str | None) -> None:
        future = self.picker_future
        self.picker_visible = False
        self.picker_options = []
        self.picker_index = 0
        self.picker_future = None
        if future is not None and not future.done():
            future.set_result(value)
        self.app.invalidate()

    async def _pick_codex_escalation_config(self) -> tuple[str, str] | None:
        session = self._session()
        current_model = (
            session.codex_model if session else None
        ) or self.storage.get_setting("codex_default_model")
        model = await self._pick_codex_model(current_model)
        if model is None:
            return None
        info = self._codex_info(model)
        levels = (
            list(info.reasoning_levels)
            if info and info.reasoning_levels
            else ["low", "medium", "high", "xhigh"]
        )
        current_effort = (
            session.codex_reasoning if session else None
        ) or self.storage.get_setting("codex_default_reasoning", "medium")
        effort = await self._pick(
            "Codex reasoning",
            [
                (
                    value,
                    value.replace("xhigh", "extra high").title(),
                    "supervisor effort",
                )
                for value in levels
            ],
            default_key=current_effort if current_effort in levels else levels[0],
        )
        if effort is None:
            return None
        if session is not None:
            self.storage.update_session(
                session.id,
                codex_model=model,
                codex_reasoning=effort,
            )
        return model, effort

    async def _run_codex_escalation_job(
        self,
        *,
        mode: str,
        original_task: str,
        result: TurnResult,
    ) -> CodexEscalationResult | None:
        config = await self._pick_codex_escalation_config()
        if config is None or self.session_id is None:
            return None
        model, effort = config
        task = self._new_task(
            f"Codex · {mode}",
            original_task,
            background=False,
        )
        self.foreground_task_id = task.task_id
        callback = self._thread_event_callback(task.task_id)
        self._append_event("queued", f"Codex {mode} queued", task.task_id)
        try:
            escalation = await asyncio.to_thread(
                execute_codex_escalation,
                storage=self.storage,
                registry=self.registry,
                session_id=self.session_id,
                original_instruction=original_task,
                primary_output=result.primary_output,
                reviewer_output=result.review or "",
                mode=mode,
                codex_model=model,
                reasoning=effort,
                run_state_id=result.run_state_id,
                event_callback=callback,
                cancel_event=task.cancel_event,
                working_directory=Path.cwd(),
            )
            task.status = "done"
            task.output = escalation.output
            task.detail = f"{escalation.codex_label} · {mode}"
            self._append_event(
                "success",
                f"Codex {mode} complete",
                task.task_id,
            )
            self._conversation_to_latest()
            return escalation
        except Exception as exc:
            task.error = str(exc)
            task.status = "cancelled" if task.cancel_event.is_set() else "failed"
            self._append_event(
                "warning" if task.cancel_event.is_set() else "error",
                f"Codex {mode} failed · {exc}",
                task.task_id,
            )
            return None
        finally:
            task.finished_at = time.monotonic()
            self.foreground_task_id = None
            self.app.invalidate()

    async def _run_repair_job(
        self,
        *,
        original_task: str,
        repair_prompt: str,
        run_state_id: str | None,
        label: str = "repair retry",
    ) -> TurnResult | None:
        if self.session_id is None:
            return None
        task = self._new_task(label, original_task, background=False)
        self.foreground_task_id = task.task_id
        callback = self._thread_event_callback(task.task_id)
        self._append_event("queued", f"{label} queued", task.task_id)
        try:
            result = await asyncio.to_thread(
                execute_repair_turn,
                storage=self.storage,
                registry=self.registry,
                session_id=self.session_id,
                original_instruction=original_task,
                repair_prompt=repair_prompt,
                run_state_id=run_state_id,
                event_callback=callback,
                cancel_event=task.cancel_event,
                working_directory=Path.cwd(),
            )
            task.status = "done"
            task.output = result.primary_output
            task.detail = (
                f"{result.primary_label}"
                + (f" · {result.verdict}" if result.verdict else "")
            )
            self._append_event("success", f"{label} complete", task.task_id)
            self._conversation_to_latest()
            return result
        except Exception as exc:
            task.error = str(exc)
            task.status = "cancelled" if task.cancel_event.is_set() else "failed"
            self._append_event(
                "warning" if task.cancel_event.is_set() else "error",
                f"{label} failed · {exc}",
                task.task_id,
            )
            return None
        finally:
            task.finished_at = time.monotonic()
            self.foreground_task_id = None
            self.app.invalidate()

    async def _needs_fix_flow(
        self,
        original_task: str,
        initial_result: TurnResult,
    ) -> None:
        current = initial_result
        self.last_needs_fix_task = original_task
        self.last_needs_fix_result = initial_result

        while current.verdict == "NEEDS_FIX":
            if current.run_state_id:
                try:
                    persisted = self.storage.get_run_state(current.run_state_id)
                    current.loop_detected = (
                        persisted.status == "loop_detected"
                        or persisted.escalation_state == "loop_detected"
                    )
                    current.failure_fingerprint = persisted.failure_fingerprint
                    current.retries_remaining = persisted.retries_remaining
                except KeyError:
                    pass

            free_retry_allowed = (
                not current.loop_detected
                and (current.retries_remaining is None or current.retries_remaining > 0)
            )
            if current.loop_detected:
                self._append_event(
                    "warning",
                    f"loop guard active · {current.failure_fingerprint or 'repeated failure'} · free retry disabled",
                )
            elif current.retries_remaining == 0:
                self._append_event(
                    "warning",
                    "retry budget exhausted · use Codex escalation or stop",
                )

            options = []
            if free_retry_allowed:
                options.extend(
                    [
                        (
                            "retry",
                            "Retry with reviewer feedback",
                            f"same free worker · {current.retries_remaining if current.retries_remaining is not None else '?'} retry left",
                        ),
                        (
                            "switch",
                            "Switch free worker + retry",
                            "change Auto primary; cooldown models are skipped automatically",
                        ),
                    ]
                )
            options.extend(
                [
                    (
                        "codex_review",
                        "Codex · supervisor review only",
                        "diagnose the failure; do not fix or edit",
                    ),
                    (
                        "codex_prompt",
                        "Codex · create repair prompt",
                        "show a standalone prompt, then auto-send or edit manually",
                    ),
                    (
                        "codex_fix",
                        "Codex · take over and fix",
                        "Codex may inspect/edit/test and produce the corrected result",
                    ),
                    (
                        "stop",
                        "Keep current result / stop",
                        "leave the reviewed result in history",
                    ),
                ]
            )
            choice = await self._pick(
                "Review · NEEDS_FIX · what next?",
                options,
            )
            if choice in {None, "stop"}:
                return

            if choice == "retry":
                current = await self._run_repair_job(
                    original_task=original_task,
                    repair_prompt=current.review or "Address every reviewer finding.",
                    run_state_id=current.run_state_id,
                    label="reviewer-feedback retry",
                ) or current
                if current.verdict != "NEEDS_FIX":
                    self.last_needs_fix_task = None
                    self.last_needs_fix_result = None
                    return
                self.last_needs_fix_result = current
                continue

            if choice == "switch":
                session = self._session()
                if session is None:
                    return
                selected = await self._pick(
                    "Switch free worker",
                    [
                        ("nemotron", "Nemotron 3 Ultra Free", "free primary"),
                        ("mimo", "MiMo V2.6 Flash Free", "free primary"),
                    ],
                    default_key=session.primary_model,
                )
                if selected is None:
                    continue
                self.storage.update_session(session.id, primary_model=selected)
                if current.run_state_id:
                    self.storage.update_run_state(
                        current.run_state_id,
                        current_worker=selected,
                    )
                current = await self._run_repair_job(
                    original_task=original_task,
                    repair_prompt=current.review or "Address every reviewer finding.",
                    run_state_id=current.run_state_id,
                    label="switched-worker retry",
                ) or current
                if current.verdict != "NEEDS_FIX":
                    self.last_needs_fix_task = None
                    self.last_needs_fix_result = None
                    return
                self.last_needs_fix_result = current
                continue

            if choice == "codex_review":
                await self._run_codex_escalation_job(
                    mode="diagnose",
                    original_task=original_task,
                    result=current,
                )
                # Diagnosis is intentionally advisory. Return to the same fix menu.
                continue

            if choice == "codex_prompt":
                escalation = await self._run_codex_escalation_job(
                    mode="prompt",
                    original_task=original_task,
                    result=current,
                )
                if escalation is None or not escalation.repair_prompt:
                    continue
                action = await self._pick(
                    "Codex repair prompt ready",
                    [
                        (
                            "auto",
                            "Send directly to worker",
                            "JORE runs another free-worker attempt now",
                        ),
                        (
                            "manual",
                            "Load prompt into composer",
                            "review/edit it yourself, then press Enter",
                        ),
                        ("back", "Back", "return to NEEDS_FIX options"),
                    ],
                )
                if action == "auto":
                    current = await self._run_repair_job(
                        original_task=original_task,
                        repair_prompt=escalation.repair_prompt,
                        run_state_id=current.run_state_id,
                        label="Codex-prompt repair",
                    ) or current
                    if current.verdict != "NEEDS_FIX":
                        self.last_needs_fix_task = None
                        self.last_needs_fix_result = None
                        return
                    self.last_needs_fix_result = current
                    continue
                if action == "manual":
                    self.composer.text = escalation.repair_prompt
                    self.composer.cursor_position = len(self.composer.text)
                    self._append_event(
                        "info",
                        "Codex repair prompt loaded into composer",
                    )
                    return
                continue

            if choice == "codex_fix":
                escalation = await self._run_codex_escalation_job(
                    mode="fix",
                    original_task=original_task,
                    result=current,
                )
                if escalation is None:
                    continue
                if escalation.verdict == "NEEDS_FIX":
                    current = TurnResult(
                        primary_output=escalation.output,
                        primary_label=escalation.codex_label,
                        verdict=escalation.verdict,
                        review=escalation.review,
                        run_state_id=escalation.run_state_id,
                        loop_detected=escalation.loop_detected,
                        retries_remaining=(
                            self.storage.get_run_state(escalation.run_state_id).retries_remaining
                            if escalation.run_state_id else None
                        ),
                    )
                    self.last_needs_fix_result = current
                    continue
                self.last_needs_fix_task = None
                self.last_needs_fix_result = None
                return

    # ---------- sessions / models ----------

    async def _new_session_flow(self) -> None:
        if self.foreground_task_id is not None:
            self._append_event(
                "warning",
                "finish or cancel the foreground run before starting another session",
            )
            return

        mode = await self._pick(
            "New session · mode",
            [
                (
                    "auto",
                    "Auto",
                    "free primary + automatic reviewer",
                ),
                (
                    "single",
                    "Single Agent",
                    "choose OpenCode or Codex + model",
                ),
            ],
            default_key=self.storage.get_setting(
                "default_mode",
                "auto",
            ),
        )
        if mode is None:
            return

        if mode == "auto":
            default = self.storage.get_setting(
                "default_free_model",
                "nemotron",
            )
            primary = await self._pick(
                "Auto primary",
                [
                    (
                        "nemotron",
                        "Nemotron 3 Ultra Free",
                        "proven JORE free primary",
                    ),
                    (
                        "mimo",
                        "MiMo V2.6 Flash Free",
                        "fast free OpenCode model",
                    ),
                ],
                default_key=default,
            )
            if primary is None:
                return

            reviewer = self.storage.get_setting(
                "reviewer_model",
                "mimo",
            ) or "mimo"
            session = self.storage.create_session(
                mode="auto",
                primary_model=primary,
                reviewer_model=reviewer,
            )
            self.session_id = session.id
            self.view_mode = "session"
            self._conversation_to_latest()
            self._append_event("info", "new Auto session created")
            return

        provider = await self._pick(
            "Single Agent · provider",
            [
                (
                    "codex",
                    "◇ Codex",
                    "models visible to your Codex account",
                ),
                (
                    "opencode",
                    "◆ OpenCode",
                    "models visible through configured OpenCode providers",
                ),
            ],
            default_key="codex",
        )
        if provider is None:
            return

        if provider == "codex":
            model = await self._pick_codex_model(
                self.storage.get_setting("codex_default_model")
            )
            if model is None:
                return

            info = self._codex_info(model)
            levels = (
                list(info.reasoning_levels)
                if info and info.reasoning_levels
                else ["low", "medium", "high", "xhigh"]
            )
            default_effort = (
                self.storage.get_setting(
                    "codex_default_reasoning",
                    "medium",
                )
                or "medium"
            )
            effort = await self._pick(
                "Codex reasoning",
                [
                    (
                        value,
                        value.replace("xhigh", "extra high").title(),
                        "model reasoning effort",
                    )
                    for value in levels
                ],
                default_key=(
                    default_effort
                    if default_effort in levels
                    else (
                        info.default_reasoning
                        if info and info.default_reasoning in levels
                        else levels[0]
                    )
                ),
            )
            if effort is None:
                return

            self.storage.set_setting("codex_default_model", model)
            self.storage.set_setting("codex_default_reasoning", effort)
            session = self.storage.create_session(
                mode="single",
                primary_model="codex",
                codex_model=model,
                codex_reasoning=effort,
            )
        else:
            model = await self._pick_opencode_model(
                self.storage.get_setting("opencode_default_model")
            )
            if model is None:
                return
            self.storage.set_setting("opencode_default_model", model)
            session = self.storage.create_session(
                mode="single",
                primary_model=f"opencode:{model}",
            )

        self.session_id = session.id
        self.view_mode = "session"
        self._conversation_to_latest()
        self._append_event("info", "new Single Agent session created")

    def _codex_info(self, model_id: str) -> ModelInfo | None:
        for model in self.registry.codex_models().models:
            if model.model_id == model_id:
                return model
        return None

    async def _pick_codex_model(
        self,
        current: str | None = None,
    ) -> str | None:
        catalog = await asyncio.to_thread(
            self.registry.codex_models
        )
        options = [
            (
                model.model_id,
                f"◇ {model.label}",
                model.description
                or (
                    "effort: " + ", ".join(model.reasoning_levels)
                    if model.reasoning_levels
                    else model.model_id
                ),
            )
            for model in catalog.models
        ]
        return await self._pick(
            f"Codex models · {catalog.source}",
            options,
            default_key=current,
        )

    async def _pick_opencode_model(
        self,
        current: str | None = None,
    ) -> str | None:
        catalog = await asyncio.to_thread(
            self.registry.opencode_models
        )
        options = [
            (
                model.model_id,
                (
                    f"◆ {model.label}"
                    + (" · Free" if model.free else "")
                ),
                model.model_id,
            )
            for model in catalog.models
        ]
        return await self._pick(
            f"OpenCode models · {catalog.source}",
            options,
            default_key=current,
        )

    async def _model_flow(self) -> None:
        if self.foreground_task_id is not None:
            self._append_event(
                "warning",
                "model changes are locked while the foreground run is active",
            )
            return

        session = self._session()
        if session is None:
            self._append_event("warning", "no active session")
            return

        if session.mode == "auto":
            selected = await self._pick(
                "Auto primary",
                [
                    (
                        "nemotron",
                        "Nemotron 3 Ultra Free",
                        "proven JORE free primary",
                    ),
                    (
                        "mimo",
                        "MiMo V2.6 Flash Free",
                        "fast free OpenCode model",
                    ),
                ],
                default_key=session.primary_model,
            )
            if selected:
                self.storage.update_session(
                    session.id,
                    primary_model=selected,
                )
            return

        provider = await self._pick(
            "Single Agent · provider",
            [
                (
                    "codex",
                    "Codex",
                    "use live Codex model catalog",
                ),
                (
                    "opencode",
                    "OpenCode",
                    "use live OpenCode model catalog",
                ),
            ],
            default_key=(
                "codex"
                if session.primary_model == "codex"
                else "opencode"
            ),
        )
        if provider is None:
            return

        if provider == "codex":
            model = await self._pick_codex_model(
                session.codex_model
                or self.storage.get_setting("codex_default_model")
            )
            if model is None:
                return
            info = self._codex_info(model)
            levels = (
                list(info.reasoning_levels)
                if info and info.reasoning_levels
                else ["low", "medium", "high", "xhigh"]
            )
            effort = await self._pick(
                "Codex reasoning",
                [
                    (
                        value,
                        value.replace("xhigh", "extra high").title(),
                        "",
                    )
                    for value in levels
                ],
                default_key=(
                    session.codex_reasoning
                    if session.codex_reasoning in levels
                    else levels[0]
                ),
            )
            if effort is None:
                return
            self.storage.update_session(
                session.id,
                primary_model="codex",
                reviewer_model=None,
                codex_model=model,
                codex_reasoning=effort,
            )
        else:
            current = (
                session.primary_model.split(":", 1)[1]
                if session.primary_model.startswith("opencode:")
                else self.storage.get_setting("opencode_default_model")
            )
            model = await self._pick_opencode_model(current)
            if model is None:
                return
            self.storage.update_session(
                session.id,
                primary_model=f"opencode:{model}",
                reviewer_model=None,
                codex_model=None,
                codex_reasoning=None,
            )

        self._append_event("info", f"model changed · {self._model_label()}")

    async def _sessions_flow(self) -> None:
        if self.foreground_task_id is not None:
            self._append_event(
                "warning",
                "finish or cancel the foreground run before switching sessions",
            )
            return

        project = self._active_project() if self.active_project_id else None
        sessions = self.storage.list_sessions(
            limit=50,
            project_id=project.id if project and self.view_mode == "project" else None,
        )
        options = [
            (
                session.id,
                session.title,
                f"{session.mode} · {session.last_verdict or 'active'} · {session.updated_at}",
            )
            for session in sessions
        ]
        selected = await self._pick(
            "JORE // SESSIONS",
            options,
            default_key=self.session_id,
        )
        if selected:
            self.session_id = selected
            resumed = self.storage.get_session(selected)
            if resumed.project_id:
                self.active_project_id = resumed.project_id
            self.view_mode = "session"
            self._conversation_to_latest()
            self._append_event("info", "session resumed")

    async def _models_flow(self) -> None:
        provider = await self._pick(
            "Provider model catalog",
            [
                ("codex", "◇ Codex", "live selectable Codex models"),
                ("opencode", "◆ OpenCode", "live configured OpenCode models"),
                ("refresh", "Refresh catalogs", "query provider CLIs now"),
            ],
        )
        if provider == "codex":
            value = await self._pick_codex_model(
                self.storage.get_setting("codex_default_model")
            )
            if value:
                self.storage.set_setting("codex_default_model", value)
        elif provider == "opencode":
            value = await self._pick_opencode_model(
                self.storage.get_setting("opencode_default_model")
            )
            if value:
                self.storage.set_setting("opencode_default_model", value)
        elif provider == "refresh":
            self._append_event("info", "refreshing provider catalogs")
            codex, opencode = await asyncio.gather(
                asyncio.to_thread(
                    self.registry.codex_models,
                    refresh=True,
                ),
                asyncio.to_thread(
                    self.registry.opencode_models,
                    refresh=True,
                ),
            )
            self._append_event(
                "success",
                f"catalog refreshed · Codex {len(codex.models)} · OpenCode {len(opencode.models)}",
            )

    async def _theme_flow(self) -> None:
        current = self._current_theme_name()
        selected = await self._pick(
            "JORE theme",
            [
                ("jore", "JORE Pink", "near-black + neon pink + warm white"),
                ("claude-warm", "Warm Research", "warm terminal-inspired skin"),
                ("gemini-night", "Gemini Night", "blue + violet"),
                ("mono", "Mono", "minimal monochrome"),
            ],
            default_key=current,
        )
        if selected:
            self.storage.set_setting("theme", selected)
            self._append_event("success", f"theme changed · {selected}")
            self.app.invalidate()

    async def _settings_flow(self) -> None:
        choice = await self._pick(
            "TUI settings",
            [
                (
                    "theme",
                    f"Theme · {self._current_theme_name()}",
                    "change JORE skin",
                ),
                (
                    "busy",
                    "Busy input mode",
                    "queue or interrupt when a run is active",
                ),
                (
                    "dock",
                    "Toggle work dock",
                    "show/hide live event + task panes",
                ),
                (
                    "back",
                    "Back",
                    "",
                ),
            ],
        )
        if choice == "theme":
            await self._theme_flow()
        elif choice == "busy":
            current = self.storage.get_setting(
                "busy_input_mode",
                "queue",
            )
            value = await self._pick(
                "Busy input mode",
                [
                    (
                        "queue",
                        "Queue",
                        "send as next turn after active run completes",
                    ),
                    (
                        "interrupt",
                        "Interrupt",
                        "request stop then run the new prompt next",
                    ),
                ],
                default_key=current,
            )
            if value:
                self.storage.set_setting("busy_input_mode", value)
                self._append_event(
                    "success",
                    f"busy input mode · {value}",
                )
        elif choice == "dock":
            self.dock_visible = not self.dock_visible

    async def _tasks_flow(self) -> None:
        tasks = list(self.tasks.values())
        options = [
            (
                str(task.task_id),
                f"#{task.task_id} {task.label}",
                f"{task.status} · {self._duration(task.elapsed)}",
            )
            for task in reversed(tasks[-30:])
        ]
        selected = await self._pick("Tasks", options)
        if selected is None:
            return
        task = self.tasks.get(int(selected))
        if task is None:
            return

        action_options = [
            ("view", "View details", task.detail or task.status),
            ("stop", "Stop task", "request cancellation"),
            ("back", "Back", ""),
        ]
        action = await self._pick(
            f"Task #{task.task_id}",
            action_options,
        )
        if action == "stop" and task.status == "running":
            task.status = "cancel-requested"
            task.cancel_event.set()
            self._append_event(
                "warning",
                f"stop requested · task #{task.task_id}",
                task.task_id,
            )
        elif action == "view":
            detail = task.output or task.error or task.detail
            self._append_event(
                "info",
                f"task #{task.task_id}: {self._short(detail, 120)}",
                task.task_id,
            )

    # ---------- projects / teams ----------

    async def _projects_flow(self) -> None:
        projects = self.storage.list_projects()
        options = [(item.id, item.name, self._short(item.workspace_path, 52)) for item in projects]
        options.append(("__new__", "+ New project", "create a named isolated workspace"))
        selected = await self._pick("JORE Projects", options)
        if selected is None:
            return
        if selected == "__new__":
            self.form_state = {"kind": "project_new", "stage": "name"}
            self._append_event("info", "Project name? Type it in the composer and press Enter.")
            return
        self.active_project_id = selected
        self.session_id = None
        self.view_mode = "project"
        project = self.storage.get_project(selected)
        self._append_event("success", f"project opened · {project.name} · {project.workspace_path}")

    async def _permission_picker(self, default: str = "ask") -> str | None:
        return await self._pick(
            "Project permissions",
            [
                ("ask", "Ask for Approval", "workspace-write · on-request · user reviews boundary requests"),
                ("approve_for_me", "Approve for Me", "workspace-write · auto-review eligible boundary requests"),
                ("full_access", "Full Access", "danger-full-access · no provider approval prompts; JORE still asks before each run"),
                ("custom", "Custom", "safe custom base; edit sandbox/policy/reviewer explicitly"),
            ],
            default_key=default,
        )

    async def _finish_project_create(self, path_text: str) -> None:
        assert self.form_state is not None
        name = self.form_state["name"]
        try:
            workspace = ensure_workspace(normalize_workspace_path(path_text or "."), create=True)
            assert_workspace_isolated(self.storage, workspace)
        except Exception as exc:
            self._append_event("error", f"workspace error · {exc}")
            self.form_state["stage"] = "path"
            return
        mode = await self._permission_picker("ask")
        if mode is None:
            self.form_state = None
            self._append_event("warning", "project creation cancelled")
            return
        preset = PERMISSION_PRESETS[mode]
        if mode == "full_access":
            confirmed = await self._pick(
                "Confirm Full Access",
                [
                    ("no", "Cancel", "recommended if broad machine access is unnecessary"),
                    ("yes", "I understand · create with Full Access", "agents may operate beyond workspace/provider network boundaries"),
                ],
                default_key="no",
            )
            if confirmed != "yes":
                self.form_state = None
                self._append_event("warning", "Full Access project creation cancelled")
                return
        base_slug = slugify(name)
        slug = base_slug
        used = {p.slug for p in self.storage.list_projects(include_archived=True)}
        n = 2
        while slug in used:
            slug = f"{base_slug}-{n}"; n += 1
        project = self.storage.create_project(
            name=name,
            slug=slug,
            workspace_path=str(workspace),
            workspace_source="external",
            isolation_mode="strict-context",
            approval_mode=mode,
            sandbox_mode=preset["sandbox_mode"],
            approval_policy=preset["approval_policy"],
            approvals_reviewer=preset["approvals_reviewer"],
        )
        write_workspace_marker(project.id, project.name, workspace)
        imported = auto_import_common_context(self.storage, project.id, workspace)
        self.active_project_id = project.id
        self.session_id = None
        self.view_mode = "project"
        self.form_state = None
        self._append_event("success", f"project created · {project.name}")
        self._append_event("info", f"workspace · {project.workspace_path}")
        if imported:
            self._append_event("info", f"context auto-imported · {len(imported)} common document(s)")

    async def _project_command(self, argument: str) -> None:
        arg = argument.strip()
        if not arg:
            if self.active_project_id:
                self.view_mode = "project"
            else:
                await self._projects_flow()
            return
        head, _, tail = arg.partition(" ")
        head = head.lower()
        if head == "new":
            self.form_state = {"kind": "project_new", "stage": "name"}
            self._append_event("info", "Project name? Type it in the composer and press Enter.")
        elif head in {"open", "switch"}:
            await self._projects_flow()
        elif head == "permissions":
            project = self._active_project()
            if not project:
                self._append_event("warning", "open a project first")
                return
            raw = tail.strip()
            pieces = raw.split()
            mode = pieces[0].lower() if pieces else await self._permission_picker(project.approval_mode)
            if not mode or mode not in PERMISSION_PRESETS:
                return
            if mode == "custom" and len(pieces) >= 4:
                sandbox, policy, reviewer = pieces[1:4]
                if sandbox not in {"read-only", "workspace-write", "danger-full-access"}:
                    self._append_event("warning", "custom sandbox must be read-only, workspace-write, or danger-full-access"); return
                if policy not in {"on-request", "never"}:
                    self._append_event("warning", "custom policy must be on-request or never"); return
                if reviewer not in {"user", "auto_review", "none"}:
                    self._append_event("warning", "custom reviewer must be user, auto_review, or none"); return
                self.storage.update_project(project.id, approval_mode="custom", sandbox_mode=sandbox,
                    approval_policy=policy, approvals_reviewer=reviewer,
                    custom_permissions={"sandbox_mode":sandbox,"approval_policy":policy,"approvals_reviewer":reviewer})
                self._append_event("success", f"project permissions · Custom · {sandbox} · {policy} · {reviewer}")
                return
            preset = PERMISSION_PRESETS[mode]
            self.storage.update_project(project.id, approval_mode=mode,
                sandbox_mode=preset["sandbox_mode"], approval_policy=preset["approval_policy"],
                approvals_reviewer=preset["approvals_reviewer"])
            self._append_event("success", f"project permissions · {preset['label']}")
            if mode == "custom":
                self._append_event("info", "custom syntax · /project permissions custom <read-only|workspace-write|danger-full-access> <on-request|never> <user|auto_review|none>")
        else:
            self._append_event("warning", "usage: /project [new|open|permissions]")

    async def _agents_flow(self) -> None:
        project = self._active_project()
        if not project:
            self._append_event("warning", "open a project first")
            return
        agents = self.storage.list_project_agents(project.id)
        if not agents:
            self._append_event("info", "project has no agents · use /agent add")
            return
        for item in agents:
            self._append_event("info", f"{item.name} · {item.role} · {item.provider} · {item.model_id}")

    async def _agent_add_finish(self, role: str) -> None:
        assert self.form_state is not None
        project = self._active_project()
        if not project:
            self.form_state = None
            return
        name = self.form_state["name"]
        provider = await self._pick(
            f"Agent {name} · provider",
            [("opencode", "OpenCode", "choose from live OpenCode models"),
             ("codex", "Codex", "choose from live Codex models")],
            default_key="opencode",
        )
        if provider is None:
            self.form_state = None; return
        if provider == "codex":
            model_id = await self._pick_codex_model(self.storage.get_setting("codex_default_model"))
            if model_id is None:
                self.form_state = None; return
            reasoning = self.storage.get_setting("codex_default_reasoning", "medium") or "medium"
        else:
            model_id = await self._pick_opencode_model(self.storage.get_setting("opencode_default_model"))
            if model_id is None:
                self.form_state = None; return
            reasoning = None
        self.storage.add_project_agent(
            project_id=project.id, name=name, role=role, provider=provider,
            model_id=model_id, reasoning=reasoning,
            system_instructions=f"Act as the project's {role}. Keep context inside project {project.name}.",
            read_scope=["**"], write_scope=[] if "review" in role.lower() else ["**"], handoff_scope=["*"],
        )
        self.form_state = None
        self.view_mode = "project"
        self._append_event("success", f"agent added · {name} · {role} · {provider}/{model_id}")

    async def _agent_command(self, argument: str) -> None:
        project = self._active_project()
        if not project:
            self._append_event("warning", "open a project first")
            return
        arg = argument.strip()
        if not arg or arg == "list":
            await self._agents_flow(); return
        if arg.lower() == "add":
            self.form_state = {"kind": "agent_add", "stage": "name"}
            self._append_event("info", "Agent name? Example: frontend, backend, documentation, reviewer, supervisor")
            return
        if arg.lower().startswith("remove "):
            name = arg.split(None, 1)[1]
            agent = next((a for a in self.storage.list_project_agents(project.id) if a.name == name), None)
            if not agent:
                self._append_event("warning", f"agent not found · {name}"); return
            self.storage.delete_project_agent(agent.id)
            self._append_event("success", f"agent removed · {name}"); return
        if arg.lower().startswith("model "):
            pieces = arg.split(None, 2)
            if len(pieces) < 2:
                return
            name = pieces[1]
            agent = next((a for a in self.storage.list_project_agents(project.id) if a.name == name), None)
            if not agent:
                self._append_event("warning", f"agent not found · {name}"); return
            provider = await self._pick("Change agent provider", [("opencode","OpenCode","live catalog"),("codex","Codex","live catalog")], default_key=agent.provider)
            if provider is None: return
            model = await (self._pick_codex_model(agent.model_id) if provider == "codex" else self._pick_opencode_model(agent.model_id))
            if model is None: return
            self.storage.update_project_agent(agent.id, provider=provider, model_id=model)
            self._append_event("success", f"{name} model · {provider}/{model}")
            return
        self._append_event("warning", "usage: /agent add | /agent model <name> | /agent remove <name>")

    async def _context_command(self, argument: str) -> None:
        project = self._active_project()
        if not project:
            self._append_event("warning", "open a project first")
            return
        arg = argument.strip()
        if not arg or arg == "list":
            docs = self.storage.list_project_context(project.id)
            if not docs: self._append_event("info", "no project context documents")
            for item in docs: self._append_event("info", f"context · {item.name} · {item.kind}")
            return
        head, _, tail = arg.partition(" ")
        if head == "add":
            if not tail.strip():
                self._append_event("warning", "usage: /context add <Windows or WSL path>"); return
            try:
                import_context_file(self.storage, project.id, tail.strip())
                self._append_event("success", f"context imported · {Path(tail.strip()).name}")
            except Exception as exc:
                self._append_event("error", f"context import failed · {exc}")
            return
        if head in {"new", "paste"}:
            name = tail.strip() or "context.md"
            self.form_state = {"kind": "context_text", "stage": "body", "name": name}
            self._append_event("info", f"Paste/write {name} in the composer. Ctrl+J adds lines; Enter saves.")
            return
        if head == "scan":
            imported = auto_import_common_context(self.storage, project.id, Path(project.workspace_path))
            self._append_event("success", f"context scan · {len(imported)} new common document(s)")
            return
        self._append_event("warning", "usage: /context [list|add <path>|new <name>|paste <name>|scan]")

    async def _handle_form_input(self, text: str) -> bool:
        if not self.form_state:
            return False
        if text.strip().lower() in {"/cancel", "cancel"}:
            self.form_state = None
            self._append_event("warning", "setup cancelled")
            return True
        kind = self.form_state.get("kind")
        stage = self.form_state.get("stage")
        if kind == "project_new":
            if stage == "name":
                if not text.strip():
                    self._append_event("warning", "project name cannot be empty"); return True
                self.form_state["name"] = text.strip()
                self.form_state["stage"] = "path"
                self._append_event("info", f"Workspace path? Use . for current folder ({Path.cwd()}) or paste C:\\... / D:\\...")
                return True
            if stage == "path":
                await self._finish_project_create(text.strip() or ".")
                return True
        if kind == "agent_add":
            if stage == "name":
                if not text.strip(): self._append_event("warning", "agent name cannot be empty"); return True
                self.form_state["name"] = re.sub(r"[^A-Za-z0-9_-]+", "-", text.strip()).strip("-").lower()
                self.form_state["stage"] = "role"
                self._append_event("info", "Agent role? Example: Frontend Developer, Backend Developer, Documentation, Reviewer, Supervisor")
                return True
            if stage == "role":
                await self._agent_add_finish(text.strip() or "Worker")
                return True
        if kind == "context_text" and stage == "body":
            try:
                project = self._active_project()
                if not project: raise ValueError("no active project")
                create_context_text(self.storage, project.id, self.form_state["name"], text)
                self._append_event("success", f"context created · {self.form_state['name']}")
            except Exception as exc:
                self._append_event("error", f"context create failed · {exc}")
            self.form_state = None
            return True
        return False

    async def _approve_project_run(self, prompt: str) -> bool:
        project = self._active_project()
        if not project:
            return False
        agents = self.storage.list_project_agents(project.id)
        if not agents:
            self._append_event("warning", "add at least one project agent before /run")
            return False
        summary = f"{len(agents)} agents · {project.approval_mode} · {self._short(project.workspace_path, 52)}"
        decision = await self._pick(
            "Approve project run?",
            [("approve", "Approve this run", summary), ("cancel", "Cancel", "no agent will start")],
            default_key="cancel",
        )
        if decision != "approve":
            self.storage.record_project_approval(project_id=project.id, action="team_run", permission_mode=project.approval_mode, decision="denied", details=prompt)
            self._append_event("warning", "project run not approved")
            return False
        if project.approval_mode == "full_access":
            confirm = await self._pick(
                "Full Access · confirm again",
                [("cancel","Cancel","recommended if full machine access is unnecessary"),
                 ("approve","Approve Full Access for this run","provider sandbox may permit access beyond the workspace")],
                default_key="cancel",
            )
            if confirm != "approve":
                self.storage.record_project_approval(project_id=project.id, action="team_run", permission_mode=project.approval_mode, decision="denied", details="full-access confirmation declined")
                return False
        self.storage.record_project_approval(project_id=project.id, action="team_run", permission_mode=project.approval_mode, decision="approved", details=prompt)
        return True

    async def _execute_project_task(self, task: TaskState, project_id: str) -> None:
        callback = self._thread_event_callback(task.task_id)
        try:
            result: ProjectTurnResult = await asyncio.to_thread(
                execute_project_team,
                storage=self.storage, registry=self.registry, project_id=project_id,
                instruction=task.prompt, approved=True, event_callback=callback,
                cancel_event=task.cancel_event,
            )
            self.session_id = result.session_id
            self.view_mode = "session"
            task.status = "done"; task.output = result.final_output
            task.detail = f"project team · {result.verdict or 'complete'}"
            self._append_event("success", f"project team complete · {result.verdict or 'done'}", task.task_id)
        except Exception as exc:
            task.error = str(exc); task.status = "cancelled" if task.cancel_event.is_set() else "failed"
            self._append_event("warning" if task.status == "cancelled" else "error", f"project run · {exc}", task.task_id)
        finally:
            task.finished_at = time.monotonic(); self.foreground_task_id = None
            self.app.invalidate()

    async def _run_project(self, prompt: str) -> None:
        project = self._active_project()
        if not project:
            self._append_event("warning", "open a project first"); return
        if not prompt.strip():
            self._append_event("warning", "usage: /run <complete project goal>"); return
        if self.foreground_task_id is not None:
            self._append_event("warning", "finish/stop the current foreground run first"); return
        if not await self._approve_project_run(prompt):
            return
        task = self._new_task(f"project · {self._short(prompt, 30)}", prompt, background=False)
        self.foreground_task_id = task.task_id
        self._append_event("queued", f"approved project run · {project.name}", task.task_id)
        self.app.create_background_task(self._execute_project_task(task, project.id))

    # ---------- commands ----------

    async def _run_doctor_terminal(self) -> None:
        def doctor():
            run_doctor()
            try:
                input("\nPress Enter to return to JORE TUI...")
            except EOFError:
                pass

        await run_in_terminal(doctor)

    async def _show_help(self) -> None:
        self._append_event(
            "info",
            "commands · /new /projects /project /agents /agent /context /run /model /models /sessions /status /runstate /history /attempts /export /bg /tasks /queue /busy /stop /escalate /dock /theme /settings /doctor /home /exit",
        )
        self._append_event(
            "info",
            "keys · Enter send · Ctrl+J newline · PgUp/PgDn conversation · End latest · Ctrl+Shift+C/V terminal copy/paste · ↑↓ picker · Ctrl+T dock · Ctrl+R compact · Ctrl+C interrupt/double-exit",
        )

    async def _handle_home_choice(self, text: str) -> bool:
        stripped = text.strip()
        if stripped == "1":
            await self._new_session_flow(); return True
        if stripped == "2":
            await self._projects_flow(); return True
        if stripped == "3":
            await self._sessions_flow(); return True
        if stripped == "4":
            await self._models_flow(); return True
        if stripped == "5":
            await self._settings_flow(); return True
        if stripped == "6":
            await self._run_doctor_terminal(); return True
        if stripped == "7":
            self._cancel_all(); self.app.exit(result=0); return True
        return False

    async def _handle_command(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped.startswith("/"):
            return False

        command, _, argument = stripped.partition(" ")
        command = command.lower()
        argument = argument.strip()

        if command == "/help":
            await self._show_help()
        elif command == "/new":
            await self._new_session_flow()
        elif command == "/projects":
            await self._projects_flow()
        elif command == "/project":
            await self._project_command(argument)
        elif command == "/agents":
            await self._agents_flow()
        elif command == "/agent":
            await self._agent_command(argument)
        elif command == "/context":
            await self._context_command(argument)
        elif command == "/run":
            await self._run_project(argument)
        elif command == "/model":
            await self._model_flow()
        elif command == "/models":
            await self._models_flow()
        elif command == "/sessions":
            await self._sessions_flow()
        elif command in {"/status", "/runstate"}:
            session = self._session()
            if session:
                state = self.storage.get_latest_run_state(session.id)
                cooldowns = self.storage.list_active_cooldowns()
                self._append_event(
                    "info",
                    f"{session.title} · {session.mode} · {self._model_label()} · {len(self.storage.get_messages(session.id))} msg · {len(self.storage.get_attempts(session.id))} attempt",
                )
                if state:
                    self._append_event(
                        "info",
                        f"RunState {state.task_id} · {state.status} · worker {state.current_worker} · verdict {state.verdict or '-'} · retry {state.retries_used}/{state.retry_budget} · escalation {state.escalation_state}",
                    )
                    if state.failure_fingerprint:
                        self._append_event(
                            "info",
                            f"fingerprint · {state.failure_fingerprint} · loop {state.loop_count}x",
                        )
                if cooldowns:
                    for item in cooldowns[:4]:
                        from agenthub.resilience import remaining_seconds
                        self._append_event(
                            "warning",
                            f"cooldown · {item.scope} · {remaining_seconds(item.cooldown_until)}s · {item.reason}",
                        )
            else:
                self._append_event("info", "home · no active session")
        elif command == "/history":
            self.view_mode = "session"
            self._append_event("info", "conversation timeline active")
        elif command == "/attempts":
            session = self._session()
            if session:
                attempts = self.storage.get_attempts(session.id)
                if attempts:
                    for item in attempts[-5:]:
                        self._append_event(
                            "info",
                            f"attempt {item.attempt_number} · {item.agent_role} · {item.model} · {item.status}",
                        )
                else:
                    self._append_event("info", "no attempts yet")
        elif command == "/export":
            session = self._session()
            if session:
                md, js = self.storage.export_session(session.id)
                self._append_event(
                    "success",
                    f"exported · {md.name} · {js.name}",
                )
            else:
                self._append_event("warning", "no session to export")
        elif command == "/bg":
            if argument:
                await self._start_background(argument)
            else:
                self._append_event("warning", "usage: /bg <prompt>")
        elif command == "/tasks":
            await self._tasks_flow()
        elif command == "/queue":
            if argument:
                self.pending_prompts.append(argument)
                self._append_event(
                    "queued",
                    f"queued follow-up · {len(self.pending_prompts)} waiting",
                )
                if self.foreground_task_id is None:
                    next_prompt = self.pending_prompts.popleft()
                    await self._start_foreground(next_prompt)
            else:
                self._append_event(
                    "info",
                    f"queue contains {len(self.pending_prompts)} prompt(s)",
                )
        elif command == "/busy":
            current = self.storage.get_setting(
                "busy_input_mode",
                "queue",
            ) or "queue"
            if argument in {"queue", "interrupt"}:
                self.storage.set_setting("busy_input_mode", argument)
                self._append_event(
                    "success",
                    f"busy input mode · {argument}",
                )
            else:
                self._append_event(
                    "info",
                    f"busy input mode · {current} · use /busy queue or /busy interrupt",
                )
        elif command == "/escalate":
            if self.last_needs_fix_task and self.last_needs_fix_result:
                await self._needs_fix_flow(
                    self.last_needs_fix_task,
                    self.last_needs_fix_result,
                )
            else:
                self._append_event("info", "no unresolved NEEDS_FIX result")
        elif command == "/dock":
            self.dock_visible = not self.dock_visible
            self._append_event(
                "info",
                "work dock shown" if self.dock_visible else "work dock hidden",
            )
        elif command == "/stop":
            current = self._foreground_task()
            if current and current.status == "running":
                current.status = "cancel-requested"
                current.cancel_event.set()
                self._append_event(
                    "warning",
                    "foreground stop requested",
                    current.task_id,
                )
            else:
                self._append_event("info", "no foreground run active")
        elif command in {"/theme", "/skin"}:
            await self._theme_flow()
        elif command == "/settings":
            await self._settings_flow()
        elif command == "/doctor":
            await self._run_doctor_terminal()
        elif command == "/clear":
            self.events.clear()
        elif command in {"/home", "/back"}:
            self.view_mode = "home"
        elif command in {"/exit", "/quit"}:
            self._cancel_all()
            self.app.exit(result=0)
        else:
            self._append_event(
                "warning",
                f"unknown command · {command}",
            )
        return True

    async def _handle_submit(self, text: str) -> None:
        if self.form_state is not None and not text.strip().startswith("/"):
            if await self._handle_form_input(text):
                self.app.invalidate(); return
        if self.form_state is not None and text.strip().lower() == "/cancel":
            await self._handle_form_input(text); self.app.invalidate(); return

        if self.view_mode == "home":
            if await self._handle_home_choice(text):
                self.app.invalidate()
                return

        if await self._handle_command(text):
            self.app.invalidate()
            return

        if self.session_id is None:
            self._append_event(
                "warning",
                "create or resume a session before sending a prompt",
            )
            return

        await self._start_foreground(text)
        self.view_mode = "session"
        self.app.invalidate()

    # ---------- lifecycle ----------

    async def _ticker(self) -> None:
        while not self.closed:
            await asyncio.sleep(1.0)
            if self._active_task_count():
                self.app.invalidate()

    async def run_async(self) -> int:
        self.loop = asyncio.get_running_loop()
        ticker = self.app.create_background_task(self._ticker())
        try:
            result = await self.app.run_async()
            return int(result or 0)
        finally:
            self.closed = True
            self._cancel_all()
            ticker.cancel()

    def _goodbye_text(self, cols: int) -> str:
        width = 46 if cols < 72 else 64 if cols < 110 else 82
        inner = width - 2
        session = self._session()
        lines: list[str] = []

        def center(value: str = "") -> str:
            return "│" + value[:inner].center(inner) + "│"

        def rule() -> str:
            return "├" + "─" * inner + "┤"

        lines.append("╭" + "─" * inner + "╮")
        lines.extend([
            center("S E E   Y O U"),
            center("♛"),
            center("J O R E"),
            center("session safely finalized"),
            rule(),
        ])

        if session is not None:
            messages = len(self.storage.get_messages(session.id))
            attempts = len(self.storage.get_attempts(session.id))
            try:
                created = datetime.fromisoformat(session.created_at.replace("Z", "+00:00"))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                elapsed = max(0, int((datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds()))
                duration = self._duration(elapsed)
            except Exception:
                duration = "saved"

            meta = [
                f" Session   : {session.id}",
                f" Duration  : {duration}",
                f" Messages  : {messages}",
                f" Runs      : {attempts}",
                f" Project   : {self._short(str(Path.cwd()), max(12, inner - 14))}",
                " Resume    : jore → /sessions",
            ]
            for item in meta:
                lines.append("│" + item[:inner].ljust(inner) + "│")
            lines.append(rule())

        lines.extend([
            center('“Good ideas always find a way.”'),
            center("See you next session ♡"),
            "╰" + "─" * inner + "╯",
        ])
        return "\n".join(lines)

    def run(self) -> int:
        result = asyncio.run(self.run_async())
        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 80
        print(self._goodbye_text(cols))
        return result


def run_tui() -> int:
    return AgentHubTUI().run()


def main() -> None:
    raise SystemExit(run_tui())


if __name__ == "__main__":
    main()
