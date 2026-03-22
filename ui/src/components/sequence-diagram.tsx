import type { DiagramMode, RequestSummary } from '../types'
import { buildSequenceDiagramModel, ORIGIN_COLUMN } from '../diagram'
import { classNames, compactId } from '../utils'

interface SequenceDiagramProps {
  requests: RequestSummary[]
  selectedIds: string[]
  mode: DiagramMode
  onToggleRequest: (requestId: string) => void
  onModeChange: (mode: DiagramMode) => void
}

export function SequenceDiagram({
  requests,
  selectedIds,
  mode,
  onToggleRequest,
  onModeChange,
}: SequenceDiagramProps) {
  const model = buildSequenceDiagramModel(requests, mode)
  const selected = new Set(selectedIds)

  if (requests.length === 0) {
    return (
      <div class="panel panel--diagram">
        <div class="panel__header">
          <div>
            <h2>Sequence diagram</h2>
            <p>Edges appear here once requests are loaded.</p>
          </div>
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
      <div class="panel__header">
        <div>
          <h2>Sequence diagram</h2>
          <p>Click a line to toggle the matching request row.</p>
        </div>
        <div class="segmented">
          <button
            type="button"
            class={classNames('segmented__option', mode === 'grouped' && 'is-active')}
            onClick={() => onModeChange('grouped')}
          >
            Grouped
          </button>
          <button
            type="button"
            class={classNames('segmented__option', mode === 'flat' && 'is-active')}
            onClick={() => onModeChange('flat')}
          >
            Flat
          </button>
        </div>
      </div>

      <div class="diagram">
        <svg viewBox={`0 0 ${width} ${height}`} class="diagram__svg" role="img">
          {model.columns.map((column) => (
            <g key={column}>
              <text x={columnX.get(column)} y="24" class="diagram__column-label">
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
                <g key={`group-${row.traceId}-${index}`}>
                  <rect x="20" y={y - 26} width={width - 40} height="32" class="diagram__group-bg" />
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
                class={classNames('diagram__request', isSelected && 'is-selected')}
              >
                <line
                  x1={fromX}
                  x2={toX}
                  y1={y}
                  y2={y}
                  class="diagram__request-hitbox"
                  onClick={() => onToggleRequest(row.request.request_id)}
                />
                <line
                  x1={fromX}
                  x2={toX}
                  y1={y}
                  y2={y}
                  class="diagram__request-line"
                />
                <circle cx={fromX} cy={y} r="5" class="diagram__request-node" />
                <circle cx={toX} cy={y} r="5" class="diagram__request-node" />
                <text x={labelX} y={y - 12} textAnchor="middle" class="diagram__request-label">
                  {row.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}
