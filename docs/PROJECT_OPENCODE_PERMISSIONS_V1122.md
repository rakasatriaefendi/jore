# JORE v1.12.2 — Project OpenCode permission bridge

This patch fixes a project-run failure where OpenCode headless runs emitted:

    permission requested: external_directory (<project>/*); auto-rejecting

The failure occurred even after the user selected **Approve for Me** in JORE.

## Changes

- OpenCode receives the exact JORE project workspace as an explicit allowed `external_directory` boundary.
- `Approve for Me` and `Full Access` run OpenCode with `--auto`, matching the user's explicit automatic-approval selection.
- Ask-for-Approval keeps true outside-workspace requests gated; JORE now reports a clear permission error rather than raw provider JSON.
- `PWD` is synchronized with the project workspace for child processes.
- Project prompts tell agents to prefer relative paths.
- ANSI escape sequences are removed from the live-event feed.
- Project dashboard navigation fixes from v1.12.1 are included.
- Project sessions display their project workspace in the header.

JORE still treats project context isolation separately from OS-level provider sandboxing. OpenCode shell authority is provider-controlled and should not be described as a hard OS sandbox.
