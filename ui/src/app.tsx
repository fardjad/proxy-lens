import { useEffect, useMemo, useState } from 'preact/hooks'
import './app.css'
import {
  deleteRequests,
  getHistogram,
  getRequestBody,
  getRequestDetail,
  getRequests,
  getResponseBody,
  getServerTarget,
} from './api'
import { decodeBodyPreview } from './body-preview'
import { DetailsSidebar } from './components/details-sidebar'
import { Histogram } from './components/histogram'
import { RequestList } from './components/request-list'
import { RequestToolbar } from './components/request-toolbar'
import { SequenceDiagram } from './components/sequence-diagram'
import { TokenInput } from './components/token-input'
import { TriStateToggle } from './components/tri-state-toggle'
import type { BodyState, DiagramMode, LoadState, RequestDetail, RequestSummary } from './types'
import {
  buildFilterChips,
  classNames,
  COMMON_METHODS,
  DEFAULT_FILTERS,
  formatCount,
  formatTimestamp,
  intersectSelection,
  invertSelection,
  makeBrushRange,
  sortRequestsChronologically,
  toggleSelection,
} from './utils'

function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setDebouncedValue(value), delayMs)
    return () => window.clearTimeout(timeoutId)
  }, [delayMs, value])

  return debouncedValue
}

export function App() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [diagramMode, setDiagramMode] = useState<DiagramMode>('grouped')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [histogramState, setHistogramState] = useState<LoadState<Awaited<ReturnType<typeof getHistogram>>>>({
    status: 'loading',
  })
  const [requestsState, setRequestsState] = useState<LoadState<RequestSummary[]>>({
    status: 'loading',
  })
  const [detailState, setDetailState] = useState<LoadState<RequestDetail>>({
    status: 'idle',
  })
  const [requestBodyState, setRequestBodyState] = useState<BodyState>({ status: 'idle' })
  const [responseBodyState, setResponseBodyState] = useState<BodyState>({ status: 'idle' })
  const [refreshTick, setRefreshTick] = useState(0)

  const debouncedUrlContains = useDebouncedValue(filters.urlContains, 250)

  const effectiveFilters = useMemo(
    () => ({
      ...filters,
      urlContains: debouncedUrlContains,
    }),
    [debouncedUrlContains, filters],
  )

  useEffect(() => {
    let cancelled = false
    setHistogramState({ status: 'loading' })

    getHistogram()
      .then((data) => {
        if (!cancelled) {
          setHistogramState({ status: 'ready', data })
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setHistogramState({
            status: 'error',
            error: error instanceof Error ? error.message : 'Failed to load histogram',
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [refreshTick])

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

  const suggestions = useMemo(() => {
    const traceIds = new Set<string>()
    const requestIds = new Set<string>()
    const nodeNames = new Set<string>()

    for (const request of requests) {
      traceIds.add(request.trace_id)
      requestIds.add(request.request_id)
      nodeNames.add(request.node_name)
    }

    return {
      traceIds: [...traceIds].sort(),
      requestIds: [...requestIds].sort(),
      nodeNames: [...nodeNames].sort(),
    }
  }, [requests])

  const selectedRequestId = selectedIds.length === 1 ? selectedIds[0] : undefined

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

  const filterChips = useMemo(
    () => buildFilterChips(filters, setFilters),
    [filters],
  )

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

  function updateStringList(
    key: 'traceIds' | 'requestIds' | 'nodeNames' | 'methods',
    next: string[],
  ) {
    setFilters((current) => ({
      ...current,
      [key]:
        key === 'methods'
          ? next.map((value) => value.toUpperCase())
          : next,
    }))
  }

  return (
    <main class="shell">
      <header class="shell__header">
        <div>
          <span class="eyebrow">ProxyLens</span>
          <h1>Flow sequencer</h1>
          <p>
            Histogram-driven filtering, request selection, and an interactive hop diagram for the live server data.
          </p>
        </div>
        <div class="server-pill">Server target: {getServerTarget()}</div>
      </header>

      <div class="workspace">
        <section class="workspace__main">
          <section class="panel">
            <div class="panel__header">
              <div>
                <h2>Filter</h2>
                <p>Brush time ranges and combine request query parameters with AND semantics.</p>
              </div>
              <button
                type="button"
                class="button button--ghost"
                onClick={() => setFilters(DEFAULT_FILTERS)}
              >
                Clear all
              </button>
            </div>

            {histogramState.status === 'loading' && <div class="panel-empty">Loading histogram…</div>}
            {histogramState.status === 'error' && <div class="panel-empty">{histogramState.error}</div>}
            {histogramState.status === 'ready' && (
              <Histogram
                points={histogramState.data.points}
                bucket={histogramState.data.bucket}
                selectedRange={{
                  capturedAfter: filters.capturedAfter,
                  capturedBefore: filters.capturedBefore,
                }}
                onSelectRange={(startIndex, endIndex) => {
                  const startPoint = histogramState.data.points[startIndex]
                  const endPoint = histogramState.data.points[endIndex]
                  if (!startPoint || !endPoint) {
                    return
                  }

                  const range = makeBrushRange(
                    histogramState.data.bucket,
                    startPoint.timestamp,
                    endPoint.timestamp,
                  )

                  setFilters((current) => ({
                    ...current,
                    ...range,
                  }))
                }}
                onClearRange={() =>
                  setFilters((current) => ({
                    ...current,
                    capturedAfter: undefined,
                    capturedBefore: undefined,
                  }))
                }
              />
            )}

            <div class="filter-grid">
              <label class="field">
                <span class="field__label">URL contains</span>
                <input
                  value={filters.urlContains}
                  placeholder="example.test/widgets"
                  onInput={(event) =>
                    setFilters((current) => ({
                      ...current,
                      urlContains: (event.currentTarget as HTMLInputElement).value,
                    }))
                  }
                />
              </label>

              <TokenInput
                name="trace-ids"
                label="Trace IDs"
                tokens={filters.traceIds}
                onChange={(next) => updateStringList('traceIds', next)}
                suggestions={suggestions.traceIds}
                placeholder="Paste one or more trace ids"
              />

              <TokenInput
                name="request-ids"
                label="Request IDs"
                tokens={filters.requestIds}
                onChange={(next) => updateStringList('requestIds', next)}
                suggestions={suggestions.requestIds}
                placeholder="Paste one or more request ids"
              />

              <TokenInput
                name="node-names"
                label="Node names"
                tokens={filters.nodeNames}
                onChange={(next) => updateStringList('nodeNames', next)}
                suggestions={suggestions.nodeNames}
                placeholder="edge-a, proxy-a"
              />

              <div class="field">
                <span class="field__label">Methods</span>
                <div class="method-pills">
                  {COMMON_METHODS.map((method) => {
                    const isActive = filters.methods.includes(method)
                    return (
                      <button
                        key={method}
                        type="button"
                        class={classNames('method-pill', isActive && 'is-active')}
                        onClick={() =>
                          setFilters((current) => ({
                            ...current,
                            methods: isActive
                              ? current.methods.filter((item) => item !== method)
                              : [...current.methods, method],
                          }))
                        }
                      >
                        {method}
                      </button>
                    )
                  })}
                </div>
                <TokenInput
                  name="methods-custom"
                  label="Custom methods"
                  tokens={filters.methods.filter((method) => !COMMON_METHODS.includes(method as (typeof COMMON_METHODS)[number]))}
                onChange={(customMethods) =>
                  setFilters((current) => ({
                    ...current,
                    methods: [
                      ...current.methods.filter((method) =>
                          COMMON_METHODS.includes(method as (typeof COMMON_METHODS)[number]),
                        ),
                        ...customMethods.map((value) => value.toUpperCase()),
                      ],
                    }))
                  }
                  placeholder="PROPFIND"
                />
              </div>

              <TokenInput
                name="status-codes"
                label="Status codes"
                tokens={filters.statusCodes.map(String)}
                onChange={(next) =>
                  setFilters((current) => ({
                    ...current,
                    statusCodes: next
                      .map((value) => Number.parseInt(value, 10))
                      .filter((value) => Number.isFinite(value)),
                  }))
                }
                placeholder="200, 404"
                inputMode="numeric"
              />

              <TriStateToggle
                label="Complete"
                value={filters.complete}
                onChange={(value) =>
                  setFilters((current) => ({ ...current, complete: value }))
                }
              />
              <TriStateToggle
                label="Request complete"
                value={filters.requestComplete}
                onChange={(value) =>
                  setFilters((current) => ({ ...current, requestComplete: value }))
                }
              />
              <TriStateToggle
                label="Response complete"
                value={filters.responseComplete}
                onChange={(value) =>
                  setFilters((current) => ({ ...current, responseComplete: value }))
                }
              />
            </div>

            {filterChips.length > 0 && (
              <div class="filter-chips">
                {filterChips.map((chip) => (
                  <button
                    type="button"
                    key={chip.id}
                    class="filter-chip"
                    onClick={chip.onRemove}
                  >
                    {chip.label}
                    <span aria-hidden="true">×</span>
                  </button>
                ))}
              </div>
            )}
          </section>

          <SequenceDiagram
            requests={requests}
            selectedIds={selectedIds}
            mode={diagramMode}
            onModeChange={setDiagramMode}
            onToggleRequest={(requestId) =>
              setSelectedIds((current) => toggleSelection(current, requestId))
            }
          />

          <section class="panel panel--toolbar">
            <RequestToolbar
              selectedCount={selectedIds.length}
              totalCount={requests.length}
              onSelectAll={() =>
                setSelectedIds(requests.map((request) => request.request_id))
              }
              onInvert={() =>
                setSelectedIds((current) =>
                  invertSelection(
                    current,
                    requests.map((request) => request.request_id),
                  ),
                )
              }
              onDelete={handleDeleteSelected}
            />
          </section>

          <section class="panel panel--list">
            <div class="panel__header">
              <div>
                <h2>Requests list</h2>
                <p>
                  {requestsState.status === 'ready'
                    ? `${formatCount(requests.length)} requests in view`
                    : 'Loading request summaries'}
                </p>
              </div>
              {requestsState.status === 'ready' && requests.length === 1000 && (
                <div class="server-pill">Showing the first 1000 matches</div>
              )}
            </div>

            {requestsState.status === 'loading' && <div class="panel-empty">Loading requests…</div>}
            {requestsState.status === 'error' && <div class="panel-empty">{requestsState.error}</div>}
            {requestsState.status === 'ready' && (
              <RequestList
                requests={requests}
                selectedIds={selectedIds}
                onToggleRequest={(requestId) =>
                  setSelectedIds((current) => toggleSelection(current, requestId))
                }
              />
            )}
          </section>
        </section>

        <DetailsSidebar
          selectedCount={selectedIds.length}
          selectedRequestId={selectedRequestId}
          detailState={detailState}
          requestBodyState={requestBodyState}
          responseBodyState={responseBodyState}
        />
      </div>

      <footer class="shell__footer">
        <span>Range: {formatTimestamp(filters.capturedAfter)} → {formatTimestamp(filters.capturedBefore)}</span>
        <span>Selection: {selectedIds.length}</span>
      </footer>
    </main>
  )
}
