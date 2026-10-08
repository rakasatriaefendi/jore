# JORE Visualizer v1.13 — PRD

**Product:** JORE
**Component:** JORE Visualizer
**Target:** v1.13.x
**Core baseline:** JORE v1.12.6 Stable Beta
**Development environment:** Windows + VSCode + Codex
**Runtime split:** JORE Core in WSL, Visualizer in Windows browser

## 1. Product Summary

JORE Visualizer is an optional 3D sidecar that displays JORE runtime activity as a stylized office. It visualizes projects, agents, tasks, review activity, file activity, errors, run lifecycle, and connection state.

The Visualizer is not an orchestration engine. JORE Core remains authoritative.

Initial MVP roles:

- Supervisor
- Frontend
- Backend
- Documentation
- Reviewer

Each role is represented by a simple low-poly humanoid avatar with a shared uniform system and role-specific accents.

## 2. Product Vision

Visual metaphor:

- Project = room
- Team = occupants
- Agent = avatar
- Workstation = agent role
- Task = visible work activity
- File = document/object
- Review = review activity
- Error = warning state
- Completed run = settled room state

Future versions may expand to multiple rooms, floors, buildings, richer teams, and more expressive agent behavior.

## 3. Goals

Primary goals:

1. Show what project is active.
2. Show whether a run is active.
3. Show which agent is working.
4. Show which agent is waiting.
5. Show review activity.
6. Show success and failure states.
7. Show connection status between Visualizer and Core.

Secondary goals:

- Establish a strong visual identity for JORE.
- Define a reusable Visual Event Protocol.
- Keep the 3D layer independent from orchestration logic.
- Build a foundation for future multi-room visualization.

## 4. Non-Goals

Out of scope for v1.13 MVP:

- replacing the JORE TUI
- running Codex/OpenCode from the Visualizer
- direct provider credential access
- direct SQLite access
- arbitrary shell execution
- arbitrary filesystem mutation
- project editing from the room
- multiplayer
- voice/lip sync
- VR/AR
- realistic humans
- heavy physics
- free-roaming user avatar
- multi-building world
- Electron packaging
- provider API calls from the browser

## 5. Platform Model

### Windows

Runs:

- VSCode
- Codex
- Node.js
- Vite
- browser
- Three.js Visualizer

### WSL AgentHub

Runs:

- JORE Core
- Python runtime
- OpenCode/Codex integration
- SQLite
- RunState
- project runtime
- agent orchestration
- Visual Event Bridge

## 6. Architecture

```text
Windows
└── JORE Visualizer
    ├── React
    ├── TypeScript
    ├── Three.js
    ├── @react-three/fiber
    └── Zustand
          │
          │ localhost WebSocket
          ▼
WSL
└── JORE Core
    ├── Project Runtime
    ├── Agents
    ├── Reviewer
    ├── RunState
    ├── SQLite
    └── Visual Event Bridge
```

The Visualizer is a read-only projection of sanitized Core events.

## 7. Recommended Stack

Required:

- Node.js LTS
- Vite
- TypeScript
- React
- Three.js
- `@react-three/fiber`
- `@react-three/drei`
- Zustand
- Native WebSocket
- ESLint
- Prettier
- Vitest
- Playwright

Optional after the foundation is stable:

- `@react-three/uikit`
- `gltfjsx`
- `ecctrl`

Initial dependency set should stay small:

```text
react
react-dom
three
@react-three/fiber
@react-three/drei
zustand
```

## 8. Repository Structure

```text
jore/
├── src/
│   └── agenthub/
├── docs/
│   └── visualizer/
│       ├── PRD.md
│       ├── PLANNING.md
│       ├── AGENTS.md
│       ├── SECURITY.md
│       ├── EVENT_PROTOCOL_V1.md
│       ├── ASSET_GUIDE.md
│       └── ARCHITECTURE.md
├── visualizer/
│   ├── public/
│   │   ├── models/
│   │   │   ├── agents/
│   │   │   ├── furniture/
│   │   │   ├── office/
│   │   │   └── props/
│   │   ├── animations/
│   │   ├── textures/
│   │   └── icons/
│   ├── src/
│   │   ├── app/
│   │   ├── scene/
│   │   ├── agents/
│   │   ├── environment/
│   │   ├── assets/
│   │   ├── events/
│   │   ├── state/
│   │   ├── ui/
│   │   ├── animation/
│   │   ├── camera/
│   │   ├── debug/
│   │   ├── config/
│   │   ├── types/
│   │   ├── utils/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tests/
│   │   ├── unit/
│   │   └── e2e/
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── pyproject.toml
├── release.json
├── README.md
└── LICENSE
```

## 9. Folder Responsibilities

### `app/`
Bootstrap, top-level composition, error boundary, connection lifecycle.

### `scene/`
Office scene composition, lighting, environment, ground, visual effects.

### `agents/`
Avatar components, role registry, workstation binding, labels, status indicators.

Suggested layout:

```text
agents/
├── AgentAvatar.tsx
├── AgentRegistry.ts
├── AgentLabel.tsx
├── AgentStatusIndicator.tsx
├── AgentWorkstation.tsx
├── roles/
│   ├── SupervisorAgent.tsx
│   ├── FrontendAgent.tsx
│   ├── BackendAgent.tsx
│   ├── DocumentationAgent.tsx
│   └── ReviewerAgent.tsx
└── hooks/
    ├── useAgentAnimation.ts
    ├── useAgentMovement.ts
    └── useAgentStatus.ts
```

### `events/`
Transport, parsing, validation, routing, reconnect.

### `state/`
Connection, project, run, agents, and visualizer preference state.

### `assets/`
Asset registry, manifest, loader metadata, preloading.

### `ui/`
HTML/spatial UI overlays.

### `debug/`
Development-only mock events and scene/state inspection.

## 10. Agent Roles

```ts
type AgentRole =
  | "supervisor"
  | "frontend"
  | "backend"
  | "documentation"
  | "reviewer"
```

## 11. Agent Visual States

```ts
type AgentVisualState =
  | "idle"
  | "assigned"
  | "walking"
  | "working"
  | "waiting"
  | "reviewing"
  | "success"
  | "error"
```

The state is derived from JORE Visual Events, never from browser-side orchestration decisions.

## 12. Visual Event Protocol

Transport:

```text
ws://127.0.0.1:<port>/events
```

Initial envelope:

```json
{
  "schema": "jore.visual.v1",
  "event_id": "evt_123",
  "timestamp": "2026-10-06T12:00:00Z",
  "project_id": "project_abc",
  "run_id": "run_xyz",
  "type": "agent.started",
  "payload": {}
}
```

Required:

- `schema`
- `event_id`
- `timestamp`
- `type`

Optional context:

- `project_id`
- `run_id`
- `agent_id`
- `attempt_id`

Initial event families:

```text
project.*
run.*
agent.*
review.*
file.*
error.*
connection.*
```

Initial concrete events:

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

## 13. Data Flow

```text
JORE Core
→ Sanitized Visual Event
→ Local WebSocket
→ EventClient
→ Schema Validation
→ EventRouter
→ Zustand Store
→ React
→ React Three Fiber
→ Three.js
```

Three.js objects are not the source of truth.

## 14. MVP Office Layout

One room only:

```text
┌────────────────────────────────────────────┐
│       Supervisor Desk       Whiteboard     │
│                                            │
│ Frontend Desk          Backend Desk        │
│                                            │
│ Documentation Desk     Reviewer Desk       │
│                                            │
│ Cabinet     File Rack       Archive        │
│                                            │
│                  Entry                     │
└────────────────────────────────────────────┘
```

Each agent has a clearly identifiable workstation.

## 15. Asset Style

Use:

- stylized low-poly
- clean silhouettes
- lightweight GLB
- simple PBR
- limited texture count
- role-readable uniforms

Avoid:

- photorealism
- huge textures
- expensive hair/cloth
- unnecessary props
- heavy post-processing

## 16. Avatar Asset Plan

Prefer:

```text
1 base humanoid
1 skeleton/rig
1 base uniform
5 role material variants
3–5 optional accessories
```

Role distinction:

- Supervisor: distinct trim/badge, optional tablet
- Frontend: blue/cyan accent, UI badge
- Backend: green accent, terminal/server badge
- Documentation: warm accent, notebook/folder
- Reviewer: red/purple accent, checklist

Do not rely on color alone.

## 17. Animation Plan

MVP priority:

1. Idle
2. Walk
3. Work
4. Success
5. Error

Later:

- reviewing
- reading
- waiting/look-around
- celebrate

Animation polish must not block event integration.

## 18. Furniture and Prop Plan

Required:

- 5 desks
- 5 chairs
- 5 monitors
- keyboards
- desktop/laptop representation
- supervisor desk variation
- cabinet
- bookshelf/archive shelf
- document box
- file stack
- folder
- whiteboard
- JORE room sign

Optional decorative props:

- wall clock
- plant
- trash bin

## 19. Asset Directory Convention

```text
public/models/
├── agents/
│   ├── base-agent.glb
│   └── accessories/
├── furniture/
│   ├── desk.glb
│   ├── chair.glb
│   ├── monitor.glb
│   └── cabinet.glb
├── office/
│   ├── office-room.glb
│   ├── floor.glb
│   └── wall.glb
└── props/
    ├── folder.glb
    ├── document-stack.glb
    ├── whiteboard.glb
    └── archive-box.glb

public/animations/
├── idle.glb
├── walk.glb
├── work.glb
├── success.glb
└── error.glb
```

## 20. Asset Manifest

Asset paths must be centralized.

Example:

```ts
export const assets = {
  agents: {
    base: "/models/agents/base-agent.glb",
  },
  furniture: {
    desk: "/models/furniture/desk.glb",
    chair: "/models/furniture/chair.glb",
    monitor: "/models/furniture/monitor.glb",
  },
  props: {
    folder: "/models/props/folder.glb",
    documents: "/models/props/document-stack.glb",
  },
}
```

## 21. Asset Pipeline

```text
source
→ license verification
→ inspection
→ scale normalization
→ pivot normalization
→ texture reduction
→ mesh/material cleanup
→ compression
→ GLB export
→ gltfjsx where useful
→ JORE asset registry
```

Every third-party asset must have provenance and license documentation.

## 22. UI Overlay

Use HTML for primary information.

Display:

- JORE Visualizer title
- connection state
- project
- run state
- selected agent
- selected agent state/task
- reset camera
- error/offline state

Raw prompts and secrets must not be shown by default.

## 23. Visual Language

Base:

- dark neutral environment
- pink JORE accent
- white
- gray
- limited semantic status colors

Pink is used for branding, selection, active highlights, and subtle room accents—not the entire environment.

## 24. Camera

MVP:

- perspective camera
- 3/4 office overview
- orbit
- pan
- zoom
- reset
- focus selected agent

No first-person camera.

## 25. Status Visualization

Use more than color.

| State | Animation | Indicator |
|---|---|---|
| Idle | idle | gray dot |
| Assigned | acknowledge | task icon |
| Working | work/typing | active indicator |
| Waiting | idle/look | pause |
| Reviewing | reading/checking | checklist |
| Success | success | check |
| Error | error/confused | warning |

## 26. File Activity

`file.changed` should expose sanitized display information.

Example:

```json
{
  "type": "file.changed",
  "payload": {
    "agent_id": "frontend",
    "operation": "modified",
    "display_name": "App.tsx"
  }
}
```

Avoid exposing sensitive full paths by default.

## 27. Connection Behavior

States:

```text
CONNECTED
RECONNECTING
OFFLINE
```

On disconnect:

- keep scene visible
- stop applying new events
- show reconnect status
- retry with bounded backoff
- do not reload the page
- do not affect JORE Core

## 28. Security Requirements

MVP is read-only.

Bridge binds locally by default:

```text
127.0.0.1
```

Do not expose by default on:

```text
0.0.0.0
```

Never send:

- API keys
- OAuth tokens
- provider tokens
- cookies
- passwords
- full environment dumps
- credential files
- secret file content

Visualizer must not expose shell, arbitrary file write/delete, provider execution, or database mutation.

See `SECURITY.md`.

## 29. Performance Targets

Initial targets:

- target 60 FPS on normal desktop
- acceptable minimum 30 FPS
- 5 avatars
- modest lighting
- target draw calls below ~150
- textures generally <= 1024px unless justified
- avoid unnecessary real-time shadows

## 30. Testing

Unit:

- event parsing
- event routing
- state transitions
- reconnect policy
- asset manifest integrity

Integration:

- mock event → store → rendered state
- malformed event rejection
- reconnect lifecycle

E2E:

- page loads
- canvas exists
- no fatal console errors
- mock mode works
- connection status visible
- selected agent UI works

## 31. MVP Acceptance Criteria

- [ ] JORE TUI works without Visualizer.
- [ ] Visualizer runs in Windows browser.
- [ ] JORE Core remains in WSL.
- [ ] Visualizer connects through local WebSocket.
- [ ] Visualizer is read-only.
- [ ] One office room exists.
- [ ] Five role agents are visible.
- [ ] Five workstations are visible.
- [ ] Basic office furniture exists.
- [ ] Idle state works.
- [ ] Working state works.
- [ ] Waiting state works.
- [ ] Review state works.
- [ ] Success state works.
- [ ] Error state works.
- [ ] Run start is visible.
- [ ] Run completion is visible.
- [ ] Disconnect does not crash the app.
- [ ] Reconnect works.
- [ ] Camera controls work.
- [ ] Selected agent panel works.
- [ ] build passes.
- [ ] lint passes.
- [ ] unit tests pass.
- [ ] Playwright smoke test passes.
- [ ] asset licenses are documented.
- [ ] no secrets are bundled into frontend artifacts.

## 32. Definition of Done

> A real JORE workflow can be watched inside a simple 3D office, with each configured role represented by an avatar whose visible state follows actual sanitized JORE runtime events, while JORE Core remains fully functional without the Visualizer.

## 33. Development Order

```text
Architecture
→ Scaffold
→ Empty office
→ Placeholder agents
→ Mock event state machine
→ Visual Event Protocol
→ WebSocket bridge
→ Real JORE integration
→ GLB assets
→ Animation
→ Polish
```

Functionality comes before cosmetic detail.

## 34. Reference Projects

Use as references, not as wholesale dependencies or architecture copies:

- Three.js official docs/examples
- `pmndrs/react-three-fiber`
- `pmndrs/drei`
- `pmndrs/uikit`
- `pmndrs/gltfjsx`
- `donmccurdy/three-gltf-viewer`
- `KhronosGroup/glTF-Sample-Assets`
- `heagandev/threejs-agent-starter`
- `nirholas/three.ws`
- `VerseEngine/three-avatar`
