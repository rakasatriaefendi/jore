# JORE v1.12.3 — Project Execution Integrity

## Fixed bug

A project team could return a plausible implementation report while the workspace
remained unchanged. This happened when OpenCode inherited a user-level
`default_agent = plan` (or equivalent restricted primary agent). `opencode run`
then produced prose instead of using file-editing tools.

## v1.12.3 rules

- JORE project implementation workers explicitly run OpenCode with `--agent build`.
- Project supervisor/reviewer read-only phases explicitly use `--agent plan`.
- JORE also passes `--dir <project-workspace>` instead of relying only on process cwd.
- JORE snapshots the project filesystem before work begins and verifies real file
  mutations afterward.
- Model narration is not evidence of implementation.
- If all workers return prose but no file changed, JORE performs one recovery run
  in explicit execution mode.
- If the workspace is still unchanged, the run fails closed. JORE will not display
  `JORE COMPLETE` for an unverified implementation.
- Reviewer and supervisor receive the verified changed-file list and are told to
  inspect the actual workspace rather than trust team claims.

Generated/build trees and JORE metadata (`.jore`, `.git`, `node_modules`, `.venv`,
`dist`, `build`, caches) are ignored by the lightweight mutation verifier.
