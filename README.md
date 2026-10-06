# JORE

**JORE (Yor-Eh)** is a terminal-first multi-agent orchestrator for Codex and OpenCode.

> Build. Explore. Create. Together.

JORE coordinates AI agents inside isolated project workspaces with configurable roles, approval profiles, review loops, resumable sessions, and verified filesystem execution.

## Status

**v1.12.6 — Stable Beta**

This release is the frozen JORE core baseline before development of the JORE Visualizer.

## Features

- Terminal-first interactive TUI
- Codex and OpenCode integration
- Isolated project workspaces
- Configurable multi-agent teams
- Supervisor → worker → reviewer workflows
- Approval profiles
- Project context documents
- SQLite-backed history and resumable sessions
- RunState and attempt tracking
- Provider cooldown and failure detection
- Verified filesystem execution
- Windows ↔ WSL workspace bridge verification
- Project-aware filesystem safety boundaries

## Current Platform

JORE currently targets Windows with a dedicated WSL environment.

The public command is `jore`.

The internal Python package currently retains the historical `agenthub` namespace for compatibility.

## Architecture

JORE currently consists of:

- Terminal UI
- Project & Team Runtime
- OpenCode Adapter
- Codex Adapter
- Resilience / RunState
- SQLite History
- Workspace Verification

Provider credentials remain owned by Codex and OpenCode. JORE does not store raw provider credentials.

## Next: JORE Visualizer

Development continues in the `v1.13.x` line with an optional Three.js visualizer sidecar.

The first visualizer protocol will expose runtime event families such as:

- `project.*`
- `run.*`
- `agent.*`
- `review.*`
- `file.*`
- `error.*`

The visual layer will remain separate from the orchestration core so JORE can continue operating when visualization is disabled or unavailable.

## License

Copyright © 2026 Raka Satria Efendi.

Licensed under the Apache License, Version 2.0.

See [LICENSE](LICENSE) and [NOTICE](NOTICE).
