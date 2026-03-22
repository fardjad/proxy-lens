import type { RequestSummary } from '../types'
import { classNames, compactId, displayUrl, formatTimestamp } from '../utils'

interface RequestListProps {
  requests: RequestSummary[]
  selectedIds: string[]
  onToggleRequest: (requestId: string) => void
}

export function RequestList({
  requests,
  selectedIds,
  onToggleRequest,
}: RequestListProps) {
  const selected = new Set(selectedIds)

  if (requests.length === 0) {
    return <div class="panel-empty">No requests match the current filters.</div>
  }

  return (
    <div class="request-list" role="list">
      {requests.map((request) => {
        const isSelected = selected.has(request.request_id)

        return (
          <button
            key={request.request_id}
            type="button"
            role="listitem"
            class={classNames('request-row', isSelected && 'is-selected')}
            onClick={() => onToggleRequest(request.request_id)}
          >
            <div class="request-row__primary">
              <span class="request-pill request-pill--method">
                {request.request_method ?? '???'}
              </span>
              <span class="request-row__url" title={request.request_url ?? 'Unknown URL'}>
                {displayUrl(request.request_url)}
              </span>
            </div>
            <div class="request-row__meta">
              <span>{request.node_name}</span>
              <span>Status {request.response_status_code ?? '—'}</span>
              <span>{formatTimestamp(request.captured_at)}</span>
              <span title={request.trace_id}>Trace {compactId(request.trace_id)}</span>
            </div>
          </button>
        )
      })}
    </div>
  )
}
