import {
  type CellClickedEventArgs,
  CompactSelection,
  DataEditor,
  type GridCell,
  GridCellKind,
  type GridColumn,
  type GridSelection,
  type Item,
  type Rectangle,
} from '@glideapps/glide-data-grid'
import { useEffect, useMemo, useRef, useState } from 'preact/hooks'
import '@glideapps/glide-data-grid/dist/index.css'
import type { RequestSummary } from '../types'
import {
  formatRequestState,
  formatTimestamp,
  getRequestState,
  type RequestState,
  requestDisplayUrl,
} from '../utils'
import { Icon } from './icon'

export type RequestGridSortKey =
  | 'method'
  | 'status'
  | 'node'
  | 'state'
  | 'url'
  | 'trace'
  | 'request'
  | 'captured'

export interface RequestGridSort {
  key: RequestGridSortKey
  direction: 'asc' | 'desc'
}

type RequestGridFilterKey = Exclude<RequestGridSortKey, 'captured'>

export interface RequestGridFilters {
  method: string
  status: string
  node: string
  state: '' | RequestState
  url: string
  trace: string
  request: string
}

interface RequestListProps {
  requests: RequestSummary[]
  totalRequests: number
  themeMode: 'light' | 'dark'
  page: number
  pageSize: number
  selectedIds: string[]
  filters: RequestGridFilters
  sort: RequestGridSort | null
  methods: string[]
  statuses: string[]
  nodes: string[]
  onFiltersChange: (next: RequestGridFilters) => void
  onSortChange: (next: RequestGridSort | null) => void
  onPageChange: (next: number) => void
  onSelectionChange: (requestIds: string[]) => void
  onTimeFilterShortcut: (
    request: RequestSummary,
    boundary: 'hide-before' | 'hide-after',
  ) => void
}

const DEFAULT_COLUMNS: Array<{ id: string; title: string; width: number }> = [
  { id: 'method', title: 'Method', width: 78 },
  { id: 'status', title: 'Status', width: 76 },
  { id: 'node', title: 'Node', width: 120 },
  { id: 'state', title: 'State', width: 118 },
  { id: 'url', title: 'URL', width: 360 },
  { id: 'trace', title: 'Trace ID', width: 220 },
  { id: 'request', title: 'Request ID', width: 220 },
  { id: 'captured', title: 'Captured', width: 178 },
]

const FILTERABLE_COLUMNS = new Set<RequestGridFilterKey>([
  'method',
  'status',
  'node',
  'state',
  'url',
  'trace',
  'request',
])

const GRID_THEMES = {
  light: {
    accentColor: '#205493',
    accentFg: '#ffffff',
    accentLight: '#e8f0fb',
    textDark: '#151b23',
    textMedium: '#667281',
    textLight: '#8793a1',
    bgCell: '#ffffff',
    bgCellMedium: '#f7f9fb',
    bgHeader: '#f7f9fb',
    bgHeaderHasFocus: '#eef3f8',
    bgBubble: '#eef3f8',
    horizontalBorderColor: '#d7dee7',
    verticalBorderColor: '#e6ebf1',
    headerBottomBorderColor: '#d7dee7',
    borderColor: '#d7dee7',
    linkColor: '#205493',
  },
  dark: {
    accentColor: '#0a84ff',
    accentFg: '#ffffff',
    accentLight: '#2c3d52',
    textDark: '#f5f5f7',
    textMedium: '#a1a1a6',
    textLight: '#8e8e93',
    bgCell: '#1c1c1e',
    bgCellMedium: '#242426',
    bgHeader: '#242426',
    bgHeaderHasFocus: '#2c2c2e',
    bgBubble: '#2c2c2e',
    horizontalBorderColor: '#3a3a3c',
    verticalBorderColor: '#2f2f31',
    headerBottomBorderColor: '#3a3a3c',
    borderColor: '#3a3a3c',
    linkColor: '#4da3ff',
  },
} as const

const SELECTED_ROW_THEMES = {
  light: {
    bgCell: '#e8f0fb',
    bgCellMedium: '#e8f0fb',
  },
  dark: {
    bgCell: '#2c3d52',
    bgCellMedium: '#2c3d52',
  },
} as const

function readStoredWidths() {
  if (typeof window === 'undefined') {
    return {}
  }

  try {
    const rawValue = window.localStorage.getItem('proxylens.requestGridColumns')
    if (!rawValue) {
      return {}
    }

    const parsedValue = JSON.parse(rawValue) as Record<string, number>
    return Object.fromEntries(
      Object.entries(parsedValue).filter(([, value]) => Number.isFinite(value)),
    )
  } catch {
    return {}
  }
}

function makeTextCell(value: string): GridCell {
  return {
    kind: GridCellKind.Text,
    data: value,
    displayData: value,
    allowOverlay: false,
    readonly: true,
  }
}

function getFilterValue(
  filters: RequestGridFilters,
  columnId: RequestGridFilterKey,
) {
  switch (columnId) {
    case 'method':
      return filters.method
    case 'status':
      return filters.status
    case 'node':
      return filters.node
    case 'state':
      return filters.state
    case 'url':
      return filters.url
    case 'trace':
      return filters.trace
    case 'request':
      return filters.request
  }
}

function collectSelectedRowIndexes(selection: GridSelection) {
  const rowIndexes = new Set<number>()

  for (const rowIndex of selection.rows.toArray()) {
    rowIndexes.add(rowIndex)
  }

  const addRangeRows = (range: { y: number; height: number }) => {
    for (
      let rowIndex = range.y;
      rowIndex < range.y + range.height;
      rowIndex += 1
    ) {
      rowIndexes.add(rowIndex)
    }
  }

  if (selection.current) {
    rowIndexes.add(selection.current.cell[1])
    addRangeRows(selection.current.range)

    for (const range of selection.current.rangeStack) {
      addRangeRows(range)
    }
  }

  return [...rowIndexes].sort((left, right) => left - right)
}

export function RequestList({
  requests,
  totalRequests,
  themeMode,
  page,
  pageSize,
  selectedIds,
  filters,
  sort,
  methods,
  statuses,
  nodes,
  onFiltersChange,
  onSortChange,
  onPageChange,
  onSelectionChange,
  onTimeFilterShortcut,
}: RequestListProps) {
  const editorRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [columnWidths, setColumnWidths] =
    useState<Record<string, number>>(readStoredWidths)
  const [headerMenu, setHeaderMenu] = useState<{
    columnId: RequestGridFilterKey
    left: number
    top: number
    draft: string
  } | null>(null)
  const [rowMenu, setRowMenu] = useState<{
    request: RequestSummary
    left: number
    top: number
  } | null>(null)
  const headerInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    window.localStorage.setItem(
      'proxylens.requestGridColumns',
      JSON.stringify(columnWidths),
    )
  }, [columnWidths])

  useEffect(() => {
    if (!headerMenu && !rowMenu) {
      return
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setHeaderMenu(null)
        setRowMenu(null)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setHeaderMenu(null)
        setRowMenu(null)
      }
    }

    window.addEventListener('pointerdown', handlePointerDown)
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [headerMenu, rowMenu])

  const columns = useMemo<GridColumn[]>(
    () =>
      DEFAULT_COLUMNS.map((column) => ({
        id: column.id,
        title: `${column.title}${
          FILTERABLE_COLUMNS.has(column.id as RequestGridFilterKey) &&
          getFilterValue(filters, column.id as RequestGridFilterKey)
            ? ' •'
            : ''
        }${sort?.key === column.id ? ` ${sort.direction === 'asc' ? '↑' : '↓'}` : ''}`,
        hasMenu: FILTERABLE_COLUMNS.has(column.id as RequestGridFilterKey),
        width: columnWidths[column.id] ?? column.width,
      })),
    [columnWidths, filters, sort],
  )

  const rowIndexById = useMemo(
    () =>
      new Map(
        requests.map((request, index) => [request.request_id, index] as const),
      ),
    [requests],
  )

  const selectedRows = useMemo(() => {
    let rows = CompactSelection.empty()

    for (const requestId of selectedIds) {
      const rowIndex = rowIndexById.get(requestId)
      if (rowIndex !== undefined) {
        rows = rows.add(rowIndex)
      }
    }

    return rows
  }, [rowIndexById, selectedIds])

  const selectedRowSet = useMemo(
    () => new Set(selectedRows.toArray()),
    [selectedRows],
  )

  const gridSelection = useMemo<GridSelection>(
    () => ({
      rows: selectedRows,
      columns: CompactSelection.empty(),
      current:
        selectedRows.first() === undefined
          ? undefined
          : {
              cell: [0, selectedRows.first() as number],
              range: {
                x: 0,
                y: selectedRows.first() as number,
                width: columns.length,
                height: 1,
              },
              rangeStack: [],
            },
    }),
    [columns.length, selectedRows],
  )

  const getCellContent = useMemo(
    () =>
      ([col, row]: Item): GridCell => {
        const request = requests[row]
        const columnId = DEFAULT_COLUMNS[col]?.id

        if (!request || !columnId) {
          return makeTextCell('')
        }

        switch (columnId) {
          case 'method':
            return makeTextCell(request.request_method ?? '—')
          case 'status':
            return makeTextCell(request.response_status_code?.toString() ?? '—')
          case 'node':
            return makeTextCell(request.node_name)
          case 'state':
            return makeTextCell(formatRequestState(getRequestState(request)))
          case 'url':
            return makeTextCell(requestDisplayUrl(request))
          case 'trace':
            return makeTextCell(request.trace_id)
          case 'request':
            return makeTextCell(request.request_id)
          case 'captured':
            return makeTextCell(formatTimestamp(request.captured_at))
          default:
            return makeTextCell('')
        }
      },
    [requests],
  )

  const handleGridSelectionChange = (nextSelection: GridSelection) => {
    const rowIndexes = collectSelectedRowIndexes(nextSelection)

    onSelectionChange(
      rowIndexes
        .map((rowIndex) => requests[rowIndex]?.request_id)
        .filter((requestId): requestId is string => requestId !== undefined),
    )
  }

  const applyHeaderFilter = (columnId: RequestGridFilterKey, value: string) => {
    const nextValue = value.trim()

    switch (columnId) {
      case 'method':
        onFiltersChange({ ...filters, method: nextValue.toUpperCase() })
        return
      case 'status':
        onFiltersChange({ ...filters, status: nextValue })
        return
      case 'node':
        onFiltersChange({ ...filters, node: nextValue })
        return
      case 'state':
        onFiltersChange({
          ...filters,
          state: nextValue as RequestGridFilters['state'],
        })
        return
      case 'url':
        onFiltersChange({ ...filters, url: nextValue })
        return
      case 'trace':
        onFiltersChange({ ...filters, trace: nextValue })
        return
      case 'request':
        onFiltersChange({ ...filters, request: nextValue })
    }
  }

  const handleHeaderMenuClick = (
    columnIndex: number,
    screenPosition: Rectangle,
  ) => {
    const columnId = DEFAULT_COLUMNS[columnIndex]?.id as
      | RequestGridFilterKey
      | undefined
    if (!columnId || !FILTERABLE_COLUMNS.has(columnId)) {
      return
    }

    setRowMenu(null)
    setHeaderMenu({
      columnId,
      left: screenPosition.x,
      top: screenPosition.y + screenPosition.height + 4,
      draft: getFilterValue(filters, columnId),
    })
  }

  const handleCellContextMenu = (_cell: Item, event: CellClickedEventArgs) => {
    const request = requests[event.location[1]]
    if (!request) {
      return
    }

    event.preventDefault()
    setHeaderMenu(null)
    setRowMenu({
      request,
      left: event.bounds.x + event.localEventX,
      top: event.bounds.y + event.localEventY + 4,
    })
  }

  const totalPages = Math.max(1, Math.ceil(totalRequests / pageSize))
  const pageStart = totalRequests === 0 ? 0 : page * pageSize + 1
  const pageEnd = totalRequests === 0 ? 0 : page * pageSize + requests.length

  return (
    <div class="request-grid">
      <div class="request-grid__editor" ref={editorRef}>
        <DataEditor
          columns={columns}
          rows={requests.length}
          getCellContent={getCellContent}
          width="100%"
          height="100%"
          rowHeight={26}
          headerHeight={24}
          smoothScrollX={false}
          smoothScrollY={false}
          rowMarkers={{
            kind: 'checkbox-visible',
            width: 34,
            checkboxStyle: 'square',
          }}
          rowSelect="multi"
          rowSelectionMode="auto"
          rowSelectionBlending="mixed"
          rangeSelect="multi-rect"
          rangeSelectionBlending="mixed"
          columnSelect="none"
          gridSelection={gridSelection}
          onGridSelectionChange={handleGridSelectionChange}
          onHeaderClicked={(columnIndex) => {
            const nextKey = DEFAULT_COLUMNS[columnIndex]?.id as
              | RequestGridSortKey
              | undefined
            if (!nextKey) {
              return
            }

            if (sort?.key !== nextKey) {
              onSortChange({ key: nextKey, direction: 'asc' })
              return
            }

            if (sort.direction === 'asc') {
              onSortChange({ key: nextKey, direction: 'desc' })
              return
            }

            onSortChange(null)
          }}
          onHeaderMenuClick={(columnIndex, screenPosition) => {
            handleHeaderMenuClick(columnIndex, screenPosition)
          }}
          onCellContextMenu={handleCellContextMenu}
          onColumnResize={(_, newSize, columnIndex) => {
            const columnId = DEFAULT_COLUMNS[columnIndex]?.id
            if (!columnId) {
              return
            }

            setColumnWidths((current) => ({
              ...current,
              [columnId]: Math.max(60, Math.round(newSize)),
            }))
          }}
          getRowThemeOverride={(row) =>
            selectedRowSet.has(row) ? SELECTED_ROW_THEMES[themeMode] : undefined
          }
          theme={GRID_THEMES[themeMode]}
        />

        {requests.length === 0 && (
          <div class="request-grid__empty">
            No requests match the current filters.
          </div>
        )}
      </div>

      <div class="request-grid__pagination">
        <span>
          {pageStart}-{pageEnd} of {totalRequests}
        </span>
        <div class="request-grid__pagination-actions">
          <button
            type="button"
            class="button button--ghost"
            disabled={page <= 0}
            onClick={() => onPageChange(page - 1)}
          >
            <span class="button__content">
              <Icon name="chevron-left" class="button__icon" />
              <span>Prev</span>
            </span>
          </button>
          <span>
            Page {totalRequests === 0 ? 0 : page + 1} of {totalPages}
          </span>
          <button
            type="button"
            class="button button--ghost"
            disabled={page >= totalPages - 1 || totalRequests === 0}
            onClick={() => onPageChange(page + 1)}
          >
            <span class="button__content">
              <span>Next</span>
              <Icon name="chevron-right" class="button__icon" />
            </span>
          </button>
        </div>
      </div>

      {headerMenu && (
        <div
          class="grid-menu"
          ref={menuRef}
          style={{
            left: `${headerMenu.left}px`,
            top: `${headerMenu.top}px`,
          }}
        >
          <div class="grid-menu__title">
            Filter{' '}
            {
              DEFAULT_COLUMNS.find(
                (column) => column.id === headerMenu.columnId,
              )?.title
            }
          </div>

          {headerMenu.columnId === 'method' ||
          headerMenu.columnId === 'status' ||
          headerMenu.columnId === 'node' ||
          headerMenu.columnId === 'state' ? (
            <select
              value={headerMenu.draft}
              onInput={(event) =>
                setHeaderMenu((current) =>
                  current
                    ? {
                        ...current,
                        draft: (event.currentTarget as HTMLSelectElement).value,
                      }
                    : current,
                )
              }
            >
              <option value="">All</option>
              {headerMenu.columnId === 'method' &&
                methods.map((method) => (
                  <option key={method} value={method}>
                    {method}
                  </option>
                ))}
              {headerMenu.columnId === 'status' &&
                statuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              {headerMenu.columnId === 'node' &&
                nodes.map((node) => (
                  <option key={node} value={node}>
                    {node}
                  </option>
                ))}
              {headerMenu.columnId === 'state' && (
                <>
                  <option value="complete">Complete</option>
                  <option value="request-open">Request open</option>
                  <option value="response-open">Response open</option>
                  <option value="websocket-open">WebSocket open</option>
                  <option value="error">Error</option>
                </>
              )}
            </select>
          ) : (
            <input
              ref={(node) => {
                headerInputRef.current = node
                node?.focus()
              }}
              value={headerMenu.draft}
              placeholder="Contains…"
              onInput={(event) =>
                setHeaderMenu((current) =>
                  current
                    ? {
                        ...current,
                        draft: (event.currentTarget as HTMLInputElement).value,
                      }
                    : current,
                )
              }
              onKeyDown={(event) => {
                if (event.key !== 'Enter') {
                  return
                }

                applyHeaderFilter(headerMenu.columnId, headerMenu.draft)
                setHeaderMenu(null)
              }}
            />
          )}

          <div class="grid-menu__actions">
            <button
              type="button"
              class="button button--ghost"
              onClick={() => {
                applyHeaderFilter(headerMenu.columnId, '')
                setHeaderMenu(null)
              }}
            >
              <span class="button__content">
                <Icon name="x" class="button__icon" />
                <span>Clear</span>
              </span>
            </button>
            <button
              type="button"
              class="button button--accent"
              onClick={() => {
                applyHeaderFilter(headerMenu.columnId, headerMenu.draft)
                setHeaderMenu(null)
              }}
            >
              <span class="button__content">
                <Icon name="apply" class="button__icon" />
                <span>Apply</span>
              </span>
            </button>
          </div>
        </div>
      )}

      {rowMenu && (
        <div
          class="grid-menu"
          ref={menuRef}
          style={{
            left: `${rowMenu.left}px`,
            top: `${rowMenu.top}px`,
          }}
        >
          <div class="grid-menu__title">
            Captured {formatTimestamp(rowMenu.request.captured_at)}
          </div>
          <button
            type="button"
            class="button button--ghost"
            onClick={() => {
              onTimeFilterShortcut(rowMenu.request, 'hide-before')
              setRowMenu(null)
            }}
          >
            <span class="button__content">
              <Icon name="chevrons-left" class="button__icon" />
              <span>Hide requests before this</span>
            </span>
          </button>
          <button
            type="button"
            class="button button--ghost"
            onClick={() => {
              onTimeFilterShortcut(rowMenu.request, 'hide-after')
              setRowMenu(null)
            }}
          >
            <span class="button__content">
              <Icon name="chevrons-right" class="button__icon" />
              <span>Hide requests after this</span>
            </span>
          </button>
        </div>
      )}
    </div>
  )
}
