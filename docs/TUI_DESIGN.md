# AgentHub Terminal UI v1.6

## Design goals

AgentHub should feel alive without pretending to know provider state it cannot
actually observe.

The v1.6 interface borrows useful interaction ideas from terminal agents while
keeping its own identity:

- welcome surface
- compact command discoverability
- status strip above the input composer
- visible working/loading state
- explicit success/warning/error states
- session-first navigation
- provider/model visibility

## AgentHub identity

Primary accent: cyan
Secondary accent: warm orange
Neutral: terminal foreground / bright black

Core symbols:

```text
✦ AgentHub / active work
◆ current model / session
◈ session
◉ model catalog
◷ history
⚙ settings
✚ doctor
↻ retry / refresh / attempts
✓ success
✕ error
! warning
i information
❯ composer
```

## Welcome

Wide terminals render a compact ASCII AgentHub mark inside a bordered panel.
Narrow terminals use a small title card automatically.

## Session surface

```text
╭─ ✦ AgentHub Session ───────────────────────────────────────────────╮
│ ◈ Fix authentication                                             │
│ mode  Single  model  Codex · GPT-6-Astra                         │
│ review Off  cwd  ~/projects/agenthub                             │
╰───────────────────────────────────────────────────────────────────╯

╭─ status ───────────────────────────────────────────────────────────╮
│ ◆ Codex · GPT-6-Astra │ Single │ ~4.8K ctx │ 8 msg │ 3 run │ 7m │
╰───────────────────────────────────────────────────────────────────╯

✎ message  •  / commands  •  Ctrl+C interrupt

❯
```

## Loading state

The provider call uses a spinner plus a staged bar:

```text
⠼ ✦ OpenCode · opencode/nemotron-3-ultra-free
   waiting for response  [███████░░░] 27s
```

This does not claim a provider completion percentage. The bar only visualizes
AgentHub's local execution stages.

## Context and cost honesty

The context number is currently a local text-size estimate and is marked `~`.
AgentHub does not fabricate a context-window denominator.

Cost is displayed as `n/a` until a reliable provider usage/cost source is
integrated.

## Responsive behavior

- wide: model + mode + context + messages + runs + cost + duration + verdict
- medium: model + mode + context + messages + runs + duration
- narrow: model + mode + duration

## Next UI stage

Only after v1.6 is stable:

- real multiline composer
- slash-command autocomplete dropdown
- arrow-key model/session picker
- fixed bottom status/composer region
- background task dock
- stream/tool event feed
- themes/skins
- terminal notifications/bell
- provider-native token usage
- usage/cost accounting
