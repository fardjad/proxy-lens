import type {
  HeaderPair,
  HistogramBucket,
  RequestFilters,
  RequestSummary,
  TriState,
} from './types'

export const DEFAULT_FILTERS: RequestFilters = {
  traceIds: [],
  requestIds: [],
  nodeNames: [],
  methods: [],
  urlContains: '',
  statusCodes: [],
  complete: undefined,
  requestComplete: undefined,
  responseComplete: undefined,
  limit: 1000,
  offset: 0,
}

export const COMMON_METHODS = [
  'GET',
  'POST',
  'PUT',
  'PATCH',
  'DELETE',
  'HEAD',
  'OPTIONS',
] as const

export function classNames(
  ...values: Array<string | false | null | undefined>
) {
  return values.filter(Boolean).join(' ')
}

export function compareRequestsChronologically(
  left: Pick<RequestSummary, 'captured_at' | 'request_id'>,
  right: Pick<RequestSummary, 'captured_at' | 'request_id'>,
) {
  const timestampDelta =
    new Date(left.captured_at).getTime() - new Date(right.captured_at).getTime()

  if (timestampDelta !== 0) {
    return timestampDelta
  }

  return left.request_id.localeCompare(right.request_id)
}

export function sortRequestsChronologically(requests: RequestSummary[]) {
  return [...requests].sort(compareRequestsChronologically)
}

export function headerValue(headers: HeaderPair[], name: string) {
  const normalized = name.toLowerCase()
  return headers.find(([key]) => key.toLowerCase() === normalized)?.[1] ?? null
}

export function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return '—'
  }

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
}

export function formatCount(value: number) {
  return new Intl.NumberFormat().format(value)
}

export function formatBytes(value: number) {
  if (value < 1024) {
    return `${value} B`
  }

  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`
  }

  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export function formatTriState(value: TriState) {
  if (value === true) {
    return 'Yes'
  }

  if (value === false) {
    return 'No'
  }

  return 'Any'
}

export function compactId(value: string, lead = 8, tail = 6) {
  if (value.length <= lead + tail + 1) {
    return value
  }

  return `${value.slice(0, lead)}…${value.slice(-tail)}`
}

export function displayUrl(value: string | null, fallback = 'Unknown URL') {
  if (!value) {
    return fallback
  }

  try {
    const parsed = new URL(value)
    return `${parsed.hostname}${parsed.pathname}${parsed.search}`
  } catch {
    return value
  }
}

export function requestDisplayUrl(
  request: Pick<RequestSummary, 'request_url' | 'request_headers'>,
  fallback = 'Unknown URL',
) {
  const authority = headerValue(request.request_headers, ':authority')
  const host = authority ?? headerValue(request.request_headers, 'host')

  if (!host) {
    return displayUrl(request.request_url, fallback)
  }

  if (!request.request_url) {
    return host
  }

  try {
    const parsed = new URL(request.request_url)
    return `${host}${parsed.pathname}${parsed.search}`
  } catch {
    return host
  }
}

export function requestTitle(request: RequestSummary) {
  const method = request.request_method ?? '???'
  const url = requestDisplayUrl(request)
  return `[${method} ${url}]`
}

export type RequestState =
  | 'complete'
  | 'request-open'
  | 'response-open'
  | 'websocket-open'
  | 'error'

export function getRequestState(request: RequestSummary): RequestState {
  if (request.error) {
    return 'error'
  }

  if (request.websocket_open) {
    return 'websocket-open'
  }

  if (!request.request_complete) {
    return 'request-open'
  }

  if (!request.response_complete) {
    return 'response-open'
  }

  return 'complete'
}

export function formatRequestState(state: RequestState) {
  switch (state) {
    case 'complete':
      return 'Complete'
    case 'request-open':
      return 'Request open'
    case 'response-open':
      return 'Response open'
    case 'websocket-open':
      return 'WebSocket open'
    case 'error':
      return 'Error'
  }
}

export function toggleSelection(selectedIds: string[], requestId: string) {
  return selectedIds.includes(requestId)
    ? selectedIds.filter((id) => id !== requestId)
    : [...selectedIds, requestId]
}

export function intersectSelection(
  selectedIds: string[],
  visibleIds: string[],
) {
  const visible = new Set(visibleIds)
  return selectedIds.filter((id) => visible.has(id))
}

export function invertSelection(selectedIds: string[], visibleIds: string[]) {
  const selected = new Set(selectedIds)
  return visibleIds.filter((id) => !selected.has(id))
}

export interface TimeShortcutAnchor {
  boundary: 'hide-before' | 'hide-after'
  requestId: string
}

export function filterRequestsByTimeShortcutAnchor(
  requests: RequestSummary[],
  anchor: TimeShortcutAnchor | null,
) {
  if (!anchor) {
    return requests
  }

  const anchorIndex = requests.findIndex(
    (request) => request.request_id === anchor.requestId,
  )

  if (anchorIndex < 0) {
    return requests
  }

  return anchor.boundary === 'hide-before'
    ? requests.slice(anchorIndex)
    : requests.slice(0, anchorIndex + 1)
}

export function bucketDurationMs(bucket: HistogramBucket) {
  switch (bucket) {
    case 'second':
      return 1_000
    case 'minute':
      return 60_000
    case 'hour':
      return 3_600_000
  }
}

export function makeBrushRange(
  bucket: HistogramBucket,
  startTimestamp: string,
  endTimestamp: string,
) {
  const startMs = new Date(startTimestamp).getTime()
  const endMs = new Date(endTimestamp).getTime()
  const durationMs = bucketDurationMs(bucket)

  return {
    capturedAfter: new Date(startMs - 1).toISOString(),
    capturedBefore: new Date(endMs + durationMs).toISOString(),
  }
}

export interface FilterChip {
  id: string
  label: string
  onRemove: () => void
}

export function buildFilterChips(
  filters: RequestFilters,
  update: (updater: (current: RequestFilters) => RequestFilters) => void,
) {
  const chips: FilterChip[] = []

  for (const value of filters.traceIds) {
    chips.push({
      id: `trace-${value}`,
      label: `Trace ${compactId(value)}`,
      onRemove: () =>
        update((current) => ({
          ...current,
          traceIds: current.traceIds.filter((item) => item !== value),
        })),
    })
  }

  for (const value of filters.requestIds) {
    chips.push({
      id: `request-${value}`,
      label: `Request ${compactId(value)}`,
      onRemove: () =>
        update((current) => ({
          ...current,
          requestIds: current.requestIds.filter((item) => item !== value),
        })),
    })
  }

  for (const value of filters.nodeNames) {
    chips.push({
      id: `node-${value}`,
      label: `Node ${value}`,
      onRemove: () =>
        update((current) => ({
          ...current,
          nodeNames: current.nodeNames.filter((item) => item !== value),
        })),
    })
  }

  for (const value of filters.methods) {
    chips.push({
      id: `method-${value}`,
      label: `Method ${value}`,
      onRemove: () =>
        update((current) => ({
          ...current,
          methods: current.methods.filter((item) => item !== value),
        })),
    })
  }

  for (const value of filters.statusCodes) {
    chips.push({
      id: `status-${value}`,
      label: `Status ${value}`,
      onRemove: () =>
        update((current) => ({
          ...current,
          statusCodes: current.statusCodes.filter((item) => item !== value),
        })),
    })
  }

  if (filters.urlContains.trim()) {
    chips.push({
      id: 'url-contains',
      label: `URL has "${filters.urlContains.trim()}"`,
      onRemove: () =>
        update((current) => ({
          ...current,
          urlContains: '',
        })),
    })
  }

  const booleanFilters: Array<
    ['complete' | 'requestComplete' | 'responseComplete', string]
  > = [
    ['complete', 'Complete'],
    ['requestComplete', 'Request complete'],
    ['responseComplete', 'Response complete'],
  ]

  for (const [key, label] of booleanFilters) {
    const value = filters[key]
    if (value !== undefined) {
      chips.push({
        id: key,
        label: `${label}: ${formatTriState(value)}`,
        onRemove: () =>
          update((current) => ({
            ...current,
            [key]: undefined,
          })),
      })
    }
  }

  if (filters.capturedAfter || filters.capturedBefore) {
    chips.push({
      id: 'time-range',
      label: `Range ${formatTimestamp(filters.capturedAfter)} → ${formatTimestamp(filters.capturedBefore)}`,
      onRemove: () =>
        update((current) => ({
          ...current,
          capturedAfter: undefined,
          capturedBefore: undefined,
        })),
    })
  }

  return chips
}
