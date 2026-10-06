# AgentHub v1.7.2 TUI hotfix checks

## 1. Idle flicker

Start:

```text
agenthub
```

Leave the TUI idle for 30 seconds.

Expected:
- no repeated visible full-screen flashing
- cursor remains stable
- no periodic repaint is needed while nothing is running

## 2. Active refresh

Start an Auto task.

Expected:
- live events appear as stages happen
- running duration updates approximately once per second
- the screen should not visibly blink on each timer tick

## 3. Runtime wording

Live events may show:

```text
AgentHub orchestration started
AgentHub orchestration ready
starting primary agent
starting reviewer agent
```

No underlying internal runtime name should render in the TUI.

## 4. Output follow

Run an Auto prompt that produces both primary and reviewer messages.

Expected after reviewer finishes:
- newest reviewer/output content is visible in the conversation pane
- the pane does not remain pinned to the first assistant response
- `/history` still provides the complete stored timeline

## 5. Duration freeze

After a task finishes, note the duration in the work dock.

Wait 60 seconds.

Expected:
- completed-task duration remains unchanged
- event ages may continue increasing; task duration must not

## 6. Timing visibility

Expected live events include actual per-agent completion time:

```text
primary completed · <seconds>s
reviewer completed · <seconds>s
```

This timing is used to distinguish provider latency from AgentHub UI latency.
