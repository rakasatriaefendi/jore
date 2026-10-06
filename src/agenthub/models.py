from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class SessionRecord:
    id: str
    title: str
    mode: str
    primary_model: str
    reviewer_model: Optional[str]
    codex_model: Optional[str]
    codex_reasoning: Optional[str]
    status: str
    created_at: str
    updated_at: str
    last_verdict: Optional[str] = None
    project_id: Optional[str] = None


@dataclass(slots=True)
class MessageRecord:
    id: int
    session_id: str
    role: str
    content: str
    created_at: str


@dataclass(slots=True)
class AttemptRecord:
    id: int
    session_id: str
    attempt_number: int
    agent_role: str
    model: str
    prompt: str
    output: str
    status: str
    error: Optional[str]
    created_at: str
    run_state_id: Optional[str] = None
    provider: Optional[str] = None
    failure_fingerprint: Optional[str] = None
    failure_category: Optional[str] = None
    http_status: Optional[int] = None
    consumes_retry: bool = True
    cooldown_until: Optional[str] = None


@dataclass(slots=True)
class RunStateRecord:
    id: str
    task_id: str
    session_id: str
    current_worker: str
    reviewer: Optional[str]
    attempt_no: int
    verdict: Optional[str]
    failure_fingerprint: Optional[str]
    retry_budget: int
    retries_used: int
    provider_cooldown: dict[str, str] = field(default_factory=dict)
    escalation_state: str = "none"
    handoff_packet: str = ""
    status: str = "running"
    original_instruction: str = ""
    primary_output: str = ""
    reviewer_output: str = ""
    last_error: Optional[str] = None
    loop_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    project_id: Optional[str] = None

    @property
    def retries_remaining(self) -> int:
        return max(0, self.retry_budget - self.retries_used)


@dataclass(slots=True)
class ProviderCooldownRecord:
    scope: str
    provider: str
    model: Optional[str]
    reason: str
    http_status: Optional[int]
    cooldown_until: str
    created_at: str
    updated_at: str
