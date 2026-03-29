import { cp, mkdir, rm, writeFile } from 'node:fs/promises'

const DEFAULT_SERVER_TARGET = 'http://127.0.0.1:8000'
const proxyTarget =
  process.env.PUBLIC_PROXYLENS_BASE_URL?.trim() || DEFAULT_SERVER_TARGET

await rm(new URL('./dist', import.meta.url), { force: true, recursive: true })
await mkdir(new URL('./dist/public', import.meta.url), { recursive: true })
await cp(
  new URL('./public', import.meta.url),
  new URL('./dist/public', import.meta.url),
  {
    force: true,
    recursive: true,
  },
)
await writeFile(
  new URL('./dist/runtime-config.js', import.meta.url),
  `window.__PROXYLENS_CONFIG__ = ${JSON.stringify({
    apiBaseUrl: proxyTarget,
  })};\n`,
)

const build = Bun.spawn(
  ['bun', 'build', './index.html', '--outdir', './dist'],
  {
    cwd: import.meta.dir,
    stdout: 'inherit',
    stderr: 'inherit',
  },
)

const exitCode = await build.exited

if (exitCode !== 0) {
  process.exit(exitCode)
}
