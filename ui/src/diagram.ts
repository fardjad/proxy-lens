import type { DiagramMode, RequestSummary } from './types'
import { requestTitle } from './utils'

export interface DiagramRequestRow {
  kind: 'request'
  request: RequestSummary
  fromNode: string
  toNode: string
  label: string
}

export interface DiagramGroupRow {
  kind: 'group'
  traceId: string
}

export type DiagramRow = DiagramRequestRow | DiagramGroupRow

export interface DiagramModel {
  columns: string[]
  rows: DiagramRow[]
}

export const ORIGIN_COLUMN = 'origin'

export function buildSequenceDiagramModel(
  requests: RequestSummary[],
  mode: DiagramMode,
): DiagramModel {
  const columns = new Set<string>([ORIGIN_COLUMN])

  for (const request of requests) {
    for (const node of request.hop_nodes) {
      columns.add(node)
    }
  }

  if (mode === 'flat') {
    return {
      columns: [...columns],
      rows: requests.map(buildRequestRow),
    }
  }

  const rows: DiagramRow[] = []
  let previousTraceId: string | null = null

  for (const request of requests) {
    if (request.trace_id !== previousTraceId) {
      rows.push({ kind: 'group', traceId: request.trace_id })
      previousTraceId = request.trace_id
    }

    rows.push(buildRequestRow(request))
  }

  return {
    columns: [...columns],
    rows,
  }
}

function buildRequestRow(request: RequestSummary): DiagramRequestRow {
  const fromNode =
    request.hop_nodes.length >= 2
      ? request.hop_nodes[request.hop_nodes.length - 2]
      : ORIGIN_COLUMN

  return {
    kind: 'request',
    request,
    fromNode,
    toNode: request.node_name,
    label: requestTitle(request),
  }
}
