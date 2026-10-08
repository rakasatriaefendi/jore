# AGENTS.md — JORE Visualizer Development Rules

This file defines rules for AI coding agents working on JORE Visualizer.

## 1. Product Context

JORE is an AI terminal companion and multi-agent orchestrator.

Stable baseline: JORE v1.12.6.
Visualizer line: v1.13.x.

Architecture:

```text
JORE Core
→ Python
→ WSL
→ authoritative orchestration state

JORE Visualizer
→ React + TypeScript + Three.js
→ Windows browser
→ read-only visualization
```

The Visualizer is optional.

JORE Core must keep working when the Visualizer is absent, disconnected, closed, or broken.

## 2. Primary Rule

Do not move orchestration authority into the Visualizer.

The browser is a presentation client.

It may render sanitized JORE events.

It must not become a second JORE runtime.

## 3. Preferred Work Areas

During Visualizer tasks, prefer:

```text
visualizer/**
docs/visualizer/**
```

Changes inside:

```text
src/agenthub/**
```

require an explicit Core-integration task.

Do not modify Core merely to simplify frontend implementation.

## 4. Technology Direction

Preferred stack:

- React
- TypeScript
- Vite
- Three.js
- `@react-three/fiber`
- `@react-three/drei`
- Zustand
- Native WebSocket
- Vitest
- Playwright

Do not replace the stack without explicit approval.

Avoid large frameworks for problems already solved by the existing stack.

## 5. Architecture Rule

Maintain this flow:

```text
Core Event
→ EventClient
→ Schema Validation
→ EventRouter
→ State Store
→ React
→ React Three Fiber
→ Three.js
```

Do not mutate arbitrary Three.js objects directly from WebSocket callbacks.

Three.js objects must not become authoritative application state.

## 6. Core / Visualizer Boundary

The Visualizer must not:

- read JORE SQLite directly
- write JORE SQLite
- access raw provider credentials
- access Codex/OpenCode credential stores
- execute arbitrary shell commands
- write arbitrary project files
- delete arbitrary project files
- start providers directly
- decide supervisor actions
- decide reviewer policy
- decide retry/escalation policy
- modify RunState

If a requested feature requires one of these, stop and report the architectural conflict.

## 7. Visual Event Protocol

Use a versioned protocol.

Target schema:

```text
jore.visual.v1
```

Do not serialize internal Python objects directly into the browser.

Do not expose internal fields merely because they exist.

Unknown events must not crash the client.

Malformed events must be rejected safely.

## 8. Security Rule

Assume every browser-visible value can be inspected in developer tools.

Never emit:

- API keys
- access tokens
- refresh tokens
- cookies
- passwords
- authorization headers
- credential-store contents
- SSH private keys
- `.env` contents
- full process environments
- secret file contents

See `SECURITY.md`.

## 9. Network Rule

Visual Event Bridge is local-only by default.

Prefer:

```text
127.0.0.1
```

Do not change default binding to:

```text
0.0.0.0
```

without explicit approval and security review.

## 10. Scene Rule

The scene exists to communicate runtime state.

Readability beats realism.

Prefer:

- low-poly
- clean silhouette
- simple PBR
- stable frame rate
- reusable geometry
- reusable materials

Avoid:

- photorealism
- expensive post-processing
- unnecessary particles
- heavy physics
- giant textures

## 11. Avatar Rule

MVP roles:

- Supervisor
- Frontend
- Backend
- Documentation
- Reviewer

Prefer one shared humanoid rig and shared animation system.

Differentiate roles using:

- accent
- badge
- accessory
- label

Do not rely on color alone.

Do not introduce five unrelated rigs without a concrete reason.

## 12. Animation Rule

Initial priority:

1. Idle
2. Walk
3. Work
4. Success
5. Error

Animation must reflect store state.

Avoid:

- new `AnimationMixer` per render
- action accumulation
- unnecessary animation restarts
- transport logic inside animation code

## 13. Asset Rule

All runtime asset paths must go through an asset registry/manifest.

Do not scatter raw `/models/...` strings through components.

Every third-party asset requires:

- source
- author
- license
- original filename
- JORE filename
- modifications

Unknown-license assets must not be committed.

## 14. Folder Responsibility

```text
scene/
→ scene composition

agents/
→ avatar representation

events/
→ transport + event routing

state/
→ semantic visual state

assets/
→ registry + loading metadata

ui/
→ UI overlays

animation/
→ animation logic

debug/
→ development-only tools
```

Do not create a giant all-purpose `Scene.tsx`.

## 15. State Management

Use semantic stores for:

- connection
- project
- run
- agents
- visualizer preferences

Avoid duplicate sources of truth.

Derived values should remain derived where practical.

## 16. Error Handling

Do not silently swallow fatal initialization errors.

Recoverable errors should:

- show a controlled fallback
- provide useful development diagnostics
- keep JORE Core unaffected

Browser must survive:

- Core unavailable
- WebSocket disconnect
- malformed event
- unknown event
- non-critical asset failure

## 17. Development Order

Follow:

```text
scaffold
→ room primitives
→ placeholder agents
→ mock state machine
→ event protocol
→ bridge
→ real events
→ final assets
→ animation
→ polish
```

Do not jump to final assets before event behavior works.

## 18. Testing Rule

Every behavior change should have the smallest relevant automated test.

For event changes, test:

- valid parse
- malformed parse
- routing
- state update

For store changes, test state transitions.

For user-visible flows, update Playwright where appropriate.

Do not rely only on manual browser observation.

## 19. Performance Rule

Watch for:

- repeated GLB loads
- duplicated geometry
- duplicated materials
- excessive shadows
- excessive lights
- React render loops
- allocations every frame
- event-handler leaks
- animation-mixer leaks

Use `useFrame` only when frame-by-frame work is required.

## 20. Accessibility / Readability

Runtime state must not use color as the only signal.

Use combinations of:

- text
- icon
- animation
- color

Keep labels readable at the default camera distance.

## 21. Codex Task Behavior

For bounded tasks:

1. Inspect existing architecture first.
2. Modify only relevant areas.
3. Preserve stable behavior.
4. Run relevant checks.
5. Summarize changed files.
6. Report unresolved risks.
7. Stop at the requested boundary.

Do not opportunistically refactor unrelated Core code.

## 22. No Hidden Scope Expansion

Do not add unless explicitly requested:

- multiplayer
- Electron
- VR
- voice
- AI chat inside Visualizer
- provider execution
- free-roaming player
- advanced physics
- multiple buildings
- procedural world
- cloud backend
- user accounts
- telemetry

## 23. Documentation Rule

If a change alters:

- event schema
- security boundary
- folder responsibility
- asset rules
- lifecycle behavior

update the corresponding Visualizer documentation in the same change.

## 24. Definition of Correctness

A Visualizer feature is correct only if:

1. it accurately represents Core state,
2. it does not become authoritative,
3. it fails without breaking Core,
4. it respects security boundaries,
5. it remains understandable to the user.

## 25. Final Guardrail

When uncertain whether logic belongs in Core or Visualizer:

- workflow truth belongs in Core
- visual interpretation belongs in Visualizer

If the browser can change the outcome of a JORE run, the design probably crossed the boundary.
