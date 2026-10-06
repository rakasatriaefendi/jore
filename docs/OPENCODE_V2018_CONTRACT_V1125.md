# JORE v1.12.5 — OpenCode v2.0.18 project runner contract

This patch is based on the actual `opencode v2.0.18` CLI contract observed on
the target JORE machine.

Observed `opencode run --help` supports:

- `--standalone`
- `--server`
- `--continue`
- `--session`
- `--fork`
- `--model`
- `--agent`
- `--format`
- `--file`
- `--title`
- `--thinking`
- `--auto`

It does **not** expose a `--dir` flag.

## Correct JORE invocation

JORE uses the process working directory as the project boundary:

    cwd=/mnt/d/AgentHub/Coba

and invokes:

    opencode run --standalone --auto       --agent build       --model <provider/model>       --format json       "<prompt>"

The private standalone server is deliberate for project runs: it avoids
depending on the user's shared background OpenCode service while JORE is
executing an isolated project task.

## Compatibility guard

JORE now requires only the flags it actually uses:

- `--standalone`
- `--agent`
- `--model`
- `--format`

`--auto` is additionally required only for permission profiles that request
automatic approval.

Project path selection is an OS subprocess `cwd`, not a CLI flag.
