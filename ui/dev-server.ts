import { join, normalize } from 'node:path'
import indexHtml from './index.html'

const DEFAULT_SERVER_TARGET = 'http://127.0.0.1:8000'
const DEV_PROXY_PREFIX = '/__proxylens'
const DIST_MODE = process.argv.includes('--dist')
const HOST = process.env.HOST ?? '127.0.0.1'
const PORT = Number(process.env.PORT ?? '3000')
const ROOT_DIR = import.meta.dir
const STATIC_DIR = join(ROOT_DIR, DIST_MODE ? 'dist' : 'public')
const proxyTarget =
  process.env.PUBLIC_PROXYLENS_BASE_URL?.trim() || DEFAULT_SERVER_TARGET
const routes = DIST_MODE ? undefined : { '/': indexHtml }
const runtimeConfigBody = `window.__PROXYLENS_CONFIG__ = ${JSON.stringify({
  apiBaseUrl: DIST_MODE ? proxyTarget : DEV_PROXY_PREFIX,
})};\n`

function resolveStaticPath(pathname: string) {
  const safePath = normalize(decodeURIComponent(pathname))
    .replace(/^[/\\]+/, '')
    .replace(/^(\.\.(\/|\\|$))+/, '')
  return join(STATIC_DIR, safePath)
}

async function serveStatic(pathname: string) {
  const filePath = resolveStaticPath(pathname)
  const file = Bun.file(filePath)

  if (!(await file.exists())) {
    return null
  }

  return new Response(file)
}

async function proxyRequest(request: Request) {
  const url = new URL(request.url)
  const upstreamUrl = new URL(
    `${url.pathname.slice(DEV_PROXY_PREFIX.length) || '/'}${url.search}`,
    proxyTarget,
  )
  const headers = new Headers(request.headers)
  headers.delete('host')

  return fetch(upstreamUrl, {
    method: request.method,
    headers,
    body:
      request.method === 'GET' || request.method === 'HEAD'
        ? undefined
        : request.body,
    redirect: 'manual',
  })
}

const server = Bun.serve({
  development: !DIST_MODE,
  hostname: HOST,
  port: PORT,
  routes,
  async fetch(request) {
    const { pathname } = new URL(request.url)

    if (pathname === '/runtime-config.js') {
      return new Response(runtimeConfigBody, {
        headers: { 'content-type': 'application/javascript; charset=utf-8' },
      })
    }

    if (pathname.startsWith(DEV_PROXY_PREFIX)) {
      return proxyRequest(request)
    }

    const staticResponse = await serveStatic(pathname)
    if (staticResponse) {
      return staticResponse
    }

    if (DIST_MODE) {
      return new Response(Bun.file(join(STATIC_DIR, 'index.html')))
    }

    return new Response('Not found', { status: 404 })
  },
})

console.log(`ProxyLens UI listening on ${server.url}`)
