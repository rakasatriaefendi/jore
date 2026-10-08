# JORE Visualizer — Phase V1

Optional, read-only browser sidecar for JORE v1.13 development. JORE Core stays
in WSL on the v1.12.6 baseline and runs independently of this frontend.

V1 contains an HTML header, a dark React Three Fiber office built from primitive
geometry, five labeled workstations, an entrance, wall whiteboard, archive area,
and a controlled fatal-error fallback. The camera supports bounded orbit, pan,
zoom, and a Reset View button. The static scene renders on demand. There are no
downloaded assets, avatars, physics, event protocol, WebSocket client, or Core
communication. Zustand is installed as required by the stack; no store is needed
for this static scene.

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
and use Reset View to restore the office overview.
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
```

- `build` type-checks source, tests, and configuration before creating `dist/`.
- `lint` checks TypeScript and React rules and treats warnings as failures.
- `format` applies Prettier; `format:check` checks without writing.
- `test` runs the Vitest error-boundary tests using jsdom. `test:watch` watches.
- `test:e2e` builds and starts a dedicated production preview on port 4173, then
  checks the header, root, live WebGL context, five workstation labels, Reset View,
  and absence of browser errors. It saves a scene screenshot under ignored
  `test-results/` and stops the server.
- `preview` serves a previously built `dist/` on <http://127.0.0.1:4173>.

Playwright needs its matching Chromium browser. If it reports a missing browser,
explicitly install it with `npx.cmd playwright install chromium`, then rerun the
smoke test. This downloads a browser to Playwright's per-user cache; no browser
installation runs automatically in npm scripts. No system-wide dependencies or
PowerShell execution-policy changes are needed. Ports 5173 and 4173 must be free.

## Structure

```text
public/          Reserved for reviewed local assets; empty in V0
src/app/         Bootstrap styling and application error boundary
src/scene/       Canvas, shared primitives, and office composition
src/ui/          HTML header, camera reset, and fatal-error display
src/agents/      Reserved
src/environment/ Room shell, reusable workstation, and fixtures
src/assets/      Reserved
src/events/      Reserved
src/state/       Reserved; no speculative state
src/animation/   Reserved
src/camera/      Orbit controls and reset behavior
src/debug/       Reserved
src/config/      Reserved
src/types/       Reserved
src/utils/       Reserved
tests/unit/      Fatal-error behavior tests
tests/e2e/       Production browser smoke test
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

The documents' content and `src/agenthub/**` are unchanged. Work stops at Phase V1.
