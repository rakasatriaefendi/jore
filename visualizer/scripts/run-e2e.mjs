import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createServer, preview } from 'vite';

const mode = process.argv[2];
if (mode !== 'production' && mode !== 'development') {
  throw new Error('Expected production or development E2E mode');
}

const root = fileURLToPath(new URL('../', import.meta.url));
const playwrightCli = fileURLToPath(
  new URL('../node_modules/@playwright/test/cli.js', import.meta.url),
);
let server;
let runner;

function stopRunner() {
  runner?.kill();
}

process.once('SIGINT', stopRunner);
process.once('SIGTERM', stopRunner);

try {
  server =
    mode === 'development'
      ? await createServer({
          root,
          server: { host: '127.0.0.1', port: 5174, strictPort: true },
        })
      : await preview({ root });
  if (mode === 'development') await server.listen();

  const result = await new Promise((resolve, reject) => {
    runner = spawn(process.execPath, [playwrightCli, 'test'], {
      cwd: root,
      env: { ...process.env, JORE_E2E_MODE: mode },
      stdio: 'inherit',
    });
    runner.once('error', reject);
    runner.once('exit', (code) => resolve(code ?? 1));
  });
  process.exitCode = result;
} catch (error) {
  console.error(error);
  process.exitCode = 1;
} finally {
  process.removeListener('SIGINT', stopRunner);
  process.removeListener('SIGTERM', stopRunner);
  await server?.close();
}
