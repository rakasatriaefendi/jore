# JORE v1.12.4 — OpenCode `run` compatibility hotfix

## Root cause

JORE v1.12.3 incorrectly invoked:

    opencode run --standalone ...

`--standalone` belongs to an older interactive/mini integration path and is
not a supported flag for the current non-interactive `opencode run` command.

When OpenCode receives the unsupported flag it prints the command help
(`DESCRIPTION / USAGE`) instead of executing the project task.

## Fix

JORE now invokes:

    opencode run ...

and probes:

    opencode run --help

once per process to validate the installed CLI capabilities.

Required project flags:

- --agent
- --dir
- --model
- --format

Permission profiles that need automatic approval additionally require:

- --auto

If a future OpenCode release changes these flags, JORE now fails with an
explicit compatibility error instead of forwarding a generic usage screen.

This hotfix does not weaken the project workspace boundary.
