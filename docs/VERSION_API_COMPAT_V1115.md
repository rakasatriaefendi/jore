# JORE v1.11.5 — dynamic version API compatibility

v1.11.4 correctly removed the hardcoded semantic version from Python, but the
replacement `agenthub.version` module accidentally removed compatibility
symbols still imported by the existing runtime:

```python
APP_NAME
__version__
```

That caused the clean-runtime import check to fail before `runtime.json` was
published.

v1.11.5 keeps dynamic version resolution and restores the stable public API:

```python
APP_NAME
APP_PRONUNCIATION
VERSION
__version__
```

`VERSION` and `__version__` resolve dynamically from:

1. build/install environment
2. installed `runtime.json`
3. packaged `release.json`
4. `0+unknown` only as a last-resort diagnostic fallback

The installer derives all semantic version values from `release.json`.
There is no semantic-version literal in installer validation logic.
