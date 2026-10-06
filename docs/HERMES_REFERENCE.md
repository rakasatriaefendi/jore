# Hermes Agent CLI reference used for AgentHub v1.7

This document records which interaction patterns from the user-provided Hermes
Agent CLI documentation were useful as design references.

AgentHub does not reuse Hermes source code. The concepts below were adapted to
AgentHub's own Python/provider orchestration architecture.

## Referenced interaction ideas

### Full terminal interface

Hermes describes its CLI as a terminal UI with multiline editing,
slash-command autocomplete, conversation history, interrupt behavior and
streaming tool output.

AgentHub v1.7 maps those ideas to `prompt_toolkit`.

### Fixed input and status

Hermes documents a stable conversation area with a fixed input prompt and a
persistent status bar directly above it.

AgentHub v1.7 now uses the same broad information architecture:

```text
conversation
live events
work dock
status
composer
```

but uses AgentHub-specific fields and styling.

### Honest context metadata

Hermes marks locally estimated context values with `~`.

AgentHub already used estimated context in v1.6 and retains that convention in
v1.7:

```text
~2480 ctx
```

AgentHub does not invent a max context denominator unless provider metadata is
available.

### Multiline keys

Hermes documents `Enter` for send and `Ctrl+J` as a portable newline shortcut,
including for Windows Terminal where modified Enter keys can be ambiguous.

AgentHub v1.7 uses:

```text
Enter    send
Ctrl+J   newline
```

### Work dock

Hermes documents a live work monitor/dock and keyboard toggles:

```text
Ctrl+T / F6
Ctrl+R / F7
```

AgentHub v1.7 uses the same ergonomic key family for its own task/event dock:

```text
Ctrl+T / F6    show/hide
Ctrl+R / F7    expanded/compact
```

### Ctrl+C

Hermes documents an interrupt-first Ctrl+C and double-press force-exit model.

AgentHub v1.7 adapts that behavior to provider cancellation events:

```text
running task   -> request cancellation
draft present  -> clear composer
idle           -> warn
second press   -> exit
```

### Background prompts

Hermes exposes `/bg <prompt>` and shows active jobs in the work dock.

AgentHub v1.7 adds `/bg <prompt>` for Single Agent Codex/OpenCode sessions and
tracks each job in an in-memory work dock while persisting attempts in SQLite.

### Slash autocomplete and interactive sessions

Hermes documents typing `/` to open command completion and `/sessions` to open
an arrow-key session picker.

AgentHub v1.7 implements both patterns with its own command/model/session
registry.

## Not copied yet

AgentHub v1.7 intentionally does not claim feature parity with Hermes.

Examples not implemented yet:

- prompt stash stack
- side-question semantics
- full background steering
- worktree manager
- shell-mode approval system
- voice mode
- provider-native context/cost accounting
- images in the composer
- MCP/skills UI
- native mouse task actions
