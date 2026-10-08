# JORE Visualizer — SECURITY

**Applies to:** JORE Visualizer v1.13.x
**Security posture:** Local, read-only visualization sidecar
**Core authority:** JORE Core in WSL

## 1. Security Objective

JORE Visualizer must provide useful live visualization without increasing the trust level of the browser.

The browser is a presentation client.

It must not become a path to:

- provider credentials
- arbitrary shell execution
- arbitrary filesystem mutation
- direct database mutation
- orchestration control
- privilege escalation

## 2. Trust Boundaries

### JORE Core

Owns:

- project runtime
- orchestration
- RunState
- attempts
- provider invocation
- provider-owned authentication
- SQLite
- approval policy
- review policy
- filesystem execution

### Visual Event Bridge

May expose only intentionally sanitized runtime metadata.

It is not a generic JORE Core API.

### Browser

Assume users can inspect:

- WebSocket traffic
- bundled JavaScript
- runtime state
- developer tools

Therefore browser-visible data must already be safe to reveal locally.

## 3. Default Network Exposure

Visual Event Bridge binds to loopback by default:

```text
127.0.0.1
```

Do not default to:

```text
0.0.0.0
```

Expected endpoint shape:

```text
ws://127.0.0.1:<port>/events
```

Any LAN/remote access requires a separate security design.

## 4. Read-Only MVP

The MVP event channel is for observation only.

No browser command endpoint is required.

Visualizer must not request:

- shell execution
- file deletion
- file modification
- provider invocation
- retry
- approval
- reviewer override
- run cancellation
- database mutation

Future state-changing controls require a separate authenticated command protocol.

## 5. Secret Handling

Never send to the browser:

- OpenAI API keys
- provider API keys
- OAuth access tokens
- OAuth refresh tokens
- GitHub tokens
- cookies
- passwords
- authorization headers
- credential-store content
- SSH private keys
- raw `.env` content
- full process environment

Never put secrets in client-exposed `VITE_*` variables.

## 6. Provider Credentials

Codex and OpenCode own their authentication state.

JORE must not copy raw credentials into Visualizer.

Allowed sanitized display metadata may include:

```text
provider: "opencode"
model: "example-model"
```

only when intentionally exposed for user display.

## 7. Filesystem Privacy

Avoid full absolute paths by default.

Prefer:

```json
{
  "display_name": "App.tsx",
  "operation": "modified"
}
```

Use project-relative paths only when needed.

Never emit file contents automatically as part of `file.changed`.

## 8. Prompt and Model Output Privacy

Do not send full prompts by default.

Do not send full model responses by default.

Use sanitized task labels such as:

```text
Task: Build login UI
```

rather than full orchestration prompts.

Transcript visualization requires future explicit privacy design.

## 9. Event Sanitization

All internal events sent to Visualizer should pass through an explicit sanitizer:

```text
Internal Event
→ VisualEventSanitizer
→ VisualEvent
→ WebSocket
```

Use allowlists where practical.

Do not forward arbitrary internal dictionaries.

## 10. Event Schema Validation

Client validates:

- schema identifier
- event type
- IDs
- timestamps
- payload shape
- field-size limits

Unknown future events must not crash the app.

Malformed events must be rejected safely.

## 11. Payload Size Limits

The event bridge must have reasonable message limits.

Do not use Visual Events to send:

- full source files
- binary models
- screenshots
- archives
- database dumps
- very large logs

## 12. Event Rate Protection

Protect browser responsiveness from event storms.

Possible strategies:

- bounded queue
- coalescing visual-only updates
- dropping redundant transient visual events
- backpressure if later needed

Do not drop terminal states such as final success/failure without explicit design.

## 13. Origin Policy

Keep local origins narrow.

During development, allow only intended local Vite origins where origin checks are implemented.

Do not broadly allow arbitrary origins without reason.

## 14. Reconnect Security

Reconnect logic must:

- retry only configured local endpoint
- use bounded backoff
- avoid silently switching hosts
- never accept endpoint changes from event payloads

## 15. Browser Storage

Avoid sensitive runtime data in:

- LocalStorage
- SessionStorage
- IndexedDB

Keep live run state primarily in memory.

Persist only non-sensitive preferences such as:

- graphics quality
- camera preference
- UI layout

## 16. Logging

Do not broadly dump potentially sensitive event objects.

Prefer targeted development diagnostics.

Production logging should be minimal.

## 17. Source Maps

Development source maps are expected.

Production source-map policy should be deliberate.

Main risk for this public project is unintended local data inclusion, not hiding open-source code.

## 18. Asset Security

Review 3D assets for:

- provenance
- license
- excessive size
- malformed structure
- external URLs
- extreme texture memory usage

Prefer reviewed local bundled assets.

Avoid arbitrary runtime third-party asset URLs.

## 19. External Resource Policy

Prefer local bundled:

- models
- textures
- fonts
- scripts

This improves:

- reproducibility
- privacy
- offline use
- supply-chain control

## 20. Dependency Security

Before adding a dependency:

- verify package identity
- verify project reputation
- inspect license
- confirm it is necessary
- review lockfile changes

Do not install dependencies solely because generated code suggests them.

## 21. Supply-Chain Safety

Do not blindly execute setup scripts from reference repositories.

When studying third-party repositories:

- inspect before copying
- do not import credential files
- do not copy unknown CI secret configuration
- do not vendor whole projects unless explicitly justified
- preserve license obligations

## 22. Core Failure Isolation

Visualizer failure must not fail Core.

Examples:

- bridge cannot start
- browser disconnects
- browser crashes
- event serialization fails
- Visualizer is closed

Core should continue or degrade gracefully.

Visual event emission must never become required for run completion.

## 23. Visualizer Failure Isolation

A non-critical asset failure must not crash the whole app.

Use:

- asset fallback
- controlled error boundary
- offline state
- malformed-event isolation

## 24. Database Boundary

Browser must never query JORE SQLite directly.

Reasons:

- schema coupling
- write risk
- sanitization bypass
- competing source of truth

Expose required information only through a designed event/read API.

## 25. Command Boundary

MVP does not need browser-to-Core commands.

If future versions add controls such as:

- cancel run
- approve action
- request history
- pause run

state-changing commands require:

- authentication/authorization design
- explicit confirmation where appropriate
- auditability
- origin/CSRF review where applicable
- separate threat model

Do not casually turn the read-only event socket into a generic command socket.

## 26. Threat Scenarios

### Provider token appears in event

Security defect. Fix sanitizer/protocol before release.

### Visualizer can write project files

Out of MVP scope and boundary violation.

### WebSocket exposed on LAN by default

Configuration defect unless explicitly designed and approved.

### Huge malicious event

Reject, truncate, or bound according to protocol limits.

### Browser closes during run

JORE run continues normally.

### Visualizer cannot reconnect

Core remains unaffected; browser shows offline state.

## 27. Security Tests

Before v1.13 release:

- [ ] bridge binds only to intended local interface
- [ ] no raw credential fields in events
- [ ] no `.env` contents emitted
- [ ] no auth headers emitted
- [ ] no full process environment emitted
- [ ] malformed event does not crash browser
- [ ] unknown event does not crash browser
- [ ] oversized payload behavior is defined
- [ ] Visualizer can stop without affecting Core
- [ ] no direct SQLite access
- [ ] no arbitrary shell endpoint
- [ ] no arbitrary file-write endpoint
- [ ] frontend build contains no secrets
- [ ] third-party asset licenses recorded
- [ ] dependency lockfile committed
- [ ] development controls do not become production execution controls

## 28. Security Review Triggers

Require new review for:

- remote/LAN access
- browser-to-Core commands
- authentication
- user accounts
- cloud sync
- provider API calls
- filesystem browser
- prompt transcript visualization
- file content visualization
- Electron shell
- plugins
- remote deployment

## 29. Security Invariant

> Compromising or misusing the Visualizer should not provide control over JORE Core.

The Visualizer may observe intentionally exposed local runtime metadata.

It must not become an orchestration privilege boundary.
