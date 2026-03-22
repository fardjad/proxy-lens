import type { BodyPreview } from './types'

const TEXT_PREFIXES = ['text/']
const TEXT_TYPES = new Set([
  'application/json',
  'application/xml',
  'application/javascript',
  'application/x-www-form-urlencoded',
  'image/svg+xml',
])

function normalizeContentType(contentType: string | null | undefined) {
  return contentType?.split(';', 1)[0].trim().toLowerCase() ?? null
}

export function isTextLikeContentType(contentType: string | null | undefined) {
  const normalized = normalizeContentType(contentType)

  if (!normalized) {
    return false
  }

  if (TEXT_TYPES.has(normalized)) {
    return true
  }

  return TEXT_PREFIXES.some((prefix) => normalized.startsWith(prefix))
}

export function decodeBodyPreview(
  bytes: Uint8Array,
  contentType: string | null | undefined,
): BodyPreview {
  const shouldTryUtf8 = isTextLikeContentType(contentType) || bytes.length < 4_096

  if (!shouldTryUtf8) {
    return { kind: 'binary' }
  }

  try {
    const decoder = new TextDecoder('utf-8', { fatal: true })
    return { kind: 'text', text: decoder.decode(bytes) }
  } catch {
    return { kind: 'binary' }
  }
}
