# JORE Visualizer — Phase V3

Optional, read-only browser sidecar for JORE v1.13 development. JORE Core stays
in WSL on the v1.12.6 baseline and runs independently of this frontend.

V3 contains an HTML header, a dark React Three Fiber office built from primitive
geometry, five workstations, and five simple humanoid placeholders. The office
also has an entrance, wall whiteboard, archive area, and a controlled fatal-error
fallback. Each agent shares one body design and uses a role accent, badge shape,
and readable label. Clicking an agent or its label selects it and opens a small
identity panel. Each agent has one semantic visual state in a Zustand store. All
five start idle. The eight states change a static primitive pose and show a text
and symbol status near the avatar; the selected panel also shows the state. A
compact development-only mock panel can apply or reset states without Core data.
Mock state resets on refresh and is not persisted.
The camera supports bounded orbit, pan, zoom, and a Reset View button. The scene
renders on demand. There are no downloaded assets, physics, event protocol,
WebSocket client, or Core communication. The mock actions are local development
controls, not the final event format.

## Run on Windows

Use Node.js LTS (Node 22.22.2+ on the 22.x line, or 24.15.0+ on the 24.x line)
and npm. Development was validated with Node 22.23.2 and npm 10.9.8.
From PowerShell at the repository root:

```powershell
cd visualizer
npm.cmd ci
npm.cmd run dev
```

Open <http://127.0.0.1:5173>. Drag to orbit, scroll to zoom, right-drag to pan,
and use Reset View to restore the office overview. In development, use the
"Mock visual events" panel to select an agent and state, apply it, or reset one
or all agents. "Reset selected" resets the agent chosen in that panel. The panel
is absent from production builds.
WebGL2 must be available in the browser. If initialization fails, the app displays
a fallback with a reload action; development errors also appear in the console.

`npm.cmd` avoids PowerShell execution-policy restrictions on `npm.ps1` without
changing system policy. Other shells can use `npm` normally. No WSL or Core
process is required to run the scaffold.

## Checks

```powershell
npm.cmd run build
npm.cmd run lint
npm.cmd run format:check
npm.cmd run test
npm.cmd run test:e2e
npm.cmd run test:e2e:prod
npm.cmd run test:e2e:dev
```

- `build` type-checks source, tests, and configuration before creating `dist/`.
- `lint` checks TypeScript and React rules and treats warnings as failures.
- `format` applies Prettier; `format:check` checks without writing.
- `test` runs Vitest error-boundary, registry, visual-state store, and mock UI
  tests. `test:watch` watches.
- `test:e2e` runs both production and development browser tests. The production
  mode builds and previews on port 4173, then checks the header, root, WebGL,
  idle labels, selection, camera reset, and browser errors. The development mode
  starts a dedicated Vite server on port 5174 and checks every mock state, both
  reset controls, visible labels, the selected panel, and accessible names. The test runner owns
  the Vite server and closes it after Playwright exits, including on test failure.
  Modes can also be run separately with `test:e2e:prod` and `test:e2e:dev`.
  The production smoke test saves a screenshot under ignored `test-results/`;
  neither test compares pixels.
- `preview` serves a previously built `dist/` on <http://127.0.0.1:4173>.

Playwright needs its matching Chromium browser. If it reports a missing browser,
explicitly install it with `npx.cmd playwright install chromium`, then rerun the
smoke test. This downloads a browser to Playwright's per-user cache; no browser
installation runs automatically in npm scripts. No system-wide dependencies or
PowerShell execution-policy changes are needed. Ports 4173 and 5174 must be free
for E2E; port 5173 is used only by the normal development server.
The browser runner starts Vite in its own Node process using Vite's server API;
it does not use Playwright's managed `webServer` shell command, which previously
lingered during shutdown on this Windows setup. An interrupted Node process also
releases its server socket.

## Structure

```text
public/          Reserved for reviewed local assets; empty in V0
src/app/         Bootstrap styling and application error boundary
src/agents/      Typed registry, shared avatar, badges, labels, state presentation
src/scene/       Canvas, shared primitives, and office composition
src/ui/          HTML header, office key, selected-agent panel, error display
src/environment/ Room shell, reusable workstation, and fixtures
src/assets/      Reserved
src/events/      Reserved
src/state/       Agent visual-state store
src/animation/   Reserved
src/camera/      Orbit controls and reset behavior
src/debug/       Development-only mock controls
src/config/      Reserved
src/types/       Reserved
src/utils/       Reserved
tests/unit/      Fatal-error, registry, state, and mock UI tests
tests/e2e/       Production smoke and development mock-state tests
```

Empty folders use `.gitkeep` so the requested structure survives checkout.

## Dependencies and boundaries

Runtime dependencies are limited to React, React DOM, Three.js, R3F, Drei, and
Zustand. Development dependencies provide Vite/React compilation, TypeScript
and type declarations, ESLint/React rules, Prettier, Vitest/jsdom, and Playwright.
Direct versions are pinned and `package-lock.json` records the resolved graph.
Direct package identities, repositories, licenses (MIT or Apache-2.0), and peer
ranges were checked using npm registry metadata. React/R3F pairing follows the
[R3F installation guide](https://r3f.docs.pmnd.rs/getting-started/installation).
TypeScript 6 is pinned to satisfy typescript-eslint's supported peer range.
See also [Vite's requirements](https://vite.dev/guide/).

Vite development and preview servers bind to `127.0.0.1`; development filesystem
serving is restricted to this frontend directory. Production source maps are
disabled. No provider credentials, SQLite access, shell/file endpoints,
telemetry, remote resources, or orchestration logic are included. Do not place
secrets in `VITE_*` variables. Vite's development HMR socket is tooling only.

The authoritative documents are in the canonical location:

- [PRD](../docs/visualizer/PRD.md)
- [Planning](../docs/visualizer/PLANNING.md)
- [Agent rules](../docs/visualizer/AGENTS.md)
- [Security](../docs/visualizer/SECURITY.md)

The documents' content and `src/agenthub/**` are unchanged. Work stops at Phase V3.
