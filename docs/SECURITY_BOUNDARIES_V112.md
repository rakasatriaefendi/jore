# JORE v1.12 project isolation and approval boundaries

## Guaranteed by JORE

- Project records, project agents, imported context, project sessions, RunState, attempts and approvals are keyed by `project_id`.
- Quick-chat history excludes project sessions by default.
- Project session pickers only resume sessions from the active project.
- Imported documents are copied into the active project's private JORE data directory.
- Parent/child/duplicate workspace paths are rejected when creating another active JORE project.
- Every `/run` team execution requires an explicit JORE approval decision. Full Access requires a second confirmation.
- Codex receives the configured sandbox mode (`read-only`, `workspace-write`, or `danger-full-access`).

## Not claimed in v1.12

OpenCode is invoked from the project working directory and receives project-scoped context/instructions, but JORE v1.12 does not claim that OpenCode is OS-level confined to that directory. Provider-native sandbox/approval bridging must be verified and implemented separately before JORE can call this a complete filesystem security boundary for OpenCode.

Therefore `strict-context` means JORE does not mix project context. It does not mean every third-party provider CLI is forcibly chrooted/sandboxed by JORE.
