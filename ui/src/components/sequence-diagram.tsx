import type { JSX } from 'preact'
import { useRef, useState } from 'preact/hooks'
import { buildSequenceDiagramModel, ORIGIN_COLUMN } from '../diagram'
import type { DiagramMode, RequestSummary } from '../types'
import { classNames, compactId } from '../utils'

interface SequenceDiagramProps {
  requests: RequestSummary[]
  selectedIds: string[]
  mode: DiagramMode
  onToggleRequest: (requestId: string) => void
  onModeChange: (mode: DiagramMode) => void
  onHide: () => void
  onResizeStart: (event: JSX.TargetedPointerEvent<HTMLDivElement>) => void
}

const MIN_ZOOM = 0.5
const MAX_ZOOM = 3
const ZOOM_STEP = 0.2

function clampZoom(value: number) {
  return Math.min(Math.max(value, MIN_ZOOM), MAX_ZOOM)
}

export function SequenceDiagram({
  requests,
  selectedIds,
  mode,
  onToggleRequest,
  onModeChange,
  onHide,
  onResizeStart,
}: SequenceDiagramProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const panRef = useRef<{
    pointerId: number
    startX: number
    startY: number
    startScrollLeft: number
    startScrollTop: number
  } | null>(null)
  const [zoom, setZoom] = useState(1)
  const [isPanning, setIsPanning] = useState(false)
  const model = buildSequenceDiagramModel(requests, mode)
  const selected = new Set(selectedIds)

  const applyZoom = (nextZoom: number, anchorX?: number, anchorY?: number) => {
    const viewport = viewportRef.current
    const clampedZoom = clampZoom(nextZoom)

    if (!viewport) {
      setZoom(clampedZoom)
      return
    }

    const rect = viewport.getBoundingClientRect()
    const localX = (anchorX ?? rect.left + rect.width / 2) - rect.left
    const localY = (anchorY ?? rect.top + rect.height / 2) - rect.top
    const contentX = (viewport.scrollLeft + localX) / zoom
    const contentY = (viewport.scrollTop + localY) / zoom

    setZoom(clampedZoom)

    requestAnimationFrame(() => {
      viewport.scrollLeft = contentX * clampedZoom - localX
      viewport.scrollTop = contentY * clampedZoom - localY
    })
  }

  const resetView = () => {
    setZoom(1)
    requestAnimationFrame(() => {
      const viewport = viewportRef.current
      if (!viewport) {
        return
      }
      viewport.scrollLeft = 0
      viewport.scrollTop = 0
    })
  }

  const handlePointerDown = (
    event: JSX.TargetedPointerEvent<HTMLDivElement>,
  ) => {
    if (event.button !== 0) {
      return
    }

    const target = event.target as Element | null
    if (target?.closest('.diagram__request-hitbox')) {
      return
    }

    const viewport = viewportRef.current
    if (!viewport) {
      return
    }

    panRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startScrollLeft: viewport.scrollLeft,
      startScrollTop: viewport.scrollTop,
    }
    setIsPanning(true)
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (
    event: JSX.TargetedPointerEvent<HTMLDivElement>,
  ) => {
    const panState = panRef.current
    const viewport = viewportRef.current
    if (!panState || !viewport || panState.pointerId !== event.pointerId) {
      return
    }

    viewport.scrollLeft =
      panState.startScrollLeft - (event.clientX - panState.startX)
    viewport.scrollTop =
      panState.startScrollTop - (event.clientY - panState.startY)
  }

  const stopPanning = (event: JSX.TargetedPointerEvent<HTMLDivElement>) => {
    const panState = panRef.current
    if (!panState || panState.pointerId !== event.pointerId) {
      return
    }

    panRef.current = null
    setIsPanning(false)

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const handleWheel = (event: JSX.TargetedWheelEvent<HTMLDivElement>) => {
    if (!event.ctrlKey && !event.metaKey) {
      return
    }

    event.preventDefault()
    const direction = event.deltaY > 0 ? -1 : 1
    applyZoom(zoom + direction * ZOOM_STEP, event.clientX, event.clientY)
  }

  if (requests.length === 0) {
    return (
      <div class="panel panel--diagram">
        <div
          class="panel-border-handle panel-border-handle--top"
          onPointerDown={onResizeStart}
          title="Drag to resize the sequence diagram"
        />
        <div class="panel__header">
          <div>
            <h2>Sequence diagram</h2>
            <p>Edges appear here once requests are loaded.</p>
          </div>
          <button type="button" class="button button--ghost" onClick={onHide}>
            Hide
          </button>
        </div>
        <div class="panel-empty">No filtered requests to diagram.</div>
      </div>
    )
  }

  const columnX = new Map<string, number>()
  model.columns.forEach((column, index) => {
    columnX.set(column, 120 + index * 180)
  })

  const rowHeight = 72
  const rowOffset = 84
  const width = Math.max(420, model.columns.length * 180 + 120)
  const height = model.rows.length * rowHeight + rowOffset

  return (
    <div class="panel panel--diagram">
      <div
        class="panel-border-handle panel-border-handle--top"
        onPointerDown={onResizeStart}
        title="Drag to resize the sequence diagram"
      />
      <div class="panel__header">
        <div>
          <h2>Sequence diagram</h2>
          <p>Click a line to select. Drag to pan. Ctrl/Cmd + wheel to zoom.</p>
        </div>
          <div class="diagram__header-actions">
            <div class="diagram__controls">
              <button
                type="button"
                class="button button--ghost"
                onClick={onHide}
              >
                Hide
              </button>
              <button
                type="button"
                class="button button--ghost"
              onClick={() => applyZoom(zoom - ZOOM_STEP)}
              disabled={zoom <= MIN_ZOOM}
              aria-label="Zoom out"
            >
              -
            </button>
            <button
              type="button"
              class="button button--ghost diagram__zoom-label"
              onClick={resetView}
              aria-label="Reset zoom and pan"
            >
              {Math.round(zoom * 100)}%
            </button>
            <button
              type="button"
              class="button button--ghost"
              onClick={() => applyZoom(zoom + ZOOM_STEP)}
              disabled={zoom >= MAX_ZOOM}
              aria-label="Zoom in"
            >
              +
            </button>
            <button
              type="button"
              class="button button--ghost"
              onClick={resetView}
            >
              Reset
            </button>
          </div>
          <div class="segmented">
            <button
              type="button"
              class={classNames(
                'segmented__option',
                mode === 'grouped' && 'is-active',
              )}
              onClick={() => onModeChange('grouped')}
            >
              Grouped
            </button>
            <button
              type="button"
              class={classNames(
                'segmented__option',
                mode === 'flat' && 'is-active',
              )}
              onClick={() => onModeChange('flat')}
            >
              Flat
            </button>
          </div>
        </div>
      </div>

      <div
        ref={viewportRef}
        class={classNames('diagram', isPanning && 'is-panning')}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={stopPanning}
        onPointerCancel={stopPanning}
        onWheel={handleWheel}
      >
        <div
          class="diagram__canvas"
          style={{
            width: `${width * zoom}px`,
            height: `${height * zoom}px`,
          }}
        >
          <svg
            viewBox={`0 0 ${width} ${height}`}
            width={width}
            height={height}
            class="diagram__svg"
            role="img"
            aria-label="Request sequence diagram"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'top left',
            }}
          >
            <title>Request sequence diagram</title>
            {model.columns.map((column) => (
              <g key={column}>
                <text
                  x={columnX.get(column)}
                  y="24"
                  class="diagram__column-label"
                >
                  {column === ORIGIN_COLUMN ? 'origin' : column}
                </text>
                <line
                  x1={columnX.get(column)}
                  x2={columnX.get(column)}
                  y1="34"
                  y2={height - 18}
                  class="diagram__lifeline"
                />
              </g>
            ))}

            {model.rows.map((row, index) => {
              const y = rowOffset + index * rowHeight

              if (row.kind === 'group') {
                return (
                  <g key={row.traceId}>
                    <rect
                      x="20"
                      y={y - 26}
                      width={width - 40}
                      height="32"
                      class="diagram__group-bg"
                    />
                    <text x="32" y={y - 6} class="diagram__group-label">
                      Trace {compactId(row.traceId, 10, 6)}
                    </text>
                  </g>
                )
              }

              const fromX = columnX.get(row.fromNode) ?? 120
              const toX = columnX.get(row.toNode) ?? fromX
              const labelX = fromX + (toX - fromX) / 2
              const isSelected = selected.has(row.request.request_id)

              return (
                <g
                  key={row.request.request_id}
                  class={classNames(
                    'diagram__request',
                    isSelected && 'is-selected',
                  )}
                >
                  <a
                    href={`#request-${row.request.request_id}`}
                    aria-label={`Toggle request ${compactId(row.request.request_id)}`}
                    onClick={(event) => {
                      event.preventDefault()
                      onToggleRequest(row.request.request_id)
                    }}
                  >
                    <line
                      x1={fromX}
                      x2={toX}
                      y1={y}
                      y2={y}
                      class="diagram__request-hitbox"
                    />
                    <line
                      x1={fromX}
                      x2={toX}
                      y1={y}
                      y2={y}
                      class="diagram__request-line"
                    />
                    <circle
                      cx={fromX}
                      cy={y}
                      r="5"
                      class="diagram__request-node"
                    />
                    <circle
                      cx={toX}
                      cy={y}
                      r="5"
                      class="diagram__request-node"
                    />
                    <text
                      x={labelX}
                      y={y - 12}
                      textAnchor="middle"
                      class="diagram__request-label"
                    >
                      {row.label}
                    </text>
                  </a>
                </g>
              )
            })}
          </svg>
        </div>
      </div>
    </div>
  )
}
