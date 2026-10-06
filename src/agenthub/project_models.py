from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class ProjectRecord:
    id: str
    name: str
    slug: str
    workspace_path: str
    workspace_source: str
    isolation_mode: str
    approval_mode: str
    sandbox_mode: str
    approval_policy: str
    approvals_reviewer: str
    custom_permissions: dict[str, str] = field(default_factory=dict)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class ProjectAgentRecord:
    id: str
    project_id: str
    name: str
    role: str
    provider: str
    model_id: str
    reasoning: Optional[str]
    system_instructions: str
    read_scope: list[str] = field(default_factory=list)
    write_scope: list[str] = field(default_factory=list)
    handoff_scope: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class ProjectContextRecord:
    id: str
    project_id: str
    name: str
    kind: str
    source_path: Optional[str]
    stored_path: str
    content_hash: str
    agent_scope: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class ProjectApprovalRecord:
    id: str
    project_id: str
    session_id: Optional[str]
    action: str
    permission_mode: str
    decision: str
    details: str
    created_at: str
