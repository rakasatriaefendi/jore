# JORE v1.11.2 true clean-install test

Precondition: `~/projects/agenthub` and `~/projects/cli-agent-orchestrator` may be absent or renamed.

Expected installer behavior:

1. Stage the release ZIP contents into `/tmp`.
2. Freeze `payload/src/agenthub` into `~/.local/share/jore/runtime/1.11.2/app/src/agenthub`.
3. Build an isolated Python environment with `uv`.
4. Register `~/.local/bin/jore`.
5. Compile a versioned Windows `jore.exe` bridge.
6. Never read either development project directory.

Smoke checks:

```text
jore --version            -> JORE 1.11.2
jore doctor               -> Runtime: frozen clean release
Get-Command jore          -> jore.exe version 1.11.2.0
```

Then start an Auto session and verify Nemotron -> MiMo review without restoring the hidden development repositories.
