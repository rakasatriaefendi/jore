# JORE v1.11.0 — Runtime & Resilience Layer

## 1. Frozen runtime / launcher

`jore` no longer executes the editable development tree directly.

Installer flow:

```text
~/projects/agenthub                  development source
development orchestration source tree   internal development source
            │
            │ installer snapshot
            ▼
~/.local/share/jore/runtime/1.11.0/
├── app/
├── orchestrator/
├── bin/jore
└── runtime.json
            │
            └── current -> 1.11.0
```

`~/.local/bin/jore` points at the frozen runtime. Editing either development
repository after installation does not change the active JORE runtime.

The Windows launcher is now a small generated `jore.exe` with native PE file
version `1.11.0.0`. Therefore:

```powershell
Get-Command jore | Select CommandType,Name,Version,Source
```

should report an `Application` named `jore.exe` with version `1.11.0.0`.

## 2. Persisted RunState

Every logical execution creates a persisted RunState in `agenthub.db`:

```text
RunState
├─ task_id
├─ session_id
├─ current_worker
├─ reviewer
├─ attempt_no
├─ verdict
├─ failure_fingerprint
├─ retry_budget
├─ retries_used
├─ provider_cooldown
├─ escalation_state
├─ handoff_packet
├─ original_instruction
├─ primary_output
├─ reviewer_output
├─ last_error
└─ loop_count
```

Attempts reference their RunState. Exports include RunState and active cooldowns.

Use `/status` or `/runstate` to inspect the latest state.

## 3. Cooldown manager

Provider/model cooldowns are persisted in SQLite. Transient provider failures do
not consume the logical repair budget.

Examples:

```text
HTTP 429 -> rate_limit -> cooldown -> alternate free worker
HTTP 408 -> timeout -> cooldown -> alternate free worker
HTTP 502 -> bad_gateway -> cooldown -> alternate free worker
HTTP 503 -> service_unavailable -> cooldown -> alternate free worker
HTTP 504 -> gateway_timeout -> cooldown -> alternate free worker
```

Auto mode checks cooldowns before launching a free model. If the preferred model
is cooling down, JORE automatically tries the other free model. If both are in
cooldown, it stops and tells the user how long remains. No quality retry is spent.

Direct Codex/OpenCode selections are not silently changed: JORE reports their
cooldown and waits for user action.

## 4. Failure fingerprint / loop guard

Failures are normalized into stable fingerprints. Protocol failures ignore
provider wording differences, for example:

```text
HTTP 401 Unauthorized: invalid token
still HTTP 401 Unauthorized
```

both become:

```text
runtime:authentication:http401
```

Reviewer failures use quality categories, for example:

```text
review:factual
review:authentication:http401
review:missing_evidence
review:test
```

Within one RunState, repeating the same reviewer fingerprint twice (default)
marks the run `loop_detected` and disables further free retries.

Repeated technical failures across separate retries in the same session are also
detected. On the threshold hit JORE promotes the failure into `NEEDS_FIX` so the
existing Codex Diagnose / Prompt / Fix escalation menu becomes available.

Defaults:

```text
retry_budget            3
failure_loop_threshold  2
```

Both are persisted settings.
