from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from agenthub.codex_driver import CodexDriver
from agenthub.driver import AgentHubError, AgentResult
from agenthub.model_registry import ModelRegistry
from agenthub.opencode_driver import OpenCodeDriver
from agenthub.projects import assert_workspace_bridge, context_for_agent
from agenthub.storage import Storage

EventCallback = Callable[[str, str], None]


def _emit(callback: EventCallback | None, kind: str, text: str) -> None:
    if callback and text:
        callback(kind, text)


def _clip(text: str, limit: int = 10000) -> str:
    value = (text or "").strip()
    return value if len(value) <= limit else value[:limit] + "\n...[truncated]"


def _is_role(role: str, needle: str) -> bool:
    return needle.lower() in (role or "").lower()


_WORKSPACE_IGNORE_DIRS = {
    ".git", ".jore", "node_modules", ".venv", "venv", "dist", "build",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".next", ".cache",
}


def _workspace_snapshot(workspace: Path) -> dict[str, tuple[int, int]]:
    """Cheap mutation snapshot used to verify that implementation really happened.

    JORE intentionally does not trust an agent's prose claim that files were
    created.  The snapshot tracks path, size and nanosecond mtime for ordinary
    project files while ignoring JORE metadata and common generated trees.
    """
    snapshot: dict[str, tuple[int, int]] = {}
    for path in workspace.rglob("*"):
        try:
            rel = path.relative_to(workspace)
        except ValueError:
            continue
        if any(part in _WORKSPACE_IGNORE_DIRS for part in rel.parts):
            continue
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        snapshot[rel.as_posix()] = (int(stat.st_size), int(stat.st_mtime_ns))
    return snapshot


def _workspace_changes(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> list[str]:
    changed: list[str] = []
    for name in sorted(set(before) | set(after)):
        if before.get(name) != after.get(name):
            prefix = "deleted: " if name in before and name not in after else ""
            changed.append(prefix + name)
    return changed


def _format_changes(changes: list[str], limit: int = 80) -> str:
    if not changes:
        return "(no verified workspace changes)"
    shown = changes[:limit]
    result = "\n".join(f"- {item}" for item in shown)
    if len(changes) > limit:
        result += f"\n- ... and {len(changes) - limit} more"
    return result



@dataclass(slots=True)
class ProjectTurnResult:
    session_id: str
    run_state_id: str
    final_output: str
    agent_outputs: dict[str, str]
    verdict: str | None = None
    review: str | None = None


def _run_project_agent(
    *,
    provider: str,
    model_id: str,
    reasoning: str | None,
    workspace: Path,
    sandbox_mode: str,
    approval_mode: str,
    approval_policy: str,
    approvals_reviewer: str,
    agent_profile: str | None = None,
    prompt: str,
    label: str,
    event_callback: EventCallback | None,
    cancel_event: Event | None,
) -> AgentResult:
    if provider == "codex":
        return CodexDriver(workspace).run_agent(
            prompt=prompt,
            model=model_id,
            reasoning=reasoning or "medium",
            sandbox=sandbox_mode,
            label=label,
            event_callback=event_callback,
            cancel_event=cancel_event,
        )
    if provider == "opencode":
        return OpenCodeDriver(workspace).run_agent(
            prompt=prompt,
            model=model_id,
            label=label,
            approval_mode=approval_mode,
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            approvals_reviewer=approvals_reviewer,
            agent_profile=agent_profile,
            event_callback=event_callback,
            cancel_event=cancel_event,
        )
    raise AgentHubError(f"Unsupported project provider: {provider}")


def execute_project_team(
    *,
    storage: Storage,
    registry: ModelRegistry,
    project_id: str,
    instruction: str,
    approved: bool,
    event_callback: EventCallback | None = None,
    cancel_event: Event | None = None,
) -> ProjectTurnResult:
    if not approved:
        raise AgentHubError("Project run requires explicit user approval.")

    project = storage.get_project(project_id)
    workspace = assert_workspace_bridge(project.workspace_path)
    if not workspace.is_dir():
        raise AgentHubError(f"Project workspace is unavailable: {workspace}")

    agents = [item for item in storage.list_project_agents(project_id) if item.enabled]
    if not agents:
        raise AgentHubError("Project has no enabled agents. Add at least one agent first.")

    supervisors = [a for a in agents if _is_role(a.role, "supervisor")]
    reviewers = [a for a in agents if _is_role(a.role, "review")]
    workers = [a for a in agents if a not in supervisors and a not in reviewers]
    if not workers:
        workers = [a for a in agents if a not in reviewers]

    reviewer_name = reviewers[0].name if reviewers else None
    session = storage.create_session(
        mode="project",
        primary_model="team",
        reviewer_model=reviewer_name,
        title=instruction.strip()[:60] or project.name,
        project_id=project.id,
    )
    storage.add_message(session.id, "user", instruction)
    state = storage.create_run_state(
        session_id=session.id,
        current_worker=workers[0].name if workers else agents[0].name,
        reviewer=reviewer_name,
        original_instruction=instruction,
        project_id=project.id,
    )
    storage.update_run_state(state.id, escalation_state="project_team")

    plan = ""
    outputs: dict[str, str] = {}

    if supervisors:
        supervisor = supervisors[0]
        _emit(event_callback, "provider", f"project supervisor · {supervisor.name} · planning")
        ctx = context_for_agent(storage, project.id, supervisor.name)
        prompt = f"""
You are {supervisor.name}, the Supervisor for JORE project {project.name}.
Workspace boundary: {workspace}
The process working directory is already the project root. Use relative paths for project files; do not prefix the absolute workspace path unless a tool requires it.
Project isolation: {project.isolation_mode}
Permission profile: {project.approval_mode} / {project.sandbox_mode}

Create a concise execution plan for the project team. Do not invent files outside this project.
Assign work conceptually to the configured team. The user has already approved this run.

PROJECT CONTEXT:
{ctx or '(no registered context documents)'}

USER GOAL:
{instruction}

Return a practical plan only. Do not do the workers' implementation yet.
""".strip()
        result = _run_project_agent(
            provider=supervisor.provider,
            model_id=supervisor.model_id,
            reasoning=supervisor.reasoning,
            workspace=workspace,
            sandbox_mode="read-only",
            approval_mode=project.approval_mode,
            approval_policy=project.approval_policy,
            approvals_reviewer=project.approvals_reviewer,
            agent_profile="plan" if supervisor.provider == "opencode" else None,
            prompt=prompt,
            label=supervisor.name,
            event_callback=event_callback,
            cancel_event=cancel_event,
        )
        plan = result.output
        storage.add_attempt(
            session_id=session.id,
            attempt_number=storage.next_attempt_number(session.id),
            agent_role=f"project:{supervisor.name}:plan",
            model=supervisor.model_id,
            prompt=prompt,
            output=plan,
            status="completed",
            run_state_id=state.id,
            provider=supervisor.provider,
        )
        outputs[f"{supervisor.name}:plan"] = plan

    previous = ""
    run_snapshot_before = _workspace_snapshot(workspace)
    verified_changes: list[str] = []
    for agent in workers:
        if cancel_event and cancel_event.is_set():
            raise AgentHubError("Project run was cancelled.")
        _emit(event_callback, "provider", f"project agent · {agent.name} · {agent.role}")
        storage.update_run_state(state.id, current_worker=agent.name)
        ctx = context_for_agent(storage, project.id, agent.name)
        prompt = f"""
You are JORE project agent `{agent.name}`.
Role: {agent.role}
Project: {project.name}
Workspace: {workspace}
The process working directory is already this workspace. Use relative paths (for example `src/app.js`, not `{workspace}/src/app.js`) whenever possible.
Isolation: {project.isolation_mode}. Never use context from another JORE project.
Permission profile: {project.approval_mode}
Sandbox intent: {project.sandbox_mode}
Read scope: {', '.join(agent.read_scope) if agent.read_scope else 'project workspace/context'}
Write scope: {', '.join(agent.write_scope) if agent.write_scope else 'project workspace only'}

SYSTEM INSTRUCTIONS:
{agent.system_instructions or '(none)'}

REGISTERED PROJECT CONTEXT:
{ctx or '(none)'}

SUPERVISOR PLAN:
{_clip(plan, 8000) if plan else '(no supervisor plan)'}

PREVIOUS TEAM OUTPUTS:
{_clip(previous, 9000) if previous else '(none yet)'}

USER GOAL:
{instruction}

Work autonomously on your part of the goal. Stay inside the project boundary unless the approved permission profile explicitly allows otherwise. Report what you changed, tested, or recommend for the next agent.
""".strip()
        result = _run_project_agent(
            provider=agent.provider,
            model_id=agent.model_id,
            reasoning=agent.reasoning,
            workspace=workspace,
            sandbox_mode=project.sandbox_mode,
            approval_mode=project.approval_mode,
            approval_policy=project.approval_policy,
            approvals_reviewer=project.approvals_reviewer,
            agent_profile="build" if agent.provider == "opencode" else None,
            prompt=prompt,
            label=agent.name,
            event_callback=event_callback,
            cancel_event=cancel_event,
        )
        outputs[agent.name] = result.output
        storage.add_attempt(
            session_id=session.id,
            attempt_number=storage.next_attempt_number(session.id),
            agent_role=f"project:{agent.name}",
            model=agent.model_id,
            prompt=prompt,
            output=result.output,
            status="completed",
            run_state_id=state.id,
            provider=agent.provider,
        )
        previous += f"\n\n## {agent.name} ({agent.role})\n{result.output}"
        current_snapshot = _workspace_snapshot(workspace)
        verified_changes = _workspace_changes(run_snapshot_before, current_snapshot)
        if verified_changes:
            _emit(
                event_callback,
                "success",
                f"workspace verified · {len(verified_changes)} changed file(s)",
            )
        else:
            _emit(
                event_callback,
                "warning",
                f"{agent.name} returned output but no workspace change was observed",
            )

    # A project implementation must never be marked complete solely from model
    # narration. If every worker returned prose but the filesystem is unchanged,
    # perform one deterministic recovery attempt with the first worker using the
    # explicit OpenCode build agent.
    if not verified_changes and workers:
        recovery = workers[0]
        _emit(event_callback, "warning", f"no workspace changes · retrying {recovery.name} in execution mode")
        recovery_ctx = context_for_agent(storage, project.id, recovery.name)
        recovery_prompt = f"""
You are JORE project agent `{recovery.name}` in RECOVERY EXECUTION MODE.
Role: {recovery.role}
Project root: {workspace}

The previous team responses claimed implementation work, but JORE verified that
ZERO project files changed. Do not merely describe what you would build. Use your
file tools now and actually create/edit the files required by the user's goal.
The current working directory is the project root. Use relative paths only.
After editing, inspect the created files and run lightweight local checks when
reasonable. Stay inside the project workspace.

PROJECT CONTEXT:
{recovery_ctx or '(none)'}

SUPERVISOR PLAN:
{_clip(plan, 8000) if plan else '(none)'}

USER GOAL:
{instruction}

Return a short execution report only AFTER the files have actually been changed.
""".strip()
        recovery_result = _run_project_agent(
            provider=recovery.provider,
            model_id=recovery.model_id,
            reasoning=recovery.reasoning,
            workspace=workspace,
            sandbox_mode=project.sandbox_mode,
            approval_mode=project.approval_mode,
            approval_policy=project.approval_policy,
            approvals_reviewer=project.approvals_reviewer,
            agent_profile="build" if recovery.provider == "opencode" else None,
            prompt=recovery_prompt,
            label=f"{recovery.name}-recovery",
            event_callback=event_callback,
            cancel_event=cancel_event,
        )
        outputs[f"{recovery.name}:recovery"] = recovery_result.output
        storage.add_attempt(
            session_id=session.id,
            attempt_number=storage.next_attempt_number(session.id),
            agent_role=f"project:{recovery.name}:recovery",
            model=recovery.model_id,
            prompt=recovery_prompt,
            output=recovery_result.output,
            status="completed",
            run_state_id=state.id,
            provider=recovery.provider,
        )
        previous += f"\n\n## {recovery.name} (recovery execution)\n{recovery_result.output}"
        verified_changes = _workspace_changes(run_snapshot_before, _workspace_snapshot(workspace))

    if not verified_changes:
        storage.update_run_state(
            state.id,
            status="failed",
            verdict="NEEDS_FIX",
            last_error="Provider returned implementation prose but JORE verified zero workspace changes.",
        )
        raise AgentHubError(
            "Project execution was not verified: providers returned implementation "
            "output, but no project files changed. JORE refused to report success."
        )

    _emit(event_callback, "success", f"verified workspace changes · {len(verified_changes)} file(s)")

    verdict = None
    review = None
    if reviewers:
        reviewer = reviewers[0]
        _emit(event_callback, "provider", f"project reviewer · {reviewer.name}")
        ctx = context_for_agent(storage, project.id, reviewer.name)
        review_prompt = f"""
You are `{reviewer.name}`, reviewer for JORE project {project.name}.
Review the team result against the original user goal and registered project context.
Do not use another project's context.

USER GOAL:
{instruction}

PROJECT CONTEXT:
{ctx or '(none)'}

VERIFIED WORKSPACE CHANGES (measured by JORE; do not trust claims that contradict this):
{_format_changes(verified_changes)}

TEAM OUTPUTS:
{_clip(previous, 18000)}

Inspect the actual workspace files relevant to the goal before deciding. Team prose is not proof of implementation.

Respond exactly with:
VERDICT: PASS or NEEDS_FIX
REVIEW: <concise explanation and concrete fixes if needed>
""".strip()
        result = _run_project_agent(
            provider=reviewer.provider,
            model_id=reviewer.model_id,
            reasoning=reviewer.reasoning,
            workspace=workspace,
            sandbox_mode="read-only",
            approval_mode=project.approval_mode,
            approval_policy=project.approval_policy,
            approvals_reviewer=project.approvals_reviewer,
            agent_profile="plan" if reviewer.provider == "opencode" else None,
            prompt=review_prompt,
            label=reviewer.name,
            event_callback=event_callback,
            cancel_event=cancel_event,
        )
        review = result.output
        upper = review.upper()
        verdict = "NEEDS_FIX" if "NEEDS_FIX" in upper else "PASS" if "PASS" in upper else None
        outputs[reviewer.name] = review
        storage.add_attempt(
            session_id=session.id,
            attempt_number=storage.next_attempt_number(session.id),
            agent_role=f"project:{reviewer.name}:review",
            model=reviewer.model_id,
            prompt=review_prompt,
            output=review,
            status="completed",
            run_state_id=state.id,
            provider=reviewer.provider,
        )
        storage.add_message(session.id, "reviewer", review)

    # Supervisor gives one final project-facing synthesis after the team has worked.
    if supervisors:
        supervisor = supervisors[0]
        _emit(event_callback, "provider", f"project supervisor · {supervisor.name} · finalizing")
        final_prompt = f"""
You are the Supervisor `{supervisor.name}` for JORE project {project.name}.
The team has completed an approved project run.

ORIGINAL USER GOAL:
{instruction}

VERIFIED WORKSPACE CHANGES:
{_format_changes(verified_changes)}

TEAM OUTPUTS:
{_clip(previous, 18000)}

REVIEW:
{_clip(review or '(no reviewer configured)', 6000)}

Give the user a concise final project report: what was done, files/areas affected, test/status, remaining issues, and the next recommended action. Treat VERIFIED WORKSPACE CHANGES as authoritative. Never claim a file was created or modified merely because another agent said so. Do not expose hidden chain-of-thought.
""".strip()
        result = _run_project_agent(
            provider=supervisor.provider,
            model_id=supervisor.model_id,
            reasoning=supervisor.reasoning,
            workspace=workspace,
            sandbox_mode="read-only",
            approval_mode=project.approval_mode,
            approval_policy=project.approval_policy,
            approvals_reviewer=project.approvals_reviewer,
            agent_profile="plan" if supervisor.provider == "opencode" else None,
            prompt=final_prompt,
            label=supervisor.name,
            event_callback=event_callback,
            cancel_event=cancel_event,
        )
        final_output = result.output
        outputs[f"{supervisor.name}:final"] = final_output
        storage.add_attempt(
            session_id=session.id,
            attempt_number=storage.next_attempt_number(session.id),
            agent_role=f"project:{supervisor.name}:final",
            model=supervisor.model_id,
            prompt=final_prompt,
            output=final_output,
            status="completed",
            run_state_id=state.id,
            provider=supervisor.provider,
        )
    else:
        final_output = review or (outputs.get(workers[-1].name) if workers else "Project run completed.")

    storage.add_message(session.id, "assistant", final_output)
    storage.update_session(session.id, last_verdict=verdict)
    storage.update_run_state(
        state.id,
        status="needs_fix" if verdict == "NEEDS_FIX" else "completed",
        verdict=verdict,
        reviewer_output=review or "",
        primary_output=final_output,
        current_worker=supervisors[0].name if supervisors else workers[-1].name,
    )
    return ProjectTurnResult(
        session_id=session.id,
        run_state_id=state.id,
        final_output=final_output,
        agent_outputs=outputs,
        verdict=verdict,
        review=review,
    )
