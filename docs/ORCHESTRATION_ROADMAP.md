# JORE Orchestration Layer — v1.11.0

## Completed reliability stack

```text
1. Frozen runtime / launcher          DONE
2. Installer + uninstaller            DONE
3. SQLite History + Resume            DONE
4. Persisted RunState + attempts      DONE
5. Model switching + cooldown         DONE
6. Failure fingerprint + loop guard   DONE
7. Codex escalation                   DONE
8. Long-term/vector memory            OPTIONAL / DEFERRED
```

## NEEDS_FIX flow

```text
worker
  ↓
reviewer
  ↓
PASS ────────────────► complete
  │
  └─ NEEDS_FIX
       ├─ retry with reviewer feedback     (while retry budget remains)
       ├─ switch free worker + retry       (cooldown-aware)
       ├─ Codex Diagnose                   (read-only supervisor)
       ├─ Codex Prompt                     (auto-send or load into composer)
       ├─ Codex Fix                        (take over / edit / test)
       └─ stop
```

If the same failure fingerprint repeats at the configured threshold, free retry
and worker switching are disabled for that RunState. Codex escalation remains
available.

Provider cooldowns are a separate failure class and never consume the logical
quality retry budget.

## Handoff packet

The Codex handoff packet now includes persisted RunState fields, retry counters,
failure fingerprint, loop count, escalation state, and active provider cooldowns
in addition to the original task/result/reviewer context.
