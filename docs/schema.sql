-- JORE SQLite schema v2 (v1.11.0)
-- Existing v1 databases are migrated in-place by agenthub.storage.Storage.

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
