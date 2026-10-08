# JORE Visualizer v1.13 — PLANNING

**Branch:** `feat/visualizer-v1.13`
**Stable baseline:** `main` / `v1.12.6`
**Frontend development:** Windows + VSCode + Codex
**Core runtime:** WSL AgentHub

## 1. Principles

1. Protect the v1.12.6 baseline.
2. Keep Visualizer optional.
3. Build event behavior before visual polish.
4. Use placeholders before final assets.
5. Keep the browser read-only.
6. Never duplicate orchestration logic in TypeScript.
7. Keep one repository.
8. Use small, reviewable increments.
9. Validate every phase before continuing.

## 2. Workspace Strategy

Recommended:

```text
WSL
~/projects/jore
└── Core/reference/runtime testing

Windows
D:\AgentHub\jore
└── VSCode + Codex + Visualizer development
```

Both clones use the same GitHub repository.

Do not edit the same branch concurrently without fetch/pull synchronization.

## 3. Phase V0 — Scaffold

Goal: smallest working Visualizer.

Tasks:

- create `visualizer/`
- Vite + React + TypeScript
- install Three.js, R3F, Drei, Zustand
- ESLint + Prettier
- Vitest + Playwright
- initial folder structure
- empty R3F canvas
- basic header
- error boundary

Gate:

- dev server works
- canvas renders
- build passes
- lint passes
- first unit test passes

Do not modify Core.

## 4. Phase V1 — Office Prototype

Build with primitives first:

- floor
- walls
- five desks
- chairs
- monitors
- whiteboard
- cabinet/archive area
- supervisor area

Add:

- perspective camera
- orbit
- pan
- zoom
- reset

Gate: room is readable without GLB assets.

## 5. Phase V2 — Placeholder Agents

Create simple primitive avatars for:

- Supervisor
- Frontend
- Backend
- Documentation
- Reviewer

Add:

- labels
- workstation binding
- role registry
- role accents
- selection
- selected-agent panel

Gate: all five roles are visible and selectable.

## 6. Phase V3 — Mock State Machine

Implement:

```text
idle
assigned
walking
working
waiting
reviewing
success
error
```

Create development-only mock controls.

Flow:

```text
Mock Event
→ EventRouter
→ Store
→ Avatar
→ UI
```

Gate: every visual state can be triggered without JORE Core.

## 7. Phase V4 — Visual Event Protocol v1

Create `docs/visualizer/EVENT_PROTOCOL_V1.md`.

Define:

- envelope
- schema ID
- event IDs
- timestamps
- project/run/agent context
- payload rules
- malformed/unknown event behavior
- sensitive-data exclusions
- forward compatibility

Initial events:

```text
project.created
project.opened
project.closed
run.started
run.completed
run.failed
agent.assigned
agent.started
agent.waiting
agent.completed
agent.failed
review.started
review.passed
review.rejected
file.changed
error.created
connection.ready
```

Gate: protocol can be implemented without importing internal Python objects into the frontend.

## 8. Phase V5 — Core Event Bridge

Only now touch Core.

Suggested Core responsibilities:

```text
VisualEvent
VisualEventSanitizer
VisualEventEmitter
VisualEventBridge
```

Requirements:

- optional
- local-only by default
- `jore.visual.v1`
- sanitized payloads
- Core works when bridge is disabled
- bridge failure never fails a run

Gate: browser receives a valid test event.

## 9. Phase V6 — Real Runtime Integration

Map real lifecycle events:

- run start/complete/fail
- agent start/wait/complete/fail
- review start/pass/reject
- file changed where safe

Gate: a real JORE run drives the placeholder scene correctly.

## 10. Phase V7 — Asset Pipeline

Create:

```text
visualizer/ASSET_LICENSES.md
visualizer/src/assets/assetManifest.ts
```

For each asset:

1. verify license
2. record author/source
3. inspect
4. normalize scale
5. normalize pivot
6. optimize textures
7. clean mesh/materials
8. export GLB
9. register
10. test production build

Gate: no unknown-license asset enters the repository.

## 11. Phase V8 — Avatar Pass

Prefer:

- one base rig
- one uniform
- role variants
- lightweight accessories

Gate:

- roles are distinguishable
- role identity is not color-only
- shared rig/material architecture remains manageable

## 12. Phase V9 — Animation

Required:

- Idle
- Walk
- Work
- Success
- Error

Optional:

- Reviewing
- Waiting
- Reading

Gate:

- smooth enough transitions
- no mixer leaks
- no repeated action accumulation
- store state remains authoritative

## 13. Phase V10 — UI Polish

Add:

- project name
- run state
- connection status
- selected agent panel
- status legend
- loading state
- empty state
- offline/reconnecting state
- camera reset
- error overlay

Gate: user can understand the scene without developer logs.

## 14. Phase V11 — Resilience / Security Gate

Test:

- invalid event
- unknown event
- duplicate event
- Core unavailable
- Visualizer starts first
- Visualizer starts late
- disconnect
- reconnect
- browser refresh
- browser closes during run
- non-critical asset failure
- oversized payload handling
- sensitive field exclusion
- local binding

Gate: none of these breaks JORE Core.

## 15. Phase V12 — Performance Gate

Test:

- five avatars
- labels/status active
- event bursts
- long session
- reconnect cycles

Targets:

- target 60 FPS
- acceptable >= 30 FPS
- no uncontrolled memory growth
- no repeated asset loads
- no excessive draw calls

## 16. Phase V13 — Release Gate

Before `v1.13.0`:

- [ ] PRD acceptance criteria complete
- [ ] frontend build passes
- [ ] lint passes
- [ ] unit tests pass
- [ ] Playwright smoke passes
- [ ] affected Core tests pass
- [ ] Core works without Visualizer
- [ ] real run demonstrated
- [ ] disconnect/reconnect demonstrated
- [ ] asset licenses complete
- [ ] frontend secret scan clean
- [ ] security review complete
- [ ] docs updated
- [ ] release notes prepared

## 17. Codex Task Strategy

Give Codex narrow tasks.

Good:

```text
Implement Phase V0 only.
Do not edit src/agenthub.
Create the Vite React TypeScript scaffold under visualizer/.
Add R3F, Drei and Zustand.
Stop after build, lint and tests pass.
```

Avoid:

```text
Build the whole JORE Visualizer.
```

## 18. Commit Strategy

Examples:

```text
visualizer: scaffold Vite React TypeScript app
visualizer: add office prototype scene
visualizer: add placeholder agent registry
visualizer: add mock agent state machine
docs: define visual event protocol v1
core: add optional local visual event bridge
visualizer: connect runtime event client
visualizer: add MVP office assets
visualizer: add agent animation controller
visualizer: add connection resilience UI
```

Avoid giant commits.

## 19. Stop Conditions

Stop and review if:

- Visualizer wants direct SQLite access
- browser needs provider credentials
- TypeScript duplicates workflow rules
- bridge changes Core execution semantics
- asset work blocks protocol work
- scope expands into game mechanics
- dependency licensing is unclear
- v1.12 stable behavior is modified unnecessarily

## 20. Completion Statement

The MVP is complete when a real JORE workflow can be observed in the Windows browser as a live, read-only 3D office representation while the authoritative workflow continues independently in WSL.
