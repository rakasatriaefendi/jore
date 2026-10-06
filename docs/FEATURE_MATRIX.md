# JORE Feature Matrix — v1.11.0

| Capability | Status |
|---|---|
| Windows `jore` launcher | Done — versioned `jore.exe` |
| Frozen WSL runtime | Done — release snapshot under `~/.local/share/jore/runtime/<version>` |
| Installer / uninstaller | Done — dev source and provider credentials preserved |
| SQLite history / resume | Done |
| Persisted attempts | Done |
| Persisted RunState | Done |
| Dynamic Codex/OpenCode model catalogs | Done |
| Free-model switching | Done |
| Provider/model cooldown | Done |
| 429/timeout/5xx transient handling | Done |
| Retry-budget preservation on cooldown | Done |
| Failure fingerprint | Done |
| Repeated-failure / loop detection | Done |
| Codex Diagnose | Done |
| Codex repair prompt + auto/manual dispatch | Done |
| Codex take-over / Fix | Done |
| Compact handoff packet | Done |
| Long-term/vector memory | Not implemented; intentionally deferred until a real retrieval need exists |

JORE still uses SQLite as its persistence layer. Vector storage is not required
for the current session/history/resilience workload.
