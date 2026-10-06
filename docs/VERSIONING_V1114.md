# JORE v1.11.4 — dynamic release versioning

`release.json` is the single source of truth for the JORE release version.

Example:

```json
{
  "product": "JORE",
  "version": "1.11.4",
  "channel": "stable",
  "runtime_schema": 2,
  "launcher": "jore"
}
```

The Windows installer reads this file and derives:

- `$joreVersion`
- `$joreFileVersion`
- `$expectedRuntimeVersion`
- frozen runtime directory name
- `JORE_VERSION` passed to the runtime builder
- `jore.exe` AssemblyVersion/FileVersion/InformationalVersion
- final `jore --version` assertion

The frozen runtime carries its own runtime manifest. Python resolves
`agenthub.version.VERSION` from the installed manifest or `JORE_VERSION`.

No installer/runtime version assertion should contain a literal semantic
version. To cut a new release, the release pipeline only needs to update
`release.json`.
