# JORE v1.12 — Projects & Teams

JORE projects are explicit context boundaries. A project owns:

- a named workspace path (including Windows-mounted paths such as `/mnt/c/...` or `/mnt/d/...`)
- project-scoped sessions and RunState
- named agents with provider/model assignments
- copied context documents such as `AGENTS.md`, `PRD.md`, `PLANNING.md`, `MEMORY.md`, and `GEMINI.md`
- approval policy and sandbox intent

## Permission presets

Every project team run requires a user approval gate before execution.

- Ask for Approval: workspace-write, on-request, reviewer=user
- Approve for Me: workspace-write, on-request, reviewer=auto_review
- Full Access: danger-full-access, never; JORE asks for an extra confirmation before each team run
- Custom: stored project configuration; safe default is workspace-write/on-request/user

The approval gate is JORE-level. Codex receives its sandbox mode directly. OpenCode is started inside the project workspace and receives strict project instructions, but JORE v1.12 does not claim OS-level filesystem confinement for OpenCode unless its provider runtime exposes/verifies such a sandbox.

## Context isolation

Database objects are keyed by `project_id`. Project context builders only query the active project. Imported documents are copied into `~/.local/share/agenthub/projects/<project_id>/context` so another project cannot receive them through JORE context assembly.

## Windows workspace bridge

The versioned `jore.exe` launcher forwards the current Windows directory as `JORE_WINDOWS_CWD`. The frozen WSL launcher maps it with `wslpath` and starts JORE from the mapped directory. Therefore these workflows are valid:

```powershell
cd C:\Users\rakas\OneDrive\Documents\JHC-work
jore

cd D:\Tugas-kampus
jore
```

Project creation can use `.` to bind to that folder.
