from __future__ import annotations

import json
import os
import selectors
import re
import signal
import subprocess
import time
from pathlib import Path
from threading import Event
from typing import Callable

from agenthub.dependencies import build_runtime_env, resolve_tool
from agenthub.driver import AgentHubError, AgentResult


EventCallback = Callable[[str, str], None]


_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_PERMISSION_RE = re.compile(
    r"permission requested:\s*([^\s]+)\s*\((.*?)\);\s*auto-rejecting",
    re.IGNORECASE,
)


def _strip_ansi(value: str) -> str:
    return _ANSI_RE.sub("", value or "")


def _merge_inline_config(base: str | None, overlay_rules: list[dict[str, str]]) -> str:
    payload: dict = {}
    if base:
        try:
            parsed = json.loads(base)
            if isinstance(parsed, dict):
                payload = parsed
        except (json.JSONDecodeError, TypeError):
            payload = {}
    existing = payload.get("permissions")
    if not isinstance(existing, list):
        existing = []
    payload["permissions"] = [*existing, *overlay_rules]
    return json.dumps(payload, separators=(",", ":"))


def _emit(callback: EventCallback | None, kind: str, message: str) -> None:
    if callback is not None and message:
        callback(kind, message)


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


class OpenCodeDriver:
    _run_capabilities: set[str] | None = None

    def __init__(
        self,
        working_directory: Path,
        *,
        timeout_seconds: int = 900,
    ) -> None:
        self.working_directory = working_directory.resolve()
        self.timeout_seconds = timeout_seconds

        status = resolve_tool("opencode")
        if not status.found or not status.path:
            raise AgentHubError(
                "OpenCode CLI was not found. Run `agenthub doctor` to repair it."
            )
        self.opencode_bin = status.path

    @staticmethod
    def _extract_json_text(raw: str) -> str:
        text_parts: dict[str, str] = {}
        ordered_ids: list[str] = []
        anonymous: list[str] = []

        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") != "text":
                continue
            part = event.get("part") or {}
            text = part.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            part_id = part.get("id")
            if isinstance(part_id, str) and part_id:
                if part_id not in text_parts:
                    ordered_ids.append(part_id)
                text_parts[part_id] = text
            else:
                anonymous.append(text)

        chunks = [text_parts[item] for item in ordered_ids if item in text_parts]
        chunks.extend(anonymous)
        return "\n".join(
            chunk.strip() for chunk in chunks if chunk.strip()
        ).strip()

    @staticmethod
    def _describe_event(raw_line: str) -> tuple[str, str] | None:
        line = _strip_ansi(raw_line).strip()
        if not line.startswith("{"):
            return ("provider_output", line[:180]) if line else None

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return ("provider_output", line[:180])

        event_type = str(event.get("type") or "event")
        part = event.get("part") if isinstance(event.get("part"), dict) else {}
        tool_name = (
            part.get("tool")
            or part.get("name")
            or event.get("tool")
            or event.get("name")
        )

        if tool_name:
            return "tool", f"{tool_name}"

        if "tool" in event_type.lower():
            return "tool", event_type

        if event_type == "text":
            return None

        return "provider", event_type

    def _get_run_capabilities(self) -> set[str]:
        """Return supported `opencode run` flags.

        JORE intentionally probes the installed CLI instead of assuming that
        flags from a previous OpenCode release still exist.
        """
        cached = type(self)._run_capabilities
        if cached is not None:
            return cached

        runtime_env = build_runtime_env()
        try:
            completed = subprocess.run(
                [self.opencode_bin, "run", "--help"],
                cwd=self.working_directory,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=runtime_env,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AgentHubError(
                f"Unable to inspect OpenCode CLI capabilities: {exc}"
            ) from exc

        help_text = _strip_ansi(completed.stdout or "")
        if completed.returncode != 0 or "Run OpenCode with a message" not in help_text:
            detail = help_text.strip() or f"exit code {completed.returncode}"
            raise AgentHubError(
                "The installed OpenCode CLI does not expose a compatible "
                f"`run` command. Details: {detail}"
            )

        flags = set(re.findall(r"--[a-zA-Z0-9-]+", help_text))
        type(self)._run_capabilities = flags
        return flags

    def run_agent(
        self,
        *,
        prompt: str,
        model: str,
        label: str = "opencode",
        approval_mode: str = "ask",
        sandbox_mode: str = "workspace-write",
        approval_policy: str = "on-request",
        approvals_reviewer: str = "user",
        agent_profile: str | None = None,
        event_callback: EventCallback | None = None,
        cancel_event: Event | None = None,
    ) -> AgentResult:
        if not prompt.strip():
            raise AgentHubError("OpenCode prompt cannot be empty.")
        if not model.strip() or "/" not in model:
            raise AgentHubError(f"Invalid OpenCode model ID: {model}")

        auto_approve = (
            approval_mode in {"approve_for_me", "full_access"}
            or approval_policy == "never"
            or approvals_reviewer == "auto_review"
        )

        # Never rely on the user's OpenCode default_agent for JORE project work.
        # A user can globally select `plan`, which is intentionally restricted and
        # can return convincing prose without changing a single file.
        selected_agent = (agent_profile or ("plan" if sandbox_mode == "read-only" else "build")).strip()
        if selected_agent not in {"build", "plan"}:
            raise AgentHubError(f"Unsupported OpenCode primary agent for JORE: {selected_agent}")

        capabilities = self._get_run_capabilities()
        required_flags = {"--agent", "--model", "--format", "--standalone"}
        missing_flags = sorted(required_flags - capabilities)
        if missing_flags:
            raise AgentHubError(
                "The installed OpenCode CLI is incompatible with JORE project "
                "execution. Missing `opencode run` flag(s): "
                + ", ".join(missing_flags)
                + ". JORE sets the project workspace through the process working "
                "directory, so no `--dir` flag is required. Update OpenCode or "
                "run `jore doctor`."
            )
        if auto_approve and "--auto" not in capabilities:
            raise AgentHubError(
                "This OpenCode CLI does not support `opencode run --auto`, "
                "which JORE needs for the project's Approve for Me / Full Access "
                "permission profile. Update OpenCode or choose Ask for Approval."
            )

        command = [self.opencode_bin, "run", "--standalone"]
        if auto_approve:
            command.append("--auto")
        command.extend([
            "--agent", selected_agent,
            "--model", model,
            "--format", "json",
            prompt,
        ])

        # OpenCode's headless `run` auto-rejects permission prompts unless --auto
        # is active.  JORE therefore makes the configured project workspace an
        # explicit allowed boundary and keeps everything else outside it gated.
        workspace_rule = self.working_directory.as_posix().rstrip("/") + "/*"
        if approval_mode == "full_access" or sandbox_mode == "danger-full-access":
            external_default = "allow"
        else:
            external_default = "ask"
        rules: list[dict[str, str]] = [
            {"action": "external_directory", "resource": "*", "effect": external_default},
            {"action": "external_directory", "resource": workspace_rule, "effect": "allow"},
        ]
        if sandbox_mode == "read-only":
            rules.append({"action": "edit", "resource": "*", "effect": "deny"})

        runtime_env = build_runtime_env()
        runtime_env["PWD"] = str(self.working_directory)
        runtime_env["JORE_PROJECT_WORKSPACE"] = str(self.working_directory)
        runtime_env["OPENCODE_CONFIG_CONTENT"] = _merge_inline_config(
            runtime_env.get("OPENCODE_CONFIG_CONTENT"), rules
        )

        mode_label = "auto-approve" if auto_approve else "approval-gated"
        _emit(
            event_callback,
            "provider",
            f"starting OpenCode · {model} · {selected_agent} · standalone · {mode_label} · cwd {self.working_directory}",
        )
        started = time.monotonic()
        process: subprocess.Popen[str] | None = None
        stdout_lines: list[str] = []

        try:
            process = subprocess.Popen(
                command,
                cwd=self.working_directory,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=runtime_env,
                bufsize=1,
                start_new_session=True,
            )

            selector = selectors.DefaultSelector()
            assert process.stdout is not None
            selector.register(process.stdout, selectors.EVENT_READ)

            while True:
                if cancel_event is not None and cancel_event.is_set():
                    _emit(event_callback, "warning", "OpenCode cancellation requested")
                    _terminate_process(process)
                    raise AgentHubError("OpenCode run was cancelled.")

                if time.monotonic() - started > self.timeout_seconds:
                    _terminate_process(process)
                    raise AgentHubError(
                        "OpenCode exceeded the JORE execution timeout "
                        f"({self.timeout_seconds}s)."
                    )

                for key, _ in selector.select(timeout=0.2):
                    line = key.fileobj.readline()
                    if not line:
                        continue
                    stdout_lines.append(line)
                    described = self._describe_event(line)
                    if described:
                        _emit(event_callback, described[0], described[1])

                if process.poll() is not None:
                    remainder = process.stdout.read()
                    if remainder:
                        stdout_lines.append(remainder)
                    break

            return_code = int(process.returncode or 0)
            raw_output = "".join(stdout_lines)
            clean_output = _strip_ansi(raw_output)
            permission_match = _PERMISSION_RE.search(clean_output)

            if return_code != 0:
                if permission_match:
                    action, resource = permission_match.groups()
                    raise AgentHubError(
                        "OpenCode permission required: "
                        f"{action} ({resource}). JORE did not grant access outside "
                        f"the project workspace {self.working_directory}. "
                        "Use the project's permission settings or keep the operation "
                        "inside the workspace."
                    )
                detail = clean_output.strip() or (
                    f"OpenCode execution failed with code {return_code}."
                )
                raise AgentHubError(detail)

            output = self._extract_json_text(clean_output)
            if not output:
                non_json = [
                    line
                    for line in raw_output.splitlines()
                    if line.strip() and not line.lstrip().startswith("{")
                ]
                output = "\n".join(non_json).strip()

            if not output:
                if permission_match:
                    action, resource = permission_match.groups()
                    raise AgentHubError(
                        "OpenCode permission required: "
                        f"{action} ({resource}). The headless provider rejected it. "
                        "The project workspace itself is allowed; access beyond that "
                        "boundary requires a different project permission decision."
                    )
                raise AgentHubError(
                    "OpenCode completed but JORE did not receive final text output."
                )

            _emit(event_callback, "success", f"OpenCode completed in {int(time.monotonic() - started)}s")
            return AgentResult(agent=label, output=output)

        finally:
            if process is not None and process.poll() is None:
                _terminate_process(process)
