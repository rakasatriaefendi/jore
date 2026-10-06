# AgentHub v1.7 E2E Test Plan

## Upgrade

From an installed v1.6:

```powershell
cd "D:\AgentHub\agenthub-v1.7.0-update\setup\windows"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

Do not uninstall v1.6 first. The upgrade should preserve SQLite history,
settings, provider authentication and external CLI installations.

## Startup

Open a new PowerShell:

```text
agenthub
```

Expected:

- full-screen TUI
- fixed header
- conversation/home pane
- work dock
- status line
- multiline composer

Fallback check:

```text
agenthub classic
```

## Composer

1. Type `/` and verify completion dropdown.
2. Type `/mo` and verify `/model` + `/models`.
3. Press Ctrl+J and verify a newline is inserted.
4. Press Enter and verify the full multiline prompt is sent.

## Pickers

Test:

```text
/new
/model
/models
/sessions
/theme
/tasks
```

Expected:

```text
Up/Down  move
Enter    select
Esc      back
```

## Work dock

During a normal provider request:

- event feed updates
- foreground task appears
- duration changes without blocking composer

Single Agent only:

```text
/bg summarize the repository structure
```

Expected:

- background task appears with its own ID
- composer remains usable
- `/tasks` can inspect it

## Ctrl+C

While running:

```text
Ctrl+C
```

Expected: cancellation requested.

Press again within 2 seconds:

Expected: AgentHub exits.

When idle with text in composer:

Expected first Ctrl+C clears the draft.

## Dock shortcuts

```text
Ctrl+T / F6
```

show/hide work dock.

```text
Ctrl+R / F7
```

expanded/compact dock.

## Themes

```text
/theme
```

Test:

- AgentHub Cyan
- Warm Research
- Gemini Night
- Mono

Theme should persist across restarts.

## Persistence

Create a session, send at least one turn, exit, restart, then:

```text
/sessions
```

Resume the session and verify the stored conversation remains.

## Doctor

```text
agenthub doctor
```

Expected runtime list includes:

```text
TUI   prompt-toolkit <version>
```

## Uninstall regression

The known-good PID-based uninstaller must remain free of:

```text
pgrep
pkill
bash -lc
```

and preserve:

```text
~/projects/agenthub
internal orchestration source tree
provider credentials
external provider CLI installs
WSL distro AgentHub
```
