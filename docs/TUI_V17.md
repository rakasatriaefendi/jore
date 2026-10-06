# AgentHub TUI v1.7

## Layout

```text
┌ AgentHub header ────────────────────────────────────────────────┐
│ session / model / working directory                            │
├ conversation ───────────────────────────────────────────────────┤
│ user + assistant + reviewer timeline                           │
│                                                                │
├ live events ────────────────────────────────────────────────────┤
│ provider/orchestrator/tool lifecycle                            │
├ work dock ──────────────────────────────────────────────────────┤
│ foreground + background tasks                                  │
├ status ─────────────────────────────────────────────────────────┤
│ model | mode | ~ctx | messages | runs | tasks | cost | time     │
├ composer ───────────────────────────────────────────────────────┤
│ ❯ multiline input                                               │
│   slash autocomplete                                            │
└ Enter send · Ctrl+J newline · Ctrl+C interrupt ────────────────┘
```

## Model/session picker

Modal overlay:

```text
Select model

  GPT-6-Astra
❯ GPT-6-Sol
  GPT-6-Luna
  ...

↑/↓ move   Enter select   Esc back
```

## Activity events

The event pane uses AgentHub-native event categories:

```text
⋯ context
◇ provider
⚙ orchestrator
◆ agent
⌘ tool/provider tool-event
! review/warning
✓ success
✕ error
↻ queued
```

## Background execution

`/bg` starts a parallel direct-provider task in a Single Agent session.

Background results are not silently injected into the primary conversation.
They are visible in the task dock and persisted as `background` attempts.

## Cancellation

Provider adapters accept a `threading.Event`.

Codex/OpenCode subprocesses run in their own process groups and terminate on
cancellation. Auto-runtime launch commands are cancellable; the Auto-runtime session is then
shut down through the existing cleanup path.

## Fallback

If full-screen prompt_toolkit cannot be imported, AgentHub falls back to the
v1.6-style Rich interface.

Users can force classic mode:

```text
agenthub classic
AGENTHUB_CLASSIC=1 agenthub
```
