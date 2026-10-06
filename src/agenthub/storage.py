from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from agenthub.project_models import (
    ProjectRecord, ProjectAgentRecord, ProjectContextRecord, ProjectApprovalRecord,
)

from agenthub.models import (
    AttemptRecord,
    MessageRecord,
    ProviderCooldownRecord,
    RunStateRecord,
    SessionRecord,
)


DATA_DIR = Path.home() / ".local" / "share" / "agenthub"
DB_PATH = DATA_DIR / "agenthub.db"
EXPORT_DIR = DATA_DIR / "exports"

SCHEMA_VERSION = 3

DEFAULT_SETTINGS = {
    "default_mode": "auto",
    "default_free_model": "nemotron",
    "reviewer_model": "mimo",
    "automatic_review": "true",
    "opencode_default_model": "",
    "codex_default_model": "",
    "codex_default_reasoning": "medium",
    "theme": "jore",
    "busy_input_mode": "queue",
    "tui_enabled": "true",
    "retry_budget": "3",
    "failure_loop_threshold": "2",
    "cooldown_429_seconds": "120",
    "cooldown_5xx_seconds": "60",
    "cooldown_timeout_seconds": "45",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dict(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def _row_to_session(row: sqlite3.Row) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        title=row["title"],
        mode=row["mode"],
        primary_model=row["primary_model"],
        reviewer_model=row["reviewer_model"],
        codex_model=row["codex_model"],
        codex_reasoning=row["codex_reasoning"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_verdict=row["last_verdict"],
        project_id=row["project_id"] if "project_id" in row.keys() else None,
    )


def _row_to_run_state(row: sqlite3.Row) -> RunStateRecord:
    return RunStateRecord(
        id=row["id"],
        task_id=row["task_id"],
        session_id=row["session_id"],
        current_worker=row["current_worker"],
        reviewer=row["reviewer"],
        attempt_no=int(row["attempt_no"] or 0),
        verdict=row["verdict"],
        failure_fingerprint=row["failure_fingerprint"],
        retry_budget=int(row["retry_budget"] or 0),
        retries_used=int(row["retries_used"] or 0),
        provider_cooldown=_json_dict(row["provider_cooldown"]),
        escalation_state=row["escalation_state"] or "none",
        handoff_packet=row["handoff_packet"] or "",
        status=row["status"] or "running",
        original_instruction=row["original_instruction"] or "",
        primary_output=row["primary_output"] or "",
        reviewer_output=row["reviewer_output"] or "",
        last_error=row["last_error"],
        loop_count=int(row["loop_count"] or 0),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        project_id=row["project_id"] if "project_id" in row.keys() else None,
    )


class Storage:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        table: str,
        column: str,
        declaration: str,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    primary_model TEXT NOT NULL,
                    reviewer_model TEXT,
                    codex_model TEXT,
                    codex_reasoning TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    last_verdict TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_created
                    ON messages(session_id, id);

                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    agent_role TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    output TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    error TEXT,
                    run_state_id TEXT,
                    provider TEXT,
                    failure_fingerprint TEXT,
                    failure_category TEXT,
                    http_status INTEGER,
                    consumes_retry INTEGER NOT NULL DEFAULT 1,
                    cooldown_until TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_attempts_session_created
                    ON attempts(session_id, id);
                CREATE TABLE IF NOT EXISTS run_states (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    current_worker TEXT NOT NULL,
                    reviewer TEXT,
                    attempt_no INTEGER NOT NULL DEFAULT 0,
                    verdict TEXT,
                    failure_fingerprint TEXT,
                    retry_budget INTEGER NOT NULL DEFAULT 3,
                    retries_used INTEGER NOT NULL DEFAULT 0,
                    provider_cooldown TEXT NOT NULL DEFAULT '{}',
                    escalation_state TEXT NOT NULL DEFAULT 'none',
                    handoff_packet TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'running',
                    original_instruction TEXT NOT NULL DEFAULT '',
                    primary_output TEXT NOT NULL DEFAULT '',
                    reviewer_output TEXT NOT NULL DEFAULT '',
                    last_error TEXT,
                    loop_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_run_states_session_updated
                    ON run_states(session_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS provider_cooldowns (
                    scope TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT,
                    reason TEXT NOT NULL,
                    http_status INTEGER,
                    cooldown_until TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_provider_cooldowns_until
                    ON provider_cooldowns(cooldown_until);

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    attempt_id INTEGER,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY(attempt_id) REFERENCES attempts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    workspace_path TEXT NOT NULL,
                    workspace_source TEXT NOT NULL DEFAULT 'external',
                    isolation_mode TEXT NOT NULL DEFAULT 'strict-context',
                    approval_mode TEXT NOT NULL DEFAULT 'ask',
                    sandbox_mode TEXT NOT NULL DEFAULT 'workspace-write',
                    approval_policy TEXT NOT NULL DEFAULT 'on-request',
                    approvals_reviewer TEXT NOT NULL DEFAULT 'user',
                    custom_permissions TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS project_agents (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    reasoning TEXT,
                    system_instructions TEXT NOT NULL DEFAULT '',
                    read_scope TEXT NOT NULL DEFAULT '[]',
                    write_scope TEXT NOT NULL DEFAULT '[]',
                    handoff_scope TEXT NOT NULL DEFAULT '[]',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id, name),
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_project_agents_project
                    ON project_agents(project_id, name);

                CREATE TABLE IF NOT EXISTS project_context (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'document',
                    source_path TEXT,
                    stored_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    agent_scope TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_project_context_project
                    ON project_context(project_id, name);

                CREATE TABLE IF NOT EXISTS project_approvals (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    session_id TEXT,
                    action TEXT NOT NULL,
                    permission_mode TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_project_approvals_project
                    ON project_approvals(project_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            # Upgrade v1 databases in-place. SQLite CREATE TABLE IF NOT EXISTS
            # does not add new columns to an existing attempts table.
            self._ensure_column(conn, "sessions", "project_id", "TEXT")
            self._ensure_column(conn, "run_states", "project_id", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_project_updated ON sessions(project_id, updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_states_project_updated ON run_states(project_id, updated_at DESC)")

            for column, declaration in (
                ("run_state_id", "TEXT"),
                ("provider", "TEXT"),
                ("failure_fingerprint", "TEXT"),
                ("failure_category", "TEXT"),
                ("http_status", "INTEGER"),
                ("consumes_retry", "INTEGER NOT NULL DEFAULT 1"),
                ("cooldown_until", "TEXT"),
            ):
                self._ensure_column(conn, "attempts", column, declaration)

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attempts_run_state ON attempts(run_state_id, id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attempts_fingerprint ON attempts(run_state_id, failure_fingerprint)"
            )
            conn.execute(
                """
                INSERT INTO schema_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(SCHEMA_VERSION),),
            )
            now = _utc_now()
            for key, value in DEFAULT_SETTINGS.items():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO settings(key, value, updated_at)
                    VALUES(?, ?, ?)
                    """,
                    (key, value, now),
                )

    def create_session(
        self,
        *,
        mode: str,
        primary_model: str,
        reviewer_model: str | None = None,
        codex_model: str | None = None,
        codex_reasoning: str | None = None,
        title: str = "Untitled session",
        project_id: str | None = None,
    ) -> SessionRecord:
        session_id = uuid.uuid4().hex
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(
                    id, title, mode, primary_model, reviewer_model,
                    codex_model, codex_reasoning, status, project_id,
                    created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    session_id,
                    title,
                    mode,
                    primary_model,
                    reviewer_model,
                    codex_model,
                    codex_reasoning,
                    project_id,
                    now,
                    now,
                ),
            )
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> SessionRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Session not found: {session_id}")
        return _row_to_session(row)

    def update_session(self, session_id: str, **fields: object) -> SessionRecord:
        allowed = {
            "title",
            "mode",
            "primary_model",
            "reviewer_model",
            "codex_model",
            "codex_reasoning",
            "status",
            "last_verdict",
        }
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return self.get_session(session_id)
        clean["updated_at"] = _utc_now()
        assignments = ", ".join(f"{key} = ?" for key in clean)
        values = list(clean.values()) + [session_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE sessions SET {assignments} WHERE id = ?", values)
        return self.get_session(session_id)

    def list_sessions(
        self,
        limit: int = 20,
        *,
        project_id: str | None = None,
        include_project_sessions: bool = False,
    ) -> list[SessionRecord]:
        with self._connect() as conn:
            if project_id is not None:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE project_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (project_id, limit),
                ).fetchall()
            elif include_project_sessions:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                # Global/quick-chat history must not silently surface a project
                # session. Project sessions are resumed from their own boundary.
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE project_id IS NULL ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [_row_to_session(row) for row in rows]

    def delete_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def add_message(self, session_id: str, role: str, content: str) -> int:
        now = _utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES(?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            return int(cur.lastrowid)

    def get_messages(self, session_id: str, *, limit: int | None = None) -> list[MessageRecord]:
        query = "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC"
        params: list[object] = [session_id]
        if limit is not None:
            query = """
                SELECT * FROM (
                    SELECT * FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
            """
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            MessageRecord(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def next_attempt_number(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(attempt_number), 0) + 1 AS next_num FROM attempts WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row["next_num"])

    def add_attempt(
        self,
        *,
        session_id: str,
        attempt_number: int,
        agent_role: str,
        model: str,
        prompt: str,
        output: str = "",
        status: str,
        error: str | None = None,
        run_state_id: str | None = None,
        provider: str | None = None,
        failure_fingerprint: str | None = None,
        failure_category: str | None = None,
        http_status: int | None = None,
        consumes_retry: bool = True,
        cooldown_until: str | None = None,
    ) -> int:
        now = _utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO attempts(
                    session_id, attempt_number, agent_role, model,
                    prompt, output, status, error, run_state_id, provider,
                    failure_fingerprint, failure_category, http_status,
                    consumes_retry, cooldown_until, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    attempt_number,
                    agent_role,
                    model,
                    prompt,
                    output,
                    status,
                    error,
                    run_state_id,
                    provider,
                    failure_fingerprint,
                    failure_category,
                    http_status,
                    1 if consumes_retry else 0,
                    cooldown_until,
                    now,
                ),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            return int(cur.lastrowid)

    def get_attempts(
        self,
        session_id: str,
        *,
        run_state_id: str | None = None,
    ) -> list[AttemptRecord]:
        query = "SELECT * FROM attempts WHERE session_id = ?"
        params: list[object] = [session_id]
        if run_state_id:
            query += " AND run_state_id = ?"
            params.append(run_state_id)
        query += " ORDER BY id ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            AttemptRecord(
                id=row["id"],
                session_id=row["session_id"],
                attempt_number=row["attempt_number"],
                agent_role=row["agent_role"],
                model=row["model"],
                prompt=row["prompt"],
                output=row["output"],
                status=row["status"],
                error=row["error"],
                created_at=row["created_at"],
                run_state_id=row["run_state_id"],
                provider=row["provider"],
                failure_fingerprint=row["failure_fingerprint"],
                failure_category=row["failure_category"],
                http_status=row["http_status"],
                consumes_retry=bool(row["consumes_retry"]),
                cooldown_until=row["cooldown_until"],
            )
            for row in rows
        ]

    def count_failure_fingerprint(self, run_state_id: str, fingerprint: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM attempts
                WHERE run_state_id = ? AND failure_fingerprint = ?
                """,
                (run_state_id, fingerprint),
            ).fetchone()
        return int(row["n"] or 0)

    def count_session_failure_fingerprint(self, session_id: str, fingerprint: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM attempts
                WHERE session_id = ? AND failure_fingerprint = ?
                """,
                (session_id, fingerprint),
            ).fetchone()
        return int(row["n"] or 0)

    # ---------- persisted RunState ----------

    def create_run_state(
        self,
        *,
        session_id: str,
        current_worker: str,
        reviewer: str | None,
        original_instruction: str,
        retry_budget: int | None = None,
        task_id: str | None = None,
        project_id: str | None = None,
    ) -> RunStateRecord:
        run_id = uuid.uuid4().hex
        task_id = task_id or f"task-{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        if retry_budget is None:
            try:
                retry_budget = int(self.get_setting("retry_budget", "3") or "3")
            except ValueError:
                retry_budget = 3
        retry_budget = max(0, retry_budget)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_states(
                    id, task_id, session_id, current_worker, reviewer,
                    attempt_no, retry_budget, retries_used, provider_cooldown,
                    escalation_state, handoff_packet, status,
                    original_instruction, project_id, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, 0, ?, 0, '{}', 'none', '', 'running', ?, ?, ?, ?)
                """,
                (
                    run_id,
                    task_id,
                    session_id,
                    current_worker,
                    reviewer,
                    retry_budget,
                    original_instruction,
                    project_id,
                    now,
                    now,
                ),
            )
        return self.get_run_state(run_id)

    def get_run_state(self, run_state_id: str) -> RunStateRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM run_states WHERE id = ?",
                (run_state_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"RunState not found: {run_state_id}")
        return _row_to_run_state(row)

    def get_latest_run_state(
        self,
        session_id: str,
        *,
        unresolved_only: bool = False,
    ) -> RunStateRecord | None:
        query = "SELECT * FROM run_states WHERE session_id = ?"
        params: list[object] = [session_id]
        if unresolved_only:
            query += " AND status IN ('running', 'needs_fix', 'cooldown', 'loop_detected', 'escalating')"
        query += " ORDER BY rowid DESC LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return _row_to_run_state(row) if row else None

    def list_run_states(self, session_id: str, limit: int = 20) -> list[RunStateRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM run_states WHERE session_id = ? ORDER BY rowid DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [_row_to_run_state(row) for row in rows]

    def update_run_state(self, run_state_id: str, **fields: object) -> RunStateRecord:
        allowed = {
            "task_id",
            "current_worker",
            "reviewer",
            "attempt_no",
            "verdict",
            "failure_fingerprint",
            "retry_budget",
            "retries_used",
            "provider_cooldown",
            "escalation_state",
            "handoff_packet",
            "status",
            "original_instruction",
            "primary_output",
            "reviewer_output",
            "last_error",
            "loop_count",
            "project_id",
        }
        clean = {k: v for k, v in fields.items() if k in allowed}
        if "provider_cooldown" in clean and isinstance(clean["provider_cooldown"], dict):
            clean["provider_cooldown"] = json.dumps(clean["provider_cooldown"], sort_keys=True)
        if not clean:
            return self.get_run_state(run_state_id)
        clean["updated_at"] = _utc_now()
        assignments = ", ".join(f"{key} = ?" for key in clean)
        values = list(clean.values()) + [run_state_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE run_states SET {assignments} WHERE id = ?", values)
        return self.get_run_state(run_state_id)

    def consume_retry(self, run_state_id: str) -> RunStateRecord:
        state = self.get_run_state(run_state_id)
        if state.retries_used >= state.retry_budget:
            return state
        return self.update_run_state(
            run_state_id,
            retries_used=state.retries_used + 1,
        )

    # ---------- provider/model cooldowns ----------

    def set_provider_cooldown(
        self,
        *,
        scope: str,
        provider: str,
        model: str | None,
        reason: str,
        cooldown_until: str,
        http_status: int | None = None,
    ) -> ProviderCooldownRecord:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO provider_cooldowns(
                    scope, provider, model, reason, http_status,
                    cooldown_until, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope) DO UPDATE SET
                    provider=excluded.provider,
                    model=excluded.model,
                    reason=excluded.reason,
                    http_status=excluded.http_status,
                    cooldown_until=excluded.cooldown_until,
                    updated_at=excluded.updated_at
                """,
                (scope, provider, model, reason, http_status, cooldown_until, now, now),
            )
        return self.get_provider_cooldown(scope, active_only=False)  # type: ignore[return-value]

    def get_provider_cooldown(
        self,
        scope: str,
        *,
        active_only: bool = True,
    ) -> ProviderCooldownRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM provider_cooldowns WHERE scope = ?",
                (scope,),
            ).fetchone()
        if row is None:
            return None
        record = ProviderCooldownRecord(
            scope=row["scope"],
            provider=row["provider"],
            model=row["model"],
            reason=row["reason"],
            http_status=row["http_status"],
            cooldown_until=row["cooldown_until"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        if active_only:
            try:
                until = datetime.fromisoformat(record.cooldown_until)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
                if until <= datetime.now(timezone.utc):
                    self.clear_provider_cooldown(scope)
                    return None
            except ValueError:
                self.clear_provider_cooldown(scope)
                return None
        return record

    def list_active_cooldowns(self) -> list[ProviderCooldownRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT scope FROM provider_cooldowns ORDER BY cooldown_until ASC").fetchall()
        records: list[ProviderCooldownRecord] = []
        for row in rows:
            item = self.get_provider_cooldown(row["scope"], active_only=True)
            if item is not None:
                records.append(item)
        return records

    def clear_provider_cooldown(self, scope: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM provider_cooldowns WHERE scope = ?", (scope,))

    def cooldown_map(self) -> dict[str, str]:
        return {item.scope: item.cooldown_until for item in self.list_active_cooldowns()}

    # ---------- projects / teams / context isolation ----------

    @staticmethod
    def _json_list(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []

    @staticmethod
    def _project_from_row(row: sqlite3.Row) -> ProjectRecord:
        return ProjectRecord(
            id=row["id"], name=row["name"], slug=row["slug"],
            workspace_path=row["workspace_path"], workspace_source=row["workspace_source"],
            isolation_mode=row["isolation_mode"], approval_mode=row["approval_mode"],
            sandbox_mode=row["sandbox_mode"], approval_policy=row["approval_policy"],
            approvals_reviewer=row["approvals_reviewer"],
            custom_permissions=_json_dict(row["custom_permissions"]), status=row["status"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def create_project(self, *, name: str, slug: str, workspace_path: str,
                       workspace_source: str = "external", isolation_mode: str = "strict-context",
                       approval_mode: str = "ask", sandbox_mode: str = "workspace-write",
                       approval_policy: str = "on-request", approvals_reviewer: str = "user",
                       custom_permissions: dict[str, str] | None = None) -> ProjectRecord:
        project_id = f"prj_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO projects(id,name,slug,workspace_path,workspace_source,isolation_mode,
                  approval_mode,sandbox_mode,approval_policy,approvals_reviewer,custom_permissions,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,'active',?,?)
            """, (project_id,name,slug,workspace_path,workspace_source,isolation_mode,approval_mode,
                    sandbox_mode,approval_policy,approvals_reviewer,json.dumps(custom_permissions or {}),now,now))
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> ProjectRecord:
        with self._connect() as conn:
            row=conn.execute("SELECT * FROM projects WHERE id=?",(project_id,)).fetchone()
        if row is None: raise KeyError(f"Project not found: {project_id}")
        return self._project_from_row(row)

    def list_projects(self, *, include_archived: bool = False) -> list[ProjectRecord]:
        query="SELECT * FROM projects"
        if not include_archived: query += " WHERE status='active'"
        query += " ORDER BY updated_at DESC"
        with self._connect() as conn: rows=conn.execute(query).fetchall()
        return [self._project_from_row(row) for row in rows]

    def update_project(self, project_id: str, **fields: object) -> ProjectRecord:
        allowed={"name","slug","workspace_path","workspace_source","isolation_mode","approval_mode",
                 "sandbox_mode","approval_policy","approvals_reviewer","custom_permissions","status"}
        clean={k:v for k,v in fields.items() if k in allowed}
        if "custom_permissions" in clean and isinstance(clean["custom_permissions"],dict):
            clean["custom_permissions"]=json.dumps(clean["custom_permissions"],sort_keys=True)
        if not clean: return self.get_project(project_id)
        clean["updated_at"]=_utc_now()
        assigns=", ".join(f"{k}=?" for k in clean)
        with self._connect() as conn:
            conn.execute(f"UPDATE projects SET {assigns} WHERE id=?", list(clean.values())+[project_id])
        return self.get_project(project_id)

    def add_project_agent(self, *, project_id: str, name: str, role: str, provider: str,
                          model_id: str, reasoning: str | None = None, system_instructions: str = "",
                          read_scope: list[str] | None = None, write_scope: list[str] | None = None,
                          handoff_scope: list[str] | None = None) -> ProjectAgentRecord:
        agent_id=f"agt_{uuid.uuid4().hex[:12]}"; now=_utc_now()
        with self._connect() as conn:
            conn.execute("""INSERT INTO project_agents(id,project_id,name,role,provider,model_id,reasoning,
              system_instructions,read_scope,write_scope,handoff_scope,enabled,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
              (agent_id,project_id,name,role,provider,model_id,reasoning,system_instructions,
               json.dumps(read_scope or []),json.dumps(write_scope or []),json.dumps(handoff_scope or []),now,now))
            conn.execute("UPDATE projects SET updated_at=? WHERE id=?",(now,project_id))
        return self.get_project_agent(agent_id)

    def get_project_agent(self, agent_id: str) -> ProjectAgentRecord:
        with self._connect() as conn: row=conn.execute("SELECT * FROM project_agents WHERE id=?",(agent_id,)).fetchone()
        if row is None: raise KeyError(f"Project agent not found: {agent_id}")
        return ProjectAgentRecord(id=row["id"],project_id=row["project_id"],name=row["name"],role=row["role"],
          provider=row["provider"],model_id=row["model_id"],reasoning=row["reasoning"],system_instructions=row["system_instructions"],
          read_scope=self._json_list(row["read_scope"]),write_scope=self._json_list(row["write_scope"]),
          handoff_scope=self._json_list(row["handoff_scope"]),enabled=bool(row["enabled"]),created_at=row["created_at"],updated_at=row["updated_at"])

    def list_project_agents(self, project_id: str) -> list[ProjectAgentRecord]:
        with self._connect() as conn: rows=conn.execute("SELECT id FROM project_agents WHERE project_id=? ORDER BY rowid",(project_id,)).fetchall()
        return [self.get_project_agent(row["id"]) for row in rows]

    def update_project_agent(self, agent_id: str, **fields: object) -> ProjectAgentRecord:
        allowed={"name","role","provider","model_id","reasoning","system_instructions","read_scope","write_scope","handoff_scope","enabled"}
        clean={k:v for k,v in fields.items() if k in allowed}
        for key in ("read_scope","write_scope","handoff_scope"):
            if key in clean and isinstance(clean[key],list): clean[key]=json.dumps(clean[key])
        if "enabled" in clean: clean["enabled"]=1 if bool(clean["enabled"]) else 0
        if not clean: return self.get_project_agent(agent_id)
        clean["updated_at"]=_utc_now(); assigns=", ".join(f"{k}=?" for k in clean)
        with self._connect() as conn: conn.execute(f"UPDATE project_agents SET {assigns} WHERE id=?",list(clean.values())+[agent_id])
        return self.get_project_agent(agent_id)

    def delete_project_agent(self, agent_id: str) -> None:
        with self._connect() as conn: conn.execute("DELETE FROM project_agents WHERE id=?",(agent_id,))

    def add_project_context(self, *, project_id: str, name: str, kind: str, source_path: str | None,
                            stored_path: str, content_hash: str, agent_scope: list[str] | None = None) -> ProjectContextRecord:
        context_id=f"ctx_{uuid.uuid4().hex[:12]}"; now=_utc_now()
        with self._connect() as conn:
            conn.execute("""INSERT INTO project_context(id,project_id,name,kind,source_path,stored_path,content_hash,agent_scope,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",(context_id,project_id,name,kind,source_path,stored_path,content_hash,json.dumps(agent_scope or []),now,now))
            conn.execute("UPDATE projects SET updated_at=? WHERE id=?",(now,project_id))
        return self.get_project_context(context_id)

    def get_project_context(self, context_id: str) -> ProjectContextRecord:
        with self._connect() as conn: row=conn.execute("SELECT * FROM project_context WHERE id=?",(context_id,)).fetchone()
        if row is None: raise KeyError(f"Project context not found: {context_id}")
        return ProjectContextRecord(id=row["id"],project_id=row["project_id"],name=row["name"],kind=row["kind"],source_path=row["source_path"],
          stored_path=row["stored_path"],content_hash=row["content_hash"],agent_scope=self._json_list(row["agent_scope"]),created_at=row["created_at"],updated_at=row["updated_at"])

    def list_project_context(self, project_id: str) -> list[ProjectContextRecord]:
        with self._connect() as conn: rows=conn.execute("SELECT id FROM project_context WHERE project_id=? ORDER BY name",(project_id,)).fetchall()
        return [self.get_project_context(row["id"]) for row in rows]

    def record_project_approval(self, *, project_id: str, action: str, permission_mode: str,
                                decision: str, details: str = "", session_id: str | None = None) -> ProjectApprovalRecord:
        approval_id=f"apr_{uuid.uuid4().hex[:12]}"; now=_utc_now()
        with self._connect() as conn:
            conn.execute("INSERT INTO project_approvals(id,project_id,session_id,action,permission_mode,decision,details,created_at) VALUES(?,?,?,?,?,?,?,?)",
              (approval_id,project_id,session_id,action,permission_mode,decision,details,now))
        return ProjectApprovalRecord(id=approval_id,project_id=project_id,session_id=session_id,action=action,
          permission_mode=permission_mode,decision=decision,details=details,created_at=now)

    # ---------- settings / context / export ----------

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, _utc_now()),
            )

    def all_settings(self) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def ensure_title_from_first_prompt(self, session_id: str, prompt: str) -> None:
        session = self.get_session(session_id)
        if session.title != "Untitled session":
            return
        clean = " ".join(prompt.strip().split())
        if not clean:
            return
        title = clean[:57] + ("..." if len(clean) > 57 else "")
        self.update_session(session_id, title=title)

    def build_recent_context(self, session_id: str, *, limit: int = 8, max_chars: int = 12000) -> str:
        messages = self.get_messages(session_id, limit=limit)
        if not messages:
            return ""
        parts: list[str] = []
        used = 0
        for item in messages:
            chunk = f"{item.role.upper()}:\n{item.content.strip()}\n"
            if used + len(chunk) > max_chars:
                break
            parts.append(chunk)
            used += len(chunk)
        return "\n".join(parts).strip()

    def export_session(self, session_id: str) -> tuple[Path, Path]:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        session = self.get_session(session_id)
        messages = self.get_messages(session_id)
        attempts = self.get_attempts(session_id)
        run_states = self.list_run_states(session_id, limit=100)

        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", session.title).strip("-")
        safe = safe[:48] or "session"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = EXPORT_DIR / f"{stamp}-{safe}"
        markdown_path = base.with_suffix(".md")
        json_path = base.with_suffix(".json")

        lines = [
            f"# {session.title}",
            "",
            f"- Session ID: `{session.id}`",
            f"- Mode: `{session.mode}`",
            f"- Primary model: `{session.primary_model}`",
            f"- Reviewer: `{session.reviewer_model or '-'}`",
            f"- Status: `{session.status}`",
            f"- Last verdict: `{session.last_verdict or '-'}`",
            "",
            "## Conversation",
            "",
        ]
        for message in messages:
            lines.extend([f"### {message.role.title()}", "", message.content, ""])

        lines.extend(["## Attempts", ""])
        for attempt in attempts:
            lines.extend(
                [
                    f"### Attempt {attempt.attempt_number} — {attempt.agent_role}",
                    "",
                    f"- Model: `{attempt.model}`",
                    f"- Status: `{attempt.status}`",
                    f"- RunState: `{attempt.run_state_id or '-'}`",
                    f"- Failure fingerprint: `{attempt.failure_fingerprint or '-'}`",
                    "",
                    attempt.output or attempt.error or "_No output_",
                    "",
                ]
            )

        lines.extend(["## RunState", ""])
        for run in run_states:
            lines.extend(
                [
                    f"### {run.task_id}",
                    "",
                    f"- Status: `{run.status}`",
                    f"- Worker: `{run.current_worker}`",
                    f"- Reviewer: `{run.reviewer or '-'}`",
                    f"- Verdict: `{run.verdict or '-'}`",
                    f"- Retry: `{run.retries_used}/{run.retry_budget}`",
                    f"- Failure fingerprint: `{run.failure_fingerprint or '-'}`",
                    f"- Escalation: `{run.escalation_state}`",
                    "",
                ]
            )
        markdown_path.write_text("\n".join(lines), encoding="utf-8")
        json_path.write_text(
            json.dumps(
                {
                    "session": asdict(session),
                    "messages": [asdict(x) for x in messages],
                    "attempts": [asdict(x) for x in attempts],
                    "run_states": [asdict(x) for x in run_states],
                    "provider_cooldowns": [asdict(x) for x in self.list_active_cooldowns()],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        with self._connect() as conn:
            now = _utc_now()
            conn.execute(
                "INSERT INTO artifacts(session_id, kind, path, created_at) VALUES(?, 'export_markdown', ?, ?)",
                (session_id, str(markdown_path), now),
            )
            conn.execute(
                "INSERT INTO artifacts(session_id, kind, path, created_at) VALUES(?, 'export_json', ?, ?)",
                (session_id, str(json_path), now),
            )
        return markdown_path, json_path
