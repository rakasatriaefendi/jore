# JORE v1.11.2 true clean-install regression

The development repositories may remain renamed/hidden.

Required checks:

1. Freeze bundled payload into `~/.local/share/jore/runtime/1.11.2`.
2. Direct frozen interpreter import works without manually setting PYTHONPATH.
3. `python -m agenthub.dependencies check --json` works from the frozen venv.
4. `jore --version` reports 1.11.2.
5. Windows launcher is `jore.exe` with file version 1.11.2.0.
6. `~/projects/agenthub` and `~/projects/cli-agent-orchestrator` are not required.
