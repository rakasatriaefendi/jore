from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from agenthub.codex_driver import CodexDriver
from agenthub.driver import (
    AgentResult,
    JOREError,
    CaoDriver,
    build_review_prompt,
    parse_review,
)
from agenthub.model_registry import ModelInfo, ModelRegistry
from agenthub.opencode_driver import OpenCodeDriver
from agenthub.resilience import (
    LoopDetectedError,
    ProviderCooldownError,
    classify_failure,
    cooldown_until,
    fingerprint_failure,
    fingerprint_review,
    is_loop_detected,
    provider_scope,
    remaining_seconds,
)
from agenthub.storage import Storage


EventCallback = Callable[[str, str], None]

AUTO_MODELS = {
    "nemotron": {
        "label": "Nemotron 3 Ultra Free",
        "profile": "nemotron-developer",
    },
    "mimo": {
        "label": "MiMo V2.6 Flash Free",
        "profile": "mimo-reviewer",
    },
}


@dataclass(slots=True)
class TurnResult:
    primary_output: str
    primary_label: str
    verdict: str | None = None
    review: str | None = None
    run_state_id: str | None = None
    failure_fingerprint: str | None = None
    loop_detected: bool = False
    retries_remaining: int | None = None


@dataclass(slots=True)
class CodexEscalationResult:
    mode: str
    output: str
    codex_label: str
    repair_prompt: str | None = None
    verdict: str | None = None
    review: str | None = None
    run_state_id: str | None = None
    loop_detected: bool = False


def _emit(callback: EventCallback | None, kind: str, message: str) -> None:
    if callback is not None and message:
        callback(kind, message)


def _setting_int(storage: Storage, key: str, default: int) -> int:
    try:
        return int(storage.get_setting(key, str(default)) or str(default))
    except (TypeError, ValueError):
        return default


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


def _codex_model_info(registry: ModelRegistry, model_id: str | None) -> ModelInfo | None:
    if not model_id:
        return None
    for model in registry.codex_models().models:
        if model.model_id == model_id:
            return model
    return None


def _normalize_codex_model(registry: ModelRegistry, model_id: str | None) -> str | None:
    catalog = registry.codex_models()
    if not catalog.models:
        return model_id
    if model_id and any(model.model_id == model_id for model in catalog.models):
        return model_id
    return catalog.models[0].model_id


def _model_label(storage_session) -> str:
    if storage_session.primary_model == "codex":
        return f"Codex · {storage_session.codex_model or 'default'}"
    if storage_session.primary_model.startswith("opencode:"):
        return "OpenCode · " + storage_session.primary_model.split(":", 1)[1]
    return AUTO_MODELS.get(
        storage_session.primary_model,
        {"label": storage_session.primary_model},
    )["label"]


def _clip(text: str, limit: int = 14000) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[truncated by JORE handoff packet]"


def _attempt_summary(storage: Storage, session_id: str, run_state_id: str | None = None) -> str:
    attempts = storage.get_attempts(session_id, run_state_id=run_state_id)[-10:]
    if not attempts:
        return "- none"
    rows = []
    for item in attempts:
        fingerprint = f" fp={item.failure_fingerprint}" if item.failure_fingerprint else ""
        rows.append(
            f"- #{item.attempt_number} role={item.agent_role} "
            f"model={item.model} status={item.status}{fingerprint}"
        )
    return "\n".join(rows)


def _run_state_or_latest(storage: Storage, session_id: str, run_state_id: str | None):
    if run_state_id:
        return storage.get_run_state(run_state_id)
    state = storage.get_latest_run_state(session_id, unresolved_only=True)
    if state is None:
        session = storage.get_session(session_id)
        state = storage.create_run_state(
            session_id=session_id,
            current_worker=session.primary_model,
            reviewer=session.reviewer_model,
            original_instruction="",
        )
    return state


def _sync_cooldowns(storage: Storage, run_state_id: str) -> None:
    storage.update_run_state(
        run_state_id,
        provider_cooldown=storage.cooldown_map(),
    )


def _cooldown_scope_for_auto(model_key: str) -> str:
    return provider_scope("opencode-auto", model_key)


def _record_provider_cooldown(
    *,
    storage: Storage,
    run_state_id: str,
    session_id: str,
    attempt_number: int,
    role: str,
    provider: str,
    model: str,
    prompt: str,
    error: str,
    event_callback: EventCallback | None,
) -> str | None:
    classification = classify_failure(error)
    if not classification.provider_transient or classification.cooldown_seconds <= 0:
        return None

    scope = provider_scope(provider, model)
    until = cooldown_until(classification.cooldown_seconds)
    storage.set_provider_cooldown(
        scope=scope,
        provider=provider,
        model=model,
        reason=classification.category,
        cooldown_until=until,
        http_status=classification.http_status,
    )
    fingerprint = fingerprint_failure(error, classification=classification, source="provider")
    storage.add_attempt(
        session_id=session_id,
        attempt_number=attempt_number,
        agent_role=f"{role}_provider_failure",
        model=model,
        prompt=prompt,
        output="",
        status="cooldown",
        error=error,
        run_state_id=run_state_id,
        provider=provider,
        failure_fingerprint=fingerprint,
        failure_category=classification.category,
        http_status=classification.http_status,
        consumes_retry=False,
        cooldown_until=until,
    )
    _sync_cooldowns(storage, run_state_id)
    storage.update_run_state(
        run_state_id,
        last_error=error,
        failure_fingerprint=fingerprint,
        status="cooldown",
    )
    _emit(
        event_callback,
        "warning",
        f"{model} cooling down · {classification.category} · {classification.cooldown_seconds}s · retry budget preserved",
    )
    return until


def _run_auto_agent(
    *,
    storage: Storage,
    runtime: CaoDriver,
    run_state_id: str,
    session_id: str,
    attempt_number: int,
    preferred_key: str,
    prompt: str,
    role: str,
    event_callback: EventCallback | None,
    cancel_event: Event | None,
) -> tuple[str, AgentResult]:
    candidates = [preferred_key] + [key for key in AUTO_MODELS if key != preferred_key]
    cooldown_waits: list[tuple[str, int]] = []

    for index, key in enumerate(candidates):
        spec = AUTO_MODELS[key]
        scope = _cooldown_scope_for_auto(key)
        existing = storage.get_provider_cooldown(scope)
        if existing is not None:
            remaining = remaining_seconds(existing.cooldown_until)
            cooldown_waits.append((spec["label"], remaining))
            _emit(event_callback, "warning", f"skip {spec['label']} · cooldown {remaining}s")
            continue

        if index > 0:
            _emit(event_callback, "provider", f"automatic fallback · {spec['label']}")

        try:
            result = runtime.run_agent(
                profile=spec["profile"],
                prompt=prompt,
                label=role,
                event_callback=event_callback,
                cancel_event=cancel_event,
            )
            storage.clear_provider_cooldown(scope)
            storage.update_run_state(run_state_id, current_worker=key if role == "primary" else storage.get_run_state(run_state_id).current_worker)
            _sync_cooldowns(storage, run_state_id)
            return key, result
        except Exception as exc:
            text = str(exc)
            classification = classify_failure(text)
            if classification.provider_transient and classification.cooldown_seconds > 0:
                until = cooldown_until(classification.cooldown_seconds)
                storage.set_provider_cooldown(
                    scope=scope,
                    provider="opencode-auto",
                    model=key,
                    reason=classification.category,
                    cooldown_until=until,
                    http_status=classification.http_status,
                )
                fingerprint = fingerprint_failure(text, classification=classification, source="provider")
                storage.add_attempt(
                    session_id=session_id,
                    attempt_number=attempt_number,
                    agent_role=f"{role}_provider_failure",
                    model=spec["label"],
                    prompt=prompt,
                    output="",
                    status="cooldown",
                    error=text,
                    run_state_id=run_state_id,
                    provider="opencode-auto",
                    failure_fingerprint=fingerprint,
                    failure_category=classification.category,
                    http_status=classification.http_status,
                    consumes_retry=False,
                    cooldown_until=until,
                )
                _sync_cooldowns(storage, run_state_id)
                _emit(
                    event_callback,
                    "warning",
                    f"{spec['label']} unavailable · {classification.category}; switching without consuming retry budget",
                )
                continue
            raise

    waits = ", ".join(f"{name} {seconds}s" for name, seconds in cooldown_waits) or "no alternate available"
    storage.update_run_state(run_state_id, status="cooldown", escalation_state="provider_wait")
    raise ProviderCooldownError(
        f"All free workers are cooling down ({waits}). Retry budget was not consumed.",
        scope="opencode-auto",
    )


def _quality_review_result(
    *,
    storage: Storage,
    run_state_id: str,
    session_id: str,
    attempt_number: int,
    reviewer_key: str,
    reviewer_label: str,
    review_prompt: str,
    raw_output: str,
    event_callback: EventCallback | None,
) -> tuple[str, str, str | None, bool, int]:
    parsed = parse_review(raw_output)
    fingerprint = fingerprint_review(parsed.review) if parsed.verdict == "NEEDS_FIX" else None
    storage.add_attempt(
        session_id=session_id,
        attempt_number=attempt_number,
        agent_role="reviewer",
        model=reviewer_label,
        prompt=review_prompt,
        output=raw_output,
        status=parsed.verdict,
        run_state_id=run_state_id,
        provider="opencode-auto",
        failure_fingerprint=fingerprint,
        failure_category="quality" if fingerprint else None,
        consumes_retry=True,
    )
    storage.add_message(session_id, "reviewer", raw_output)

    threshold = max(2, _setting_int(storage, "failure_loop_threshold", 2))
    loop = False
    loop_count = 0
    status = "completed" if parsed.verdict == "PASS" else "needs_fix"
    escalation_state = "none" if parsed.verdict == "PASS" else "available"
    if fingerprint:
        loop, loop_count = is_loop_detected(
            storage,
            run_state_id,
            fingerprint,
            threshold=threshold,
        )
        if loop:
            status = "loop_detected"
            escalation_state = "loop_detected"
            _emit(
                event_callback,
                "warning",
                f"failure loop detected · {fingerprint} · repeated {loop_count}x; free retry stopped",
            )

    storage.update_session(session_id, last_verdict=parsed.verdict, status="active")
    storage.update_run_state(
        run_state_id,
        reviewer=reviewer_key,
        verdict=parsed.verdict,
        reviewer_output=raw_output,
        failure_fingerprint=fingerprint,
        status=status,
        escalation_state=escalation_state,
        loop_count=loop_count,
    )
    _emit(event_callback, "review", f"verdict · {parsed.verdict}")
    state = storage.get_run_state(run_state_id)
    return parsed.verdict, parsed.review, fingerprint, loop, state.retries_remaining


def build_handoff_packet(
    *,
    storage: Storage,
    session_id: str,
    original_instruction: str,
    primary_output: str,
    reviewer_output: str,
    request_mode: str,
    run_state_id: str | None = None,
) -> str:
    session = storage.get_session(session_id)
    state = _run_state_or_latest(storage, session_id, run_state_id)
    cooldowns = storage.cooldown_map()
    packet = f"""
JORE HANDOFF PACKET

session:
  id: {session.id}
  mode: {session.mode}
  primary: {session.primary_model}
  reviewer: {session.reviewer_model or 'none'}
  last_verdict: {session.last_verdict or 'none'}

run_state:
  id: {state.id}
  task_id: {state.task_id}
  status: {state.status}
  current_worker: {state.current_worker}
  reviewer: {state.reviewer or 'none'}
  attempt_no: {state.attempt_no}
  retry_budget: {state.retry_budget}
  retries_used: {state.retries_used}
  retries_remaining: {state.retries_remaining}
  failure_fingerprint: {state.failure_fingerprint or 'none'}
  loop_count: {state.loop_count}
  escalation_state: {state.escalation_state}
  provider_cooldown: {cooldowns or {}}

request:
  mode: {request_mode}

original_task:
{_clip(original_instruction, 10000)}

primary_result:
{_clip(primary_output)}

reviewer_result:
{_clip(reviewer_output)}

recent_attempts:
{_attempt_summary(storage, session_id, state.id)}
""".strip()
    storage.update_run_state(state.id, handoff_packet=packet)
    return packet


def _extract_repair_prompt(output: str) -> str:
    text = (output or "").strip()
    marker = "REPAIR_PROMPT:"
    index = text.upper().find(marker)
    if index >= 0:
        value = text[index + len(marker):].strip()
        if value:
            return value
    return text


def execute_codex_escalation(
    *,
    storage: Storage,
    registry: ModelRegistry,
    session_id: str,
    original_instruction: str,
    primary_output: str,
    reviewer_output: str,
    mode: str,
    codex_model: str | None,
    reasoning: str,
    run_state_id: str | None = None,
    event_callback: EventCallback | None = None,
    cancel_event: Event | None = None,
    working_directory: Path | None = None,
) -> CodexEscalationResult:
    if mode not in {"diagnose", "prompt", "fix"}:
        raise JOREError(f"Unsupported Codex escalation mode: {mode}")

    working_directory = (working_directory or Path.cwd()).resolve()
    model = _normalize_codex_model(registry, codex_model)
    if not model:
        raise JOREError("No Codex model is available for escalation.")

    info = _codex_model_info(registry, model)
    if info and info.reasoning_levels and reasoning not in info.reasoning_levels:
        reasoning = info.default_reasoning or info.reasoning_levels[0]

    state = _run_state_or_latest(storage, session_id, run_state_id)
    storage.update_session(session_id, codex_model=model, codex_reasoning=reasoning)
    storage.update_run_state(state.id, escalation_state=f"codex_{mode}", status="escalating")

    packet = build_handoff_packet(
        storage=storage,
        session_id=session_id,
        original_instruction=original_instruction,
        primary_output=primary_output,
        reviewer_output=reviewer_output,
        request_mode=mode,
        run_state_id=state.id,
    )

    if mode == "diagnose":
        instruction = f"""
You are JORE's Codex supervisor.

Do not fix the task. Do not produce a replacement final answer. Do not modify files.
Analyze the supplied handoff packet and return only:

DIAGNOSIS:
ROOT_CAUSE:
REVIEWER_VALIDITY:
RECOMMENDED_ACTION:
REQUIRED_EVIDENCE:

Pay special attention to repeated failure fingerprints, exhausted retry budgets,
and provider cooldowns. Recommend escalation rather than repeating a loop.

{packet}
""".strip()
        sandbox, label = "read-only", "codex-diagnose"
    elif mode == "prompt":
        instruction = f"""
You are JORE's prompt supervisor.

Do not answer the user's task. Do not modify files.
Create a standalone repair prompt for a worker model. Address every reviewer finding,
avoid approaches represented by repeated failure fingerprints, and tell the worker
to return the corrected final result rather than orchestration commentary.

Return exactly:
REPAIR_PROMPT:
<standalone repair prompt>

{packet}
""".strip()
        sandbox, label = "read-only", "codex-prompt"
    else:
        instruction = f"""
You are JORE's remediation agent.

Take over the task and fix it using the handoff packet. Do not repeat approaches
recorded under the same failure fingerprint. Preserve unrelated work. For coding
tasks you may inspect files, edit the workspace, and run tests. For text/research
tasks return the corrected replacement answer. Address every reviewer finding.

Return the corrected result first, followed by a concise WHAT_CHANGED summary.

{packet}
""".strip()
        sandbox, label = "workspace-write", "codex-fix"

    scope = provider_scope("codex", model)
    cooldown = storage.get_provider_cooldown(scope)
    if cooldown:
        raise ProviderCooldownError(
            f"Codex {model} is cooling down for {remaining_seconds(cooldown.cooldown_until)}s.",
            scope=scope,
        )

    _emit(event_callback, "agent", f"Codex escalation · {mode}")
    attempt_number = storage.next_attempt_number(session_id)
    try:
        result = CodexDriver(working_directory).run_agent(
            prompt=instruction,
            model=model,
            reasoning=reasoning,
            sandbox=sandbox,
            label=label,
            event_callback=event_callback,
            cancel_event=cancel_event,
        )
    except Exception as exc:
        text = str(exc)
        until = _record_provider_cooldown(
            storage=storage,
            run_state_id=state.id,
            session_id=session_id,
            attempt_number=attempt_number,
            role=f"codex_{mode}",
            provider="codex",
            model=model,
            prompt=instruction,
            error=text,
            event_callback=event_callback,
        )
        if until:
            raise ProviderCooldownError(text, scope=scope) from exc
        classification = classify_failure(text)
        fingerprint = fingerprint_failure(text, classification=classification, source="codex")
        storage.add_attempt(
            session_id=session_id,
            attempt_number=attempt_number,
            agent_role=f"codex_{mode}",
            model=f"codex:{model}:{reasoning}",
            prompt=instruction,
            status="failed",
            error=text,
            run_state_id=state.id,
            provider="codex",
            failure_fingerprint=fingerprint,
            failure_category=classification.category,
            http_status=classification.http_status,
            consumes_retry=False,
        )
        storage.update_run_state(state.id, last_error=text, failure_fingerprint=fingerprint, status="needs_fix")
        raise

    storage.add_attempt(
        session_id=session_id,
        attempt_number=attempt_number,
        agent_role=f"codex_{mode}",
        model=f"codex:{model}:{reasoning}",
        prompt=instruction,
        output=result.output,
        status="completed",
        run_state_id=state.id,
        provider="codex",
        consumes_retry=False,
    )
    codex_label = f"Codex · {model}"

    if mode == "diagnose":
        storage.add_message(session_id, "system", f"Codex supervisor review\n\n{result.output}")
        storage.update_run_state(state.id, escalation_state="codex_diagnosed", status="needs_fix")
        return CodexEscalationResult(mode, result.output, codex_label, run_state_id=state.id)

    if mode == "prompt":
        repair_prompt = _extract_repair_prompt(result.output)
        storage.add_message(session_id, "system", f"Codex repair prompt\n\n{repair_prompt}")
        storage.update_run_state(state.id, escalation_state="codex_prompt_ready", status="needs_fix")
        return CodexEscalationResult(
            mode,
            result.output,
            codex_label,
            repair_prompt=repair_prompt,
            run_state_id=state.id,
        )

    # Codex fix is reviewed once more in Auto mode.
    storage.add_message(session_id, "assistant", result.output)
    storage.update_run_state(state.id, primary_output=result.output, current_worker=f"codex:{model}")
    session = storage.get_session(session_id)
    verdict = None
    review = None
    loop = False
    if session.mode == "auto" and session.reviewer_model in AUTO_MODELS:
        reviewer_key = session.reviewer_model
        reviewer = AUTO_MODELS[reviewer_key]
        review_prompt = build_review_prompt(original_instruction, result.output)
        _emit(event_callback, "review", f"final reviewer · {reviewer['label']}")
        with CaoDriver(working_directory) as runtime:
            actual_key, review_result = _run_auto_agent(
                storage=storage,
                runtime=runtime,
                run_state_id=state.id,
                session_id=session_id,
                attempt_number=attempt_number,
                preferred_key=reviewer_key,
                prompt=review_prompt,
                role="reviewer",
                event_callback=event_callback,
                cancel_event=cancel_event,
            )
        actual = AUTO_MODELS[actual_key]
        verdict, review, fingerprint, loop, _remaining = _quality_review_result(
            storage=storage,
            run_state_id=state.id,
            session_id=session_id,
            attempt_number=attempt_number,
            reviewer_key=actual_key,
            reviewer_label=actual["label"],
            review_prompt=review_prompt,
            raw_output=review_result.output,
            event_callback=event_callback,
        )
        storage.update_run_state(
            state.id,
            escalation_state="codex_fix_reviewed" if verdict == "NEEDS_FIX" else "codex_fix_complete",
        )
    else:
        storage.update_session(session_id, last_verdict=None, status="active")
        storage.update_run_state(state.id, status="completed", escalation_state="codex_fix_complete")

    return CodexEscalationResult(
        mode=mode,
        output=result.output,
        codex_label=codex_label,
        verdict=verdict,
        review=review,
        run_state_id=state.id,
        loop_detected=loop,
    )


def execute_repair_turn(
    *,
    storage: Storage,
    registry: ModelRegistry,
    session_id: str,
    original_instruction: str,
    repair_prompt: str,
    run_state_id: str | None = None,
    event_callback: EventCallback | None = None,
    cancel_event: Event | None = None,
    working_directory: Path | None = None,
) -> TurnResult:
    del registry  # Auto repair uses the free-worker registry defined here.
    working_directory = (working_directory or Path.cwd()).resolve()
    session = storage.get_session(session_id)
    if session.primary_model not in AUTO_MODELS:
        raise JOREError("Repair retry currently requires an Auto free-worker session.")

    state = _run_state_or_latest(storage, session_id, run_state_id)
    if state.status == "loop_detected" or state.escalation_state == "loop_detected":
        raise LoopDetectedError(
            f"Repeated failure fingerprint {state.failure_fingerprint or 'unknown'} detected. Use Codex escalation or stop."
        )
    if state.retries_remaining <= 0:
        storage.update_run_state(state.id, escalation_state="retry_budget_exhausted", status="needs_fix")
        raise LoopDetectedError("JORE retry budget is exhausted. Use Codex escalation or stop.")

    attempt_number = storage.next_attempt_number(session_id)
    storage.update_run_state(
        state.id,
        current_worker=session.primary_model,
        reviewer=session.reviewer_model,
        attempt_no=attempt_number,
        status="running",
        escalation_state="none",
    )
    execution_prompt = f"""
You are retrying a failed JORE task.

ORIGINAL USER TASK:
{original_instruction.strip()}

REPAIR INSTRUCTIONS:
{repair_prompt.strip()}

Produce the corrected final result only. Address all repair instructions. Do not
explain the orchestration process or mention that you are retrying unless required.
""".strip()

    _emit(event_callback, "agent", f"repair worker · {AUTO_MODELS[session.primary_model]['label']}")
    try:
        with CaoDriver(working_directory) as runtime:
            primary_key, result = _run_auto_agent(
                storage=storage,
                runtime=runtime,
                run_state_id=state.id,
                session_id=session_id,
                attempt_number=attempt_number,
                preferred_key=session.primary_model,
                prompt=execution_prompt,
                role="primary",
                event_callback=event_callback,
                cancel_event=cancel_event,
            )
            primary = AUTO_MODELS[primary_key]
            storage.add_attempt(
                session_id=session_id,
                attempt_number=attempt_number,
                agent_role="repair_primary",
                model=primary["label"],
                prompt=execution_prompt,
                output=result.output,
                status="completed",
                run_state_id=state.id,
                provider="opencode-auto",
                consumes_retry=True,
            )
            storage.add_message(session_id, "assistant", result.output)
            storage.update_run_state(state.id, primary_output=result.output, current_worker=primary_key)

            reviewer_key = session.reviewer_model
            if reviewer_key not in AUTO_MODELS:
                state = storage.consume_retry(state.id)
                storage.update_session(session_id, last_verdict=None, status="active")
                storage.update_run_state(state.id, status="completed", verdict=None)
                return TurnResult(
                    result.output,
                    primary["label"],
                    run_state_id=state.id,
                    retries_remaining=state.retries_remaining,
                )

            reviewer = AUTO_MODELS[reviewer_key]
            _emit(event_callback, "review", f"reviewer · {reviewer['label']}")
            review_prompt = build_review_prompt(original_instruction, result.output)
            actual_reviewer_key, review_result = _run_auto_agent(
                storage=storage,
                runtime=runtime,
                run_state_id=state.id,
                session_id=session_id,
                attempt_number=attempt_number,
                preferred_key=reviewer_key,
                prompt=review_prompt,
                role="reviewer",
                event_callback=event_callback,
                cancel_event=cancel_event,
            )
            # A logical repair attempt is consumed only after provider execution
            # reaches a real quality verdict. Provider cooldowns do not consume it.
            state = storage.consume_retry(state.id)
            actual_reviewer = AUTO_MODELS[actual_reviewer_key]
            verdict, review, fingerprint, loop, remaining = _quality_review_result(
                storage=storage,
                run_state_id=state.id,
                session_id=session_id,
                attempt_number=attempt_number,
                reviewer_key=actual_reviewer_key,
                reviewer_label=actual_reviewer["label"],
                review_prompt=review_prompt,
                raw_output=review_result.output,
                event_callback=event_callback,
            )
            return TurnResult(
                primary_output=result.output,
                primary_label=primary["label"],
                verdict=verdict,
                review=review,
                run_state_id=state.id,
                failure_fingerprint=fingerprint,
                loop_detected=loop,
                retries_remaining=remaining,
            )
    except ProviderCooldownError:
        # Provider/cooldown conditions intentionally do not consume the logical
        # retry budget.
        raise
    except Exception as exc:
        classification = classify_failure(str(exc))
        fingerprint = fingerprint_failure(str(exc), classification=classification, source="repair")
        if classification.consumes_retry:
            state = storage.consume_retry(state.id)
        storage.add_attempt(
            session_id=session_id,
            attempt_number=attempt_number,
            agent_role="repair_failure",
            model=_model_label(session),
            prompt=execution_prompt,
            status="failed",
            error=str(exc),
            run_state_id=state.id,
            provider="opencode-auto",
            failure_fingerprint=fingerprint,
            failure_category=classification.category,
            http_status=classification.http_status,
            consumes_retry=classification.consumes_retry,
        )
        threshold = max(2, _setting_int(storage, "failure_loop_threshold", 2))
        repeated, loop_count = is_loop_detected(
            storage,
            state.id,
            fingerprint,
            threshold=threshold,
        )
        storage.update_run_state(
            state.id,
            failure_fingerprint=fingerprint,
            last_error=str(exc),
            status="loop_detected" if repeated else "needs_fix",
            escalation_state="loop_detected" if repeated else "available",
            loop_count=loop_count,
        )
        if repeated:
            _emit(
                event_callback,
                "warning",
                f"failure loop detected · {fingerprint} · repeated {loop_count}x",
            )
            raise LoopDetectedError(
                f"Repeated failure {fingerprint} detected. Free retries stopped; use Codex escalation or stop."
            ) from exc
        raise


def execute_turn(
    *,
    storage: Storage,
    registry: ModelRegistry,
    session_id: str,
    instruction: str,
    event_callback: EventCallback | None = None,
    cancel_event: Event | None = None,
    background: bool = False,
    working_directory: Path | None = None,
) -> TurnResult:
    """Execute one persisted logical JORE run."""
    working_directory = (working_directory or Path.cwd()).resolve()
    session = storage.get_session(session_id)
    prompt = _build_prompt(storage, session_id, instruction)

    if not background:
        storage.ensure_title_from_first_prompt(session_id, instruction)
        storage.add_message(session_id, "user", instruction)

    attempt_number = storage.next_attempt_number(session_id)
    role = "background" if background else "primary"
    state = storage.create_run_state(
        session_id=session_id,
        current_worker=session.primary_model,
        reviewer=session.reviewer_model,
        original_instruction=instruction,
        retry_budget=max(0, _setting_int(storage, "retry_budget", 3)),
    )
    storage.update_run_state(state.id, attempt_no=attempt_number)

    _emit(event_callback, "queued", instruction[:120])
    _emit(event_callback, "context", f"RunState {state.task_id} · retry budget {state.retry_budget}")

    try:
        if session.primary_model == "codex":
            model = _normalize_codex_model(registry, session.codex_model)
            if not model:
                raise JOREError("No Codex model is available. Open /models first.")
            reasoning = session.codex_reasoning or "medium"
            info = _codex_model_info(registry, model)
            if info and info.reasoning_levels and reasoning not in info.reasoning_levels:
                reasoning = info.default_reasoning or info.reasoning_levels[0]
            if session.codex_model != model or session.codex_reasoning != reasoning:
                storage.update_session(session_id, codex_model=model, codex_reasoning=reasoning)

            scope = provider_scope("codex", model)
            existing = storage.get_provider_cooldown(scope)
            if existing:
                raise ProviderCooldownError(
                    f"Codex {model} is cooling down for {remaining_seconds(existing.cooldown_until)}s.",
                    scope=scope,
                )
            _emit(event_callback, "provider", f"Codex · {model} · effort {reasoning}")
            result = CodexDriver(working_directory).run_agent(
                prompt=prompt,
                model=model,
                reasoning=reasoning,
                sandbox="read-only",
                label="codex",
                event_callback=event_callback,
                cancel_event=cancel_event,
            )
            storage.add_attempt(
                session_id=session_id,
                attempt_number=attempt_number,
                agent_role=role,
                model=f"codex:{model}:{reasoning}",
                prompt=prompt,
                output=result.output,
                status="completed",
                run_state_id=state.id,
                provider="codex",
                consumes_retry=True,
            )
            if not background:
                storage.add_message(session_id, "assistant", result.output)
                storage.update_session(session_id, last_verdict=None, status="active")
            storage.update_run_state(state.id, current_worker=f"codex:{model}", primary_output=result.output, status="completed")
            return TurnResult(result.output, f"Codex · {model}", run_state_id=state.id, retries_remaining=state.retries_remaining)

        if session.primary_model.startswith("opencode:"):
            model = session.primary_model.split(":", 1)[1]
            scope = provider_scope("opencode", model)
            existing = storage.get_provider_cooldown(scope)
            if existing:
                raise ProviderCooldownError(
                    f"OpenCode {model} is cooling down for {remaining_seconds(existing.cooldown_until)}s.",
                    scope=scope,
                )
            _emit(event_callback, "provider", f"OpenCode · {model}")
            result = OpenCodeDriver(working_directory).run_agent(
                prompt=prompt,
                model=model,
                label="opencode",
                event_callback=event_callback,
                cancel_event=cancel_event,
            )
            storage.add_attempt(
                session_id=session_id,
                attempt_number=attempt_number,
                agent_role=role,
                model=f"opencode:{model}",
                prompt=prompt,
                output=result.output,
                status="completed",
                run_state_id=state.id,
                provider="opencode",
                consumes_retry=True,
            )
            if not background:
                storage.add_message(session_id, "assistant", result.output)
                storage.update_session(session_id, last_verdict=None, status="active")
            storage.update_run_state(state.id, current_worker=f"opencode:{model}", primary_output=result.output, status="completed")
            return TurnResult(result.output, f"OpenCode · {model}", run_state_id=state.id, retries_remaining=state.retries_remaining)

        if session.primary_model not in AUTO_MODELS:
            raise JOREError(f"Unknown JORE primary model: {session.primary_model}")

        with CaoDriver(working_directory) as runtime:
            primary_key, result = _run_auto_agent(
                storage=storage,
                runtime=runtime,
                run_state_id=state.id,
                session_id=session_id,
                attempt_number=attempt_number,
                preferred_key=session.primary_model,
                prompt=prompt,
                role="primary",
                event_callback=event_callback,
                cancel_event=cancel_event,
            )
            primary = AUTO_MODELS[primary_key]
            storage.add_attempt(
                session_id=session_id,
                attempt_number=attempt_number,
                agent_role=role,
                model=primary["label"],
                prompt=prompt,
                output=result.output,
                status="completed",
                run_state_id=state.id,
                provider="opencode-auto",
                consumes_retry=True,
            )
            storage.update_run_state(state.id, current_worker=primary_key, primary_output=result.output)

            if background:
                storage.update_run_state(state.id, status="completed")
                return TurnResult(result.output, primary["label"], run_state_id=state.id, retries_remaining=state.retries_remaining)

            storage.add_message(session_id, "assistant", result.output)
            auto_review = (
                session.mode == "auto"
                and session.reviewer_model
                and storage.get_setting("automatic_review", "true") == "true"
            )
            if not auto_review:
                storage.update_session(session_id, last_verdict=None, status="active")
                storage.update_run_state(state.id, status="completed")
                return TurnResult(result.output, primary["label"], run_state_id=state.id, retries_remaining=state.retries_remaining)

            reviewer_key = session.reviewer_model
            if reviewer_key not in AUTO_MODELS:
                raise JOREError(f"Unknown reviewer model: {reviewer_key}")
            reviewer = AUTO_MODELS[reviewer_key]
            _emit(event_callback, "review", f"reviewer · {reviewer['label']}")
            review_prompt = build_review_prompt(instruction, result.output)
            actual_reviewer_key, review_result = _run_auto_agent(
                storage=storage,
                runtime=runtime,
                run_state_id=state.id,
                session_id=session_id,
                attempt_number=attempt_number,
                preferred_key=reviewer_key,
                prompt=review_prompt,
                role="reviewer",
                event_callback=event_callback,
                cancel_event=cancel_event,
            )
            actual_reviewer = AUTO_MODELS[actual_reviewer_key]
            verdict, review, fingerprint, loop, remaining = _quality_review_result(
                storage=storage,
                run_state_id=state.id,
                session_id=session_id,
                attempt_number=attempt_number,
                reviewer_key=actual_reviewer_key,
                reviewer_label=actual_reviewer["label"],
                review_prompt=review_prompt,
                raw_output=review_result.output,
                event_callback=event_callback,
            )
            return TurnResult(
                result.output,
                primary["label"],
                verdict=verdict,
                review=review,
                run_state_id=state.id,
                failure_fingerprint=fingerprint,
                loop_detected=loop,
                retries_remaining=remaining,
            )

    except ProviderCooldownError as exc:
        storage.update_run_state(
            state.id,
            provider_cooldown=storage.cooldown_map(),
            status="cooldown",
            last_error=str(exc),
        )
        if not background:
            storage.update_session(session_id, status="active")
        _emit(event_callback, "warning", str(exc))
        raise
    except Exception as exc:
        status = "cancelled" if cancel_event is not None and cancel_event.is_set() else "failed"
        classification = classify_failure(str(exc))
        fingerprint = fingerprint_failure(str(exc), classification=classification, source="runtime")
        provider = "codex" if session.primary_model == "codex" else "opencode" if session.primary_model.startswith("opencode:") else "opencode-auto"
        model = session.codex_model if session.primary_model == "codex" else session.primary_model.split(":", 1)[1] if session.primary_model.startswith("opencode:") else session.primary_model

        cooldown_value = None
        if status != "cancelled" and classification.provider_transient and classification.cooldown_seconds > 0:
            scope = provider_scope(provider, model)
            cooldown_value = cooldown_until(classification.cooldown_seconds)
            storage.set_provider_cooldown(
                scope=scope,
                provider=provider,
                model=model,
                reason=classification.category,
                cooldown_until=cooldown_value,
                http_status=classification.http_status,
            )
            _sync_cooldowns(storage, state.id)
            status = "cooldown"

        storage.add_attempt(
            session_id=session_id,
            attempt_number=attempt_number,
            agent_role=role,
            model=_model_label(session),
            prompt=prompt,
            output="",
            status=status,
            error=str(exc),
            run_state_id=state.id,
            provider=provider,
            failure_fingerprint=fingerprint,
            failure_category=classification.category,
            http_status=classification.http_status,
            consumes_retry=classification.consumes_retry,
            cooldown_until=cooldown_value,
        )
        storage.update_run_state(
            state.id,
            failure_fingerprint=fingerprint,
            last_error=str(exc),
            status="cooldown" if cooldown_value else status,
            provider_cooldown=storage.cooldown_map(),
        )
        if not background:
            storage.update_session(session_id, status="active" if cooldown_value or status == "cancelled" else "failed")

        # Across separate user retries in the same session, the same stable
        # technical failure should also stop blind repetition. On the threshold
        # hit, promote it into the same NEEDS_FIX escalation path used by the
        # reviewer so Codex Diagnose/Prompt/Fix becomes immediately available.
        threshold = max(2, _setting_int(storage, "failure_loop_threshold", 2))
        session_repeat_count = storage.count_session_failure_fingerprint(
            session_id,
            fingerprint,
        )
        repeated = (
            status == "failed"
            and session_repeat_count >= threshold
            and not background
        )
        if repeated:
            storage.update_session(session_id, status="active", last_verdict="NEEDS_FIX")
            storage.update_run_state(
                state.id,
                status="loop_detected",
                escalation_state="loop_detected",
                verdict="NEEDS_FIX",
                loop_count=session_repeat_count,
            )
            review = (
                f"Repeated technical failure detected: {fingerprint}. "
                f"The same failure occurred {session_repeat_count} times. "
                f"Last error: {exc}"
            )
            storage.add_message(session_id, "reviewer", "VERDICT: NEEDS_FIX\nREVIEW:\n" + review)
            _emit(event_callback, "warning", f"loop guard · {fingerprint} · {session_repeat_count}x")
            return TurnResult(
                primary_output="",
                primary_label=_model_label(session),
                verdict="NEEDS_FIX",
                review=review,
                run_state_id=state.id,
                failure_fingerprint=fingerprint,
                loop_detected=True,
                retries_remaining=state.retries_remaining,
            )

        _emit(event_callback, "warning" if status in {"cancelled", "cooldown"} else "error", str(exc))
        raise
