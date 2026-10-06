# JORE v1.12 validation

Validated before packaging:

- all Python modules compile
- SQLite schema v2 -> v3 migration preserves existing sessions
- named project/agent/context CRUD
- project context A is not returned to project B
- duplicate/parent-child workspace overlap guard
- Windows drive path mapping (`D:\\...` -> `/mnt/d/...`)
- every project team run fails closed without explicit approval
- fake-provider team pipeline: supervisor plan -> worker -> reviewer -> supervisor final
- project session and RunState persist `project_id`
- global quick-chat history excludes project sessions
- `.jore/project.json` marker discovery from child directories
- TUI auto-opens a recognized project workspace
- `freeze-runtime.sh` and `apply.sh` pass shell syntax checks
- Windows installer remains dynamically versioned from `release.json`

The container used to assemble this ZIP has no outbound network access, so the
full `uv pip install` frozen-runtime build could not be re-run end-to-end here.
That same online dependency step already succeeded on the target Windows/WSL
machine for v1.11.5. The v1.12 source/import paths were compiled and exercised
independently.
