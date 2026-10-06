from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from agenthub.dependencies import build_runtime_env


def _resolve_orchestrator_project() -> Path:
    configured = os.environ.get("JORE_ORCHESTRATOR_HOME")
    if configured:
        return Path(configured).expanduser()
    frozen = Path.home() / ".local" / "share" / "jore" / "runtime" / "current" / "orchestrator"
    if frozen.is_dir():
        return frozen
    return Path.home() / "projects" / "cli-agent-orchestrator"


CAO_PROJECT = _resolve_orchestrator_project()
CAO_HOST = "127.0.0.1"
CAO_PORT = 9889

EventCallback = Callable[[str, str], None]


class JOREError(RuntimeError):
    """Base runtime error raised by JORE orchestration."""


# Backward-compatible internal alias for adapters that still import the old name.
AgentHubError = JOREError


@dataclass
class AgentResult:
    agent: str
    output: str


@dataclass
class ReviewResult:
    verdict: str
    review: str
    raw: str


def _emit(callback: EventCallback | None, kind: str, message: str) -> None:
    if callback is not None and message:
        callback(kind, message)


class CaoDriver:
    def __init__(
        self,
        working_directory: Path,
        cao_project: Path = CAO_PROJECT,
    ) -> None:
        self.working_directory = working_directory.resolve()
        self.cao_project = cao_project.resolve()

        self.cao_bin = self.cao_project / ".venv" / "bin" / "cao"
        self.cao_server_bin = (
            self.cao_project / ".venv" / "bin" / "cao-server"
        )

        self._server_process: subprocess.Popen | None = None
        self._owns_server = False
        self._active_sessions: set[str] = set()
        self._closed = False

        # v1.11.2 clean-release mode: Auto workers run through the
        # installed OpenCode CLI directly. Keep this compatibility class so
        # the higher-level orchestration API remains stable without requiring
        # any development checkout.

    @staticmethod
    def _server_ready() -> bool:
        try:
            with socket.create_connection(
                (CAO_HOST, CAO_PORT),
                timeout=0.25,
            ):
                return True
        except OSError:
            return False

    def _runtime_env(self) -> dict[str, str]:
        return build_runtime_env()

    def _ensure_server(
        self,
        event_callback: EventCallback | None = None,
    ) -> None:
        if self._server_ready():
            _emit(event_callback, "orchestrator", "JORE runtime ready")
            return

        if not self.cao_server_bin.exists():
            raise JOREError(
                "JORE orchestration service executable is missing. Run `jore doctor`."
            )

        log_path = Path("/tmp/jore-orchestration.log")
        _emit(event_callback, "orchestrator", "starting JORE runtime")

        with log_path.open("ab") as log:
            process = subprocess.Popen(
                [str(self.cao_server_bin)],
                cwd=self.cao_project,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=self._runtime_env(),
            )

        self._server_process = process
        self._owns_server = True
        deadline = time.monotonic() + 10

        while time.monotonic() < deadline:
            if self._server_ready():
                _emit(event_callback, "orchestrator", "JORE runtime started")
                return
            if process.poll() is not None:
                break
            time.sleep(0.2)

        self.close()
        raise JOREError(
            f"JORE orchestration service failed to start. See log: {log_path}"
        )

    @staticmethod
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

    def _run(
        self,
        args: list[str],
        *,
        check: bool = True,
        cancel_event: Event | None = None,
        timeout_seconds: int = 900,
        event_callback: EventCallback | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [str(self.cao_bin), *args]
        process = subprocess.Popen(
            command,
            cwd=self.cao_project,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=self._runtime_env(),
        )
        started = time.monotonic()
        stdout = ""
        stderr = ""

        while True:
            if cancel_event is not None and cancel_event.is_set():
                _emit(event_callback, "warning", "JORE runtime cancellation requested")
                self._terminate_process(process)
                raise JOREError("JORE run was cancelled.")

            if time.monotonic() - started > timeout_seconds:
                self._terminate_process(process)
                raise JOREError(
                    f"JORE orchestration command exceeded {timeout_seconds}s timeout."
                )

            try:
                stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
        completed = subprocess.CompletedProcess(
            command,
            int(process.returncode or 0),
            stdout,
            stderr,
        )

        if check and completed.returncode != 0:
            message = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "JORE orchestration command failed."
            )
            raise JOREError(message)

        return completed

    @staticmethod
    def _new_session_name(prefix: str) -> str:
        return f"jore-{prefix}-{uuid.uuid4().hex[:8]}"

    def _get_last_output(
        self,
        cao_session: str,
        *,
        cancel_event: Event | None = None,
        event_callback: EventCallback | None = None,
    ) -> str:
        _emit(event_callback, "orchestrator", "reading agent result")
        result = self._run(
            ["session", "status", cao_session, "--json"],
            cancel_event=cancel_event,
            event_callback=event_callback,
        )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise JOREError(
                "JORE orchestration returned an invalid internal response."
            ) from exc

        output = payload.get("conductor", {}).get("last_output")
        if not output:
            raise JOREError(
                f"No output returned by {cao_session}"
            )
        return output.strip()

    def _shutdown_session(self, cao_session: str) -> None:
        if not self._server_ready():
            return
        try:
            self._run(
                ["shutdown", "--session", cao_session],
                check=False,
                timeout_seconds=30,
            )
        finally:
            self._active_sessions.discard(cao_session)

    def cancel_current(self) -> None:
        for session in list(self._active_sessions):
            self._shutdown_session(session)

    def run_agent(
        self,
        *,
        profile: str,
        prompt: str,
        label: str,
        event_callback: EventCallback | None = None,
        cancel_event: Event | None = None,
    ) -> AgentResult:
        model_by_profile = {
            "nemotron-developer": "opencode/nemotron-3-ultra-free",
            "mimo-reviewer": "opencode/mimo-v2.6-flash-free",
        }
        model = model_by_profile.get(profile)
        if not model:
            raise JOREError(f"Unknown Auto worker profile: {profile}")

        # Lazy import avoids the driver <-> OpenCode adapter import cycle.
        from agenthub.opencode_driver import OpenCodeDriver

        _emit(event_callback, "orchestrator", f"starting {label} agent")
        return OpenCodeDriver(self.working_directory).run_agent(
            prompt=prompt,
            model=model,
            label=label,
            event_callback=event_callback,
            cancel_event=cancel_event,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        for session in list(self._active_sessions):
            self._shutdown_session(session)

        if self._owns_server and self._server_process:
            process = self._server_process
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    if process.poll() is None:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

            deadline = time.monotonic() + 3
            while (
                self._server_ready()
                and time.monotonic() < deadline
            ):
                time.sleep(0.1)

        self._server_process = None
        self._owns_server = False

    def __enter__(self) -> "CaoDriver":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def build_review_prompt(
    original_task: str,
    developer_output: str,
) -> str:
    return f"""
You are the reviewer.

Review the developer result against the original task.

ORIGINAL TASK:
{original_task}

DEVELOPER RESULT:
{developer_output}

Return exactly this format:

VERDICT: PASS or NEEDS_FIX
REVIEW:
<short explanation>

Do not implement changes.
Do not modify files.
""".strip()


def parse_review(output: str) -> ReviewResult:
    verdict = "UNKNOWN"
    for line in output.splitlines():
        normalized = line.strip().upper()
        if normalized == "VERDICT: PASS":
            verdict = "PASS"
            break
        if normalized == "VERDICT: NEEDS_FIX":
            verdict = "NEEDS_FIX"
            break

    review = output
    if "REVIEW:" in output:
        review = output.split("REVIEW:", 1)[1].strip()

    return ReviewResult(
        verdict=verdict,
        review=review,
        raw=output,
    )
