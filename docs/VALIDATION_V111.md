# JORE v1.11.0 validation notes

Validation performed before packaging:

- all bundled Python modules compile with `py_compile`
- `apply.sh` passes `bash -n`
- `freeze-runtime.sh` passes `bash -n`
- all 61 HTTP status codes supplied for the project are present in the policy map
- 429 with numeric `Retry-After` preserves retry budget and records cooldown
- transient free-worker failure falls back to the other free worker without consuming RunState retry budget
- legacy SQLite attempts schema migrates in place to schema v2
- RunState and linked attempts survive reopening the SQLite database
- repeated reviewer quality fingerprint reaches loop guard at the configured threshold
- frozen-runtime flow was exercised with isolated fake app/orchestrator sources and a fake `uv` builder
- uninstaller regression audit confirms it does not invoke `pgrep`, `pkill`, or `bash -lc` for process termination
- development source deletion patterns are absent from the uninstaller

## Windows launcher note

The installer generates `jore.exe` on Windows with PowerShell `Add-Type` and
embeds assembly/file version `1.11.0.0`. The Linux build environment used to
assemble this update does not include Windows PowerShell/.NET Framework, so the
actual PE compilation step must be exercised by the installer on Windows.
The installer fails closed if compilation fails or if the resulting file version
does not begin with `1.11.0`.
