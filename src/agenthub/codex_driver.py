from __future__ import annotations

import os
import re
import selectors
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from threading import Event
from typing import Callable

from agenthub.dependencies import resolve_tool
from agenthub.driver import AgentHubError, AgentResult


EventCallback = Callable[[str, str], None]


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


class CodexDriver:
    def __init__(
        self,
        working_directory: Path,
        *,
        timeout_seconds: int = 900,
    ) -> None:
        self.working_directory = working_directory.resolve()
        self.timeout_seconds = timeout_seconds

        status = resolve_tool("codex")
        if not status.found or not status.path:
            raise AgentHubError(
                "Codex CLI was not found. Run `agenthub doctor` "
                "to repair or install it."
            )
        self.codex_bin = status.path

    def run_agent(
        self,
        *,
        prompt: str,
        model: str,
        reasoning: str,
        sandbox: str = "read-only",
        label: str = "codex",
        event_callback: EventCallback | None = None,
        cancel_event: Event | None = None,
    ) -> AgentResult:
        if not prompt.strip():
            raise AgentHubError("Codex prompt cannot be empty.")

        if not re.fullmatch(r"[a-z0-9_-]+", reasoning):
            raise AgentHubError(
                f"Invalid Codex reasoning level: {reasoning}"
            )

        if sandbox not in {
            "read-only",
            "workspace-write",
            "danger-full-access",
        }:
            raise AgentHubError(
                f"Unsupported Codex sandbox: {sandbox}"
            )

        with tempfile.NamedTemporaryFile(
            prefix="agenthub-codex-",
            suffix=".txt",
            delete=False,
        ) as tmp:
            output_path = Path(tmp.name)

        command = [
            self.codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            sandbox,
            "--cd",
            str(self.working_directory),
            "--model",
            model,
            "--config",
            f'model_reasoning_effort="{reasoning}"',
            "--output-last-message",
            str(output_path),
            prompt,
        ]

        _emit(event_callback, "provider", f"starting Codex · {model}")
        started = time.monotonic()
        process: subprocess.Popen[str] | None = None
        lines: list[str] = []

        try:
            process = subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=self.working_directory,
                bufsize=1,
                start_new_session=True,
            )

            selector = selectors.DefaultSelector()
            assert process.stdout is not None
            selector.register(process.stdout, selectors.EVENT_READ)

            while True:
                if cancel_event is not None and cancel_event.is_set():
                    _emit(event_callback, "warning", "Codex cancellation requested")
                    _terminate_process(process)
                    raise AgentHubError("Codex run was cancelled.")

                if time.monotonic() - started > self.timeout_seconds:
                    _terminate_process(process)
                    raise AgentHubError(
                        "Codex exceeded the JORE execution timeout "
                        f"({self.timeout_seconds}s)."
                    )

                for key, _ in selector.select(timeout=0.2):
                    line = key.fileobj.readline()
                    if not line:
                        continue
                    lines.append(line)
                    cleaned = line.strip()
                    if cleaned:
                        _emit(
                            event_callback,
                            "provider_output",
                            cleaned[:180],
                        )

                if process.poll() is not None:
                    remainder = process.stdout.read()
                    if remainder:
                        lines.append(remainder)
                    break

            return_code = int(process.returncode or 0)
            combined = "".join(lines).strip()

            if return_code != 0:
                raise AgentHubError(
                    combined or f"Codex execution failed with code {return_code}."
                )

            output = ""
            if output_path.exists():
                output = output_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).strip()

            if not output:
                output = combined

            if not output:
                raise AgentHubError(
                    "Codex completed but returned no final output."
                )

            _emit(event_callback, "success", f"Codex completed in {int(time.monotonic() - started)}s")
            return AgentResult(agent=label, output=output)

        finally:
            if process is not None and process.poll() is None:
                _terminate_process(process)
            output_path.unlink(missing_ok=True)
