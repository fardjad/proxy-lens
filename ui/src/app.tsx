import { useEffect, useMemo, useRef, useState } from 'preact/hooks'
import type { JSX } from 'preact'
import './app.css'
import {
  deleteRequests,
  getRequestBody,
  getRequestDetail,
  getRequests,
  getResponseBody,
  getServerTarget,
} from './api'
import { decodeBodyPreview } from './body-preview'
import { DetailsSidebar } from './components/details-sidebar'
import {
  RequestList,
  type RequestGridFilters,
  type RequestGridSort,
} from './components/request-list'
import { SequenceDiagram } from './components/sequence-diagram'
import type { BodyState, DiagramMode, LoadState, RequestDetail, RequestSummary } from './types'
import {
  DEFAULT_FILTERS,
  filterRequestsByTimeShortcutAnchor,
  formatCount,
  formatRequestState,
  getRequestState,
  intersectSelection,
  requestDisplayUrl,
  sortRequestsChronologically,
  toggleSelection,
  type TimeShortcutAnchor,
} from './utils'

const SEARCH_FIELDS = ['url', 'trace', 'request'] as const
type SearchField = (typeof SEARCH_FIELDS)[number]
const PAGE_SIZE = 100

interface TimeFilters {
  capturedAfter: string
  capturedBefore: string
}

const DEFAULT_GRID_FILTERS: RequestGridFilters = {
  method: '',
  status: '',
  node: '',
  state: '',
  url: '',
  trace: '',
  request: '',
}

const DEFAULT_TIME_FILTERS: TimeFilters = {
  capturedAfter: '',
  capturedBefore: '',
}

function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setDebouncedValue(value), delayMs)
    return () => window.clearTimeout(timeoutId)
  }, [delayMs, value])

  return debouncedValue
}

const MIN_MAIN_WIDTH = 520
const MIN_SIDEBAR_WIDTH = 320
const DEFAULT_SIDEBAR_WIDTH = 420
const MIN_DIAGRAM_HEIGHT = 180
const MIN_LIST_HEIGHT = 260
const DEFAULT_DIAGRAM_HEIGHT = 260
const SPLITTER_SIZE = 8

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function readStoredSize(key: string, fallback: number) {
  if (typeof window === 'undefined') {
    return fallback
  }

  const rawValue = window.localStorage.getItem(key)
  const parsedValue = Number(rawValue)
  return Number.isFinite(parsedValue) ? parsedValue : fallback
}

function readStoredText(key: string, fallback: string) {
  if (typeof window === 'undefined') {
    return fallback
  }

  return window.localStorage.getItem(key) ?? fallback
}

function readStoredJson<T>(
  key: string,
  fallback: T,
  isValid: (value: unknown) => value is T,
) {
  if (typeof window === 'undefined') {
    return fallback
  }

  const rawValue = window.localStorage.getItem(key)
  if (!rawValue) {
    return fallback
  }

  try {
    const parsedValue: unknown = JSON.parse(rawValue)
    return isValid(parsedValue) ? parsedValue : fallback
  } catch {
    return fallback
  }
}

function isSearchField(value: string): value is SearchField {
  return SEARCH_FIELDS.includes(value as SearchField)
}

function isGridFilters(value: unknown): value is RequestGridFilters {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.method === 'string' &&
    typeof candidate.status === 'string' &&
    typeof candidate.node === 'string' &&
    typeof candidate.state === 'string' &&
    typeof candidate.url === 'string' &&
    typeof candidate.trace === 'string' &&
    typeof candidate.request === 'string'
  )
}

function isGridSort(value: unknown): value is RequestGridSort {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as Record<string, unknown>
  return (
    [
      'method',
      'status',
      'node',
      'state',
      'url',
      'trace',
      'request',
      'captured',
    ].includes(String(candidate.key)) &&
    (candidate.direction === 'asc' || candidate.direction === 'desc')
  )
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isTimeFilters(value: unknown): value is TimeFilters {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.capturedAfter === 'string' &&
    typeof candidate.capturedBefore === 'string'
  )
}

function isTimeShortcutAnchor(value: unknown): value is TimeShortcutAnchor {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as Record<string, unknown>
  return (
    (candidate.boundary === 'hide-before' || candidate.boundary === 'hide-after') &&
    typeof candidate.requestId === 'string'
  )
}

function padDatePart(value: number) {
  return String(value).padStart(2, '0')
}

function toDateTimeLocalValue(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }

  const milliseconds = String(date.getMilliseconds()).padStart(3, '0')

  return [
    `${date.getFullYear()}-${padDatePart(date.getMonth() + 1)}-${padDatePart(date.getDate())}`,
    `${padDatePart(date.getHours())}:${padDatePart(date.getMinutes())}:${padDatePart(date.getSeconds())}.${milliseconds}`,
  ].join('T')
}

function toInclusiveIsoTimestamp(value: string, edge: 'after' | 'before') {
  if (!value.trim()) {
    return undefined
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return undefined
  }

  const ms = date.getTime()
  const adjustment =
    value.includes('.')
      ? 1
      : edge === 'after'
        ? 1
        : 999
  return new Date(edge === 'after' ? ms - 1 : ms + adjustment).toISOString()
}

export function App() {
  const workspaceRef = useRef<HTMLDivElement>(null)
  const mainBodyRef = useRef<HTMLDivElement>(null)
  const [searchField, setSearchField] = useState<SearchField>(() => {
    const storedValue = readStoredText('proxylens.searchField', 'url')
    return isSearchField(storedValue) ? storedValue : 'url'
  })
  const [searchQuery, setSearchQuery] = useState(() =>
    readStoredText('proxylens.searchQuery', ''),
  )
  const [gridFilters, setGridFilters] = useState<RequestGridFilters>(() =>
    readStoredJson('proxylens.gridFilters', DEFAULT_GRID_FILTERS, isGridFilters),
  )
  const [gridSort, setGridSort] = useState<RequestGridSort | null>(() =>
    readStoredJson('proxylens.gridSort', null, (value): value is RequestGridSort | null =>
      value === null || isGridSort(value),
    ),
  )
  const [timeFilters, setTimeFilters] = useState<TimeFilters>(() =>
    readStoredJson('proxylens.timeFilters', DEFAULT_TIME_FILTERS, isTimeFilters),
  )
  const [timeShortcutAnchor, setTimeShortcutAnchor] = useState<TimeShortcutAnchor | null>(() =>
    readStoredJson('proxylens.timeShortcutAnchor', null, (value): value is TimeShortcutAnchor | null =>
      value === null || isTimeShortcutAnchor(value),
    ),
  )
  const [diagramMode, setDiagramMode] = useState<DiagramMode>('grouped')
  const [currentPage, setCurrentPage] = useState(() =>
    Math.max(0, Math.floor(readStoredSize('proxylens.currentPage', 0))),
  )
  const [selectedIds, setSelectedIds] = useState<string[]>(() =>
    readStoredJson('proxylens.selectedIds', [], isStringArray),
  )
  const [sidebarWidth, setSidebarWidth] = useState(() =>
    readStoredSize('proxylens.sidebarWidth', DEFAULT_SIDEBAR_WIDTH),
  )
  const [sidebarHidden, setSidebarHidden] = useState(() =>
    readStoredSize('proxylens.sidebarHidden', 0) === 1,
  )
  const [diagramHeight, setDiagramHeight] = useState(() =>
    readStoredSize('proxylens.diagramHeight', DEFAULT_DIAGRAM_HEIGHT),
  )
  const [requestsState, setRequestsState] = useState<LoadState<RequestSummary[]>>({
    status: 'loading',
  })
  const [detailState, setDetailState] = useState<LoadState<RequestDetail>>({
    status: 'idle',
  })
  const [requestBodyState, setRequestBodyState] = useState<BodyState>({ status: 'idle' })
  const [responseBodyState, setResponseBodyState] = useState<BodyState>({ status: 'idle' })
  const [refreshTick, setRefreshTick] = useState(0)

  const debouncedSearchQuery = useDebouncedValue(searchQuery, 250)

  useEffect(() => {
    window.localStorage.setItem('proxylens.searchField', searchField)
  }, [searchField])

  useEffect(() => {
    window.localStorage.setItem('proxylens.searchQuery', searchQuery)
  }, [searchQuery])

  useEffect(() => {
    window.localStorage.setItem('proxylens.gridFilters', JSON.stringify(gridFilters))
  }, [gridFilters])

  useEffect(() => {
    window.localStorage.setItem('proxylens.gridSort', JSON.stringify(gridSort))
  }, [gridSort])

  useEffect(() => {
    window.localStorage.setItem('proxylens.timeFilters', JSON.stringify(timeFilters))
  }, [timeFilters])

  useEffect(() => {
    window.localStorage.setItem(
      'proxylens.timeShortcutAnchor',
      JSON.stringify(timeShortcutAnchor),
    )
  }, [timeShortcutAnchor])

  useEffect(() => {
    window.localStorage.setItem('proxylens.currentPage', `${currentPage}`)
  }, [currentPage])

  useEffect(() => {
    window.localStorage.setItem('proxylens.selectedIds', JSON.stringify(selectedIds))
  }, [selectedIds])

  useEffect(() => {
    window.localStorage.setItem('proxylens.sidebarWidth', `${Math.round(sidebarWidth)}`)
  }, [sidebarWidth])

  useEffect(() => {
    window.localStorage.setItem('proxylens.sidebarHidden', sidebarHidden ? '1' : '0')
  }, [sidebarHidden])

  useEffect(() => {
    window.localStorage.setItem('proxylens.diagramHeight', `${Math.round(diagramHeight)}`)
  }, [diagramHeight])

  useEffect(() => {
    const handleResize = () => {
      const workspaceRect = workspaceRef.current?.getBoundingClientRect()
      if (workspaceRect) {
        const maxSidebarWidth = Math.max(
          MIN_SIDEBAR_WIDTH,
          workspaceRect.width - MIN_MAIN_WIDTH - SPLITTER_SIZE,
        )
        setSidebarWidth((current) => clamp(current, MIN_SIDEBAR_WIDTH, maxSidebarWidth))
      }

      const mainBodyRect = mainBodyRef.current?.getBoundingClientRect()
      if (mainBodyRect) {
        const maxDiagramHeight = Math.max(
          MIN_DIAGRAM_HEIGHT,
          mainBodyRect.height - MIN_LIST_HEIGHT - SPLITTER_SIZE,
        )
        setDiagramHeight((current) => clamp(current, MIN_DIAGRAM_HEIGHT, maxDiagramHeight))
      }
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const effectiveFilters = useMemo(
    () => ({
      ...DEFAULT_FILTERS,
      capturedAfter: toInclusiveIsoTimestamp(timeFilters.capturedAfter, 'after'),
      capturedBefore: toInclusiveIsoTimestamp(timeFilters.capturedBefore, 'before'),
      urlContains: searchField === 'url' ? debouncedSearchQuery.trim() : '',
      traceIds:
        searchField === 'trace'
          ? debouncedSearchQuery
              .split(/[,\s]+/)
              .map((value) => value.trim())
              .filter(Boolean)
          : [],
      requestIds:
        searchField === 'request'
          ? debouncedSearchQuery
              .split(/[,\s]+/)
              .map((value) => value.trim())
              .filter(Boolean)
          : [],
    }),
    [debouncedSearchQuery, searchField, timeFilters],
  )

  useEffect(() => {
    let cancelled = false
    setRequestsState({ status: 'loading' })

    getRequests(effectiveFilters)
      .then((data) => {
        if (cancelled) {
          return
        }

        const sorted = sortRequestsChronologically(data.requests)
        setRequestsState({ status: 'ready', data: sorted })
        setSelectedIds((current) =>
          intersectSelection(
            current,
            sorted.map((request) => request.request_id),
          ),
        )
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setRequestsState({
            status: 'error',
            error: error instanceof Error ? error.message : 'Failed to load requests',
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [effectiveFilters, refreshTick])

  const requests =
    requestsState.status === 'ready'
      ? requestsState.data
      : []

  const anchoredRequests = useMemo(
    () => filterRequestsByTimeShortcutAnchor(requests, timeShortcutAnchor),
    [requests, timeShortcutAnchor],
  )

  const filteredRequests = useMemo(() => {
    const filtered = anchoredRequests.filter((request) => {
      if (gridFilters.method && request.request_method !== gridFilters.method) {
        return false
      }

      if (
        gridFilters.status &&
        String(request.response_status_code ?? '') !== gridFilters.status
      ) {
        return false
      }

      if (gridFilters.node && request.node_name !== gridFilters.node) {
        return false
      }

      if (gridFilters.state && getRequestState(request) !== gridFilters.state) {
        return false
      }

      if (
        gridFilters.url &&
        !requestDisplayUrl(request).toLowerCase().includes(gridFilters.url.toLowerCase())
      ) {
        return false
      }

      if (
        gridFilters.trace &&
        !request.trace_id.toLowerCase().includes(gridFilters.trace.toLowerCase())
      ) {
        return false
      }

      if (
        gridFilters.request &&
        !request.request_id.toLowerCase().includes(gridFilters.request.toLowerCase())
      ) {
        return false
      }

      return true
    })

    if (!gridSort) {
      return filtered
    }

    const sorted = [...filtered]
    sorted.sort((left, right) => {
      const direction = gridSort.direction === 'asc' ? 1 : -1

      switch (gridSort.key) {
        case 'method':
          return direction * (left.request_method ?? '').localeCompare(right.request_method ?? '')
        case 'status':
          return direction * ((left.response_status_code ?? -1) - (right.response_status_code ?? -1))
        case 'node':
          return direction * left.node_name.localeCompare(right.node_name)
        case 'state':
          return direction * formatRequestState(getRequestState(left)).localeCompare(
            formatRequestState(getRequestState(right)),
          )
        case 'url':
          return direction * requestDisplayUrl(left).localeCompare(requestDisplayUrl(right))
        case 'trace':
          return direction * left.trace_id.localeCompare(right.trace_id)
        case 'request':
          return direction * left.request_id.localeCompare(right.request_id)
        case 'captured':
          return direction * (
            new Date(left.captured_at).getTime() - new Date(right.captured_at).getTime()
          )
      }
    })

    return sorted
  }, [anchoredRequests, gridFilters, gridSort])

  const totalPages = Math.max(1, Math.ceil(filteredRequests.length / PAGE_SIZE))
  const currentPageClamped = clamp(currentPage, 0, totalPages - 1)
  const pagedRequests = useMemo(() => {
    const start = currentPageClamped * PAGE_SIZE
    return filteredRequests.slice(start, start + PAGE_SIZE)
  }, [currentPageClamped, filteredRequests])

  const gridFilterOptions = useMemo(() => {
    const methods = new Set<string>()
    const statuses = new Set<string>()
    const nodes = new Set<string>()

    for (const request of requests) {
      if (request.request_method) {
        methods.add(request.request_method)
      }
      if (request.response_status_code !== null) {
        statuses.add(String(request.response_status_code))
      }
      nodes.add(request.node_name)
    }

    return {
      methods: [...methods].sort(),
      statuses: [...statuses].sort((left, right) => Number(left) - Number(right)),
      nodes: [...nodes].sort(),
    }
  }, [requests])

  const selectedRequestId = selectedIds.length === 1 ? selectedIds[0] : undefined

  useEffect(() => {
    setCurrentPage((current) => clamp(current, 0, totalPages - 1))
  }, [totalPages])

  useEffect(() => {
    setSelectedIds((current) =>
      intersectSelection(
        current,
        filteredRequests.map((request) => request.request_id),
      ),
    )
  }, [filteredRequests])

  useEffect(() => {
    if (!selectedRequestId) {
      setDetailState({ status: 'idle' })
      setRequestBodyState({ status: 'idle' })
      setResponseBodyState({ status: 'idle' })
      return
    }

    let cancelled = false
    setDetailState({ status: 'loading' })
    setRequestBodyState({ status: 'loading' })
    setResponseBodyState({ status: 'loading' })

    getRequestDetail(selectedRequestId)
      .then(async (detail) => {
        if (cancelled) {
          return
        }

        setDetailState({ status: 'ready', data: detail })

        const [requestBody, responseBody] = await Promise.all([
          getRequestBody(selectedRequestId),
          getResponseBody(selectedRequestId),
        ])

        if (cancelled) {
          return
        }

        if (!requestBody) {
          setRequestBodyState({ status: 'missing' })
        } else {
          setRequestBodyState({
            status: 'ready',
            data: requestBody,
            preview: decodeBodyPreview(requestBody.bytes, requestBody.contentType),
          })
        }

        if (!responseBody) {
          setResponseBodyState({ status: 'missing' })
        } else {
          setResponseBodyState({
            status: 'ready',
            data: responseBody,
            preview: decodeBodyPreview(responseBody.bytes, responseBody.contentType),
          })
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message =
            error instanceof Error ? error.message : 'Failed to load request detail'
          setDetailState({ status: 'error', error: message })
          setRequestBodyState({ status: 'error', error: message })
          setResponseBodyState({ status: 'error', error: message })
        }
      })

    return () => {
      cancelled = true
    }
  }, [selectedRequestId])

  async function handleDeleteSelected() {
    if (selectedIds.length === 0) {
      return
    }

    if (!window.confirm(`Delete ${selectedIds.length} selected requests?`)) {
      return
    }

    try {
      await deleteRequests(selectedIds)
      setSelectedIds([])
      setRefreshTick((current) => current + 1)
    } catch (error) {
      window.alert(error instanceof Error ? error.message : 'Delete failed')
    }
  }

  function handleTimeShortcut(
    request: RequestSummary,
    boundary: 'hide-before' | 'hide-after',
  ) {
    const timestamp = toDateTimeLocalValue(request.captured_at)
    const requestIndex = filteredRequests.findIndex(
      (candidate) => candidate.request_id === request.request_id,
    )

    setTimeFilters((current) => ({
      ...current,
      capturedAfter: boundary === 'hide-before' ? timestamp : current.capturedAfter,
      capturedBefore: boundary === 'hide-after' ? timestamp : current.capturedBefore,
    }))
    setTimeShortcutAnchor({
      boundary,
      requestId: request.request_id,
    })

    if (boundary === 'hide-before' || requestIndex < 0) {
      setCurrentPage(0)
      return
    }

    setCurrentPage(Math.floor(requestIndex / PAGE_SIZE))
  }

  function startSidebarResize(event: JSX.TargetedPointerEvent<HTMLDivElement>) {
    if (window.matchMedia('(max-width: 1180px)').matches || !workspaceRef.current) {
      return
    }

    event.preventDefault()
    const workspaceRect = workspaceRef.current.getBoundingClientRect()
    const startSidebar = sidebarWidth
    const startX = event.clientX
    const originalUserSelect = document.body.style.userSelect
    const originalCursor = document.body.style.cursor
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    const maxSidebarWidth = Math.max(
      MIN_SIDEBAR_WIDTH,
      workspaceRect.width - MIN_MAIN_WIDTH - SPLITTER_SIZE,
    )

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const delta = startX - moveEvent.clientX
      setSidebarWidth(clamp(startSidebar + delta, MIN_SIDEBAR_WIDTH, maxSidebarWidth))
    }

    const stopResize = () => {
      document.body.style.userSelect = originalUserSelect
      document.body.style.cursor = originalCursor
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', stopResize)
      window.removeEventListener('pointercancel', stopResize)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', stopResize)
    window.addEventListener('pointercancel', stopResize)
  }

  function startDiagramResize(event: JSX.TargetedPointerEvent<HTMLDivElement>) {
    if (window.matchMedia('(max-width: 1180px)').matches || !mainBodyRef.current) {
      return
    }

    event.preventDefault()
    const mainBodyRect = mainBodyRef.current.getBoundingClientRect()
    const startHeight = diagramHeight
    const startY = event.clientY
    const originalUserSelect = document.body.style.userSelect
    const originalCursor = document.body.style.cursor
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'row-resize'

    const maxDiagramHeight = Math.max(
      MIN_DIAGRAM_HEIGHT,
      mainBodyRect.height - MIN_LIST_HEIGHT - SPLITTER_SIZE,
    )

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const delta = moveEvent.clientY - startY
      setDiagramHeight(clamp(startHeight - delta, MIN_DIAGRAM_HEIGHT, maxDiagramHeight))
    }

    const stopResize = () => {
      document.body.style.userSelect = originalUserSelect
      document.body.style.cursor = originalCursor
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', stopResize)
      window.removeEventListener('pointercancel', stopResize)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', stopResize)
    window.addEventListener('pointercancel', stopResize)
  }

  const workspaceStyle = {
    '--sidebar-width': `${sidebarWidth}px`,
  } as JSX.CSSProperties

  const mainBodyStyle = {
    '--diagram-height': `${diagramHeight}px`,
  } as JSX.CSSProperties

  return (
    <main class="shell">
      <header class="shell__header">
        <div class="shell__title">
          <strong>ProxyLens</strong>
          <span>Flow sequencer</span>
        </div>
        <button
          type="button"
          class="button button--ghost shell__header-toggle"
          onClick={() => setSidebarHidden((current) => !current)}
          aria-expanded={!sidebarHidden}
          aria-label={sidebarHidden ? 'Show details sidebar' : 'Hide details sidebar'}
          title={sidebarHidden ? 'Show details sidebar' : 'Hide details sidebar'}
        >
          {sidebarHidden ? '>' : '<'}
        </button>
      </header>

      <div
        class={`workspace${sidebarHidden ? ' workspace--sidebar-hidden' : ''}`}
        ref={workspaceRef}
        style={workspaceStyle}
      >
        <section class="workspace__main">
          <section class="search-strip">
            <select
              aria-label="Search field"
              value={searchField}
              onInput={(event) => {
                setSearchField((event.currentTarget as HTMLSelectElement).value as SearchField)
                setCurrentPage(0)
              }}
            >
              <option value="url">URL contains</option>
              <option value="trace">Trace ID</option>
              <option value="request">Request ID</option>
            </select>
            <input
              value={searchQuery}
              placeholder={
                searchField === 'url'
                  ? 'Search substring in URL'
                  : searchField === 'trace'
                    ? 'Paste one or more trace ids'
                    : 'Paste one or more request ids'
              }
              onInput={(event) => {
                setSearchQuery((event.currentTarget as HTMLInputElement).value)
                setCurrentPage(0)
              }}
            />
            <button
              type="button"
              class="button button--ghost"
              onClick={() => {
                setSearchField('url')
                setSearchQuery('')
                setGridFilters(DEFAULT_GRID_FILTERS)
                setGridSort(null)
                setTimeFilters(DEFAULT_TIME_FILTERS)
                setTimeShortcutAnchor(null)
                setCurrentPage(0)
              }}
            >
              Clear
            </button>
          </section>

          <section class="time-strip">
            <label class="field">
              <span class="field__label">Captured After</span>
              <input
                type="datetime-local"
                step="0.001"
                value={timeFilters.capturedAfter}
                onInput={(event) => {
                  setTimeFilters((current) => ({
                    ...current,
                    capturedAfter: (event.currentTarget as HTMLInputElement).value,
                  }))
                  setTimeShortcutAnchor(null)
                  setCurrentPage(0)
                }}
              />
            </label>
            <label class="field">
              <span class="field__label">Captured Before</span>
              <input
                type="datetime-local"
                step="0.001"
                value={timeFilters.capturedBefore}
                onInput={(event) => {
                  setTimeFilters((current) => ({
                    ...current,
                    capturedBefore: (event.currentTarget as HTMLInputElement).value,
                  }))
                  setTimeShortcutAnchor(null)
                  setCurrentPage(0)
                }}
              />
            </label>
            <button
              type="button"
              class="button button--ghost"
              onClick={() => {
                setTimeFilters(DEFAULT_TIME_FILTERS)
                setTimeShortcutAnchor(null)
                setCurrentPage(0)
              }}
            >
              Clear time
            </button>
          </section>

          <div class="workspace__main-body" ref={mainBodyRef} style={mainBodyStyle}>
            <section class="panel panel--list">
              {requestsState.status === 'loading' && <div class="panel-empty">Loading requests…</div>}
              {requestsState.status === 'error' && <div class="panel-empty">{requestsState.error}</div>}
              {requestsState.status === 'ready' && (
                <RequestList
                  requests={pagedRequests}
                  totalRequests={filteredRequests.length}
                  page={currentPageClamped}
                  pageSize={PAGE_SIZE}
                  selectedIds={selectedIds}
                  filters={gridFilters}
                  sort={gridSort}
                  methods={gridFilterOptions.methods}
                  statuses={gridFilterOptions.statuses}
                  nodes={gridFilterOptions.nodes}
                  onFiltersChange={(next) => {
                    setGridFilters(next)
                    setCurrentPage(0)
                  }}
                  onSortChange={(next) => {
                    setGridSort(next)
                    setCurrentPage(0)
                  }}
                  onPageChange={setCurrentPage}
                  onSelectionChange={setSelectedIds}
                  onTimeFilterShortcut={handleTimeShortcut}
                />
              )}
            </section>

            <div
              class="splitter splitter--horizontal"
              role="separator"
              aria-label="Resize request list and diagram"
              aria-orientation="horizontal"
              onPointerDown={startDiagramResize}
            />

            <SequenceDiagram
              requests={pagedRequests}
              selectedIds={selectedIds}
              mode={diagramMode}
              onModeChange={setDiagramMode}
              onToggleRequest={(requestId) =>
                setSelectedIds((current) => toggleSelection(current, requestId))
              }
            />
          </div>
        </section>

        {!sidebarHidden && (
          <div
            class="splitter splitter--vertical"
            role="separator"
            aria-label="Resize main workspace and details"
            aria-orientation="vertical"
            onPointerDown={startSidebarResize}
          />
        )}

        {!sidebarHidden && (
          <DetailsSidebar
            selectedCount={selectedIds.length}
            selectedRequestId={selectedRequestId}
            detailState={detailState}
            requestBodyState={requestBodyState}
            responseBodyState={responseBodyState}
          />
        )}
      </div>

      <footer class="shell__footer">
        <span>Server target: {getServerTarget()}</span>
        <span>{formatCount(filteredRequests.length)} visible</span>
        <span>Page {filteredRequests.length === 0 ? 0 : currentPageClamped + 1} / {totalPages}</span>
        <span>{selectedIds.length} selected</span>
        <button
          type="button"
          class="button button--danger shell__footer-action"
          disabled={selectedIds.length === 0}
          onClick={handleDeleteSelected}
        >
          Delete
        </button>
      </footer>
    </main>
  )
}
