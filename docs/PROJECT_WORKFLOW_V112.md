# JORE v1.12 project workflow

## Windows-folder workflow

```powershell
cd C:\Users\rakas\OneDrive\Documents\JHC-work
jore
```

or

```powershell
cd D:\Tugas-kampus
jore
```

Create a project with `/project new`, then use `.` as the workspace path. JORE's Windows launcher forwards the current Windows directory to WSL and the frozen launcher maps it using `wslpath`.

JORE writes only a small `.jore/project.json` marker into the workspace. Runtime/database/context copies remain under the JORE user data directory.

When JORE is launched later from that folder (or a child folder), it detects the marker and opens the project view automatically.

## Project setup

1. `/project new`
2. enter project name
3. enter/paste workspace path (`.` means current folder)
4. choose permissions
5. add agents with `/agent add`
6. add docs with `/context add <path>`, `/context new <name>`, `/context paste <name>`, or `/context scan`
7. execute one complete goal using `/run <goal>`
8. JORE shows an approval gate; no project agent starts until approved
9. supervisor (if configured) plans, workers execute, reviewer checks, supervisor summarizes

## Team examples

- frontend -> OpenCode / Nemotron
- backend -> OpenCode / MiMo
- documentation -> OpenCode / Gemini or another configured model
- reviewer -> OpenCode / MiMo
- supervisor -> Codex / selected Codex model

Use `/agent model <name>` to change a project agent's provider/model without recreating the project.
