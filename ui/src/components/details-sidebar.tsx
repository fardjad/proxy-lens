import { useEffect, useMemo, useState } from 'preact/hooks'
import type { BodyState, LoadState, RequestDetail } from '../types'
import {
  classNames,
  compactId,
  displayUrl,
  formatBytes,
  formatTimestamp,
  headerValue,
} from '../utils'

interface DetailsSidebarProps {
  selectedCount: number
  selectedRequestId?: string
  detailState: LoadState<RequestDetail>
  requestBodyState: BodyState
  responseBodyState: BodyState
}

function BodyPanel({
  title,
  bodyState,
  fallbackContentType,
}: {
  title: string
  bodyState: BodyState
  fallbackContentType: string | null
}) {
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)

  const effectiveContentType =
    bodyState.status === 'ready'
      ? bodyState.data.contentType || fallbackContentType
      : fallbackContentType

  useEffect(() => {
    if (bodyState.status !== 'ready' || bodyState.preview.kind !== 'binary') {
      setDownloadUrl((current) => {
        if (current) {
          URL.revokeObjectURL(current)
        }
        return null
      })
      return
    }

    const stableBlob = new Blob(
      [
        Uint8Array.from(bodyState.data.bytes),
      ],
      {
        type: effectiveContentType ?? 'application/octet-stream',
      },
    )
    const nextUrl = URL.createObjectURL(stableBlob)
    setDownloadUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current)
      }
      return nextUrl
    })

    return () => URL.revokeObjectURL(nextUrl)
  }, [bodyState, effectiveContentType])

  return (
    <section class="details-section">
      <h3>{title}</h3>
      {bodyState.status === 'idle' && <div class="panel-empty">Select one request to load body data.</div>}
      {bodyState.status === 'loading' && <div class="panel-empty">Loading body…</div>}
      {bodyState.status === 'missing' && <div class="panel-empty">No stored body for this side of the exchange.</div>}
      {bodyState.status === 'error' && <div class="panel-empty">{bodyState.error}</div>}
      {bodyState.status === 'ready' && bodyState.preview.kind === 'text' && (
        <pre class="body-preview">{bodyState.preview.text}</pre>
      )}
      {bodyState.status === 'ready' && bodyState.preview.kind === 'binary' && (
        <div class="binary-preview">
          <div>
            Binary payload · {formatBytes(bodyState.data.bytes.byteLength)}
            {effectiveContentType ? ` · ${effectiveContentType}` : ''}
          </div>
          {downloadUrl && (
            <a class="button button--ghost" href={downloadUrl} download={`${title.toLowerCase().replace(/\s+/g, '-')}.bin`}>
              Download body
            </a>
          )}
        </div>
      )}
    </section>
  )
}

function KeyValueGrid({
  entries,
}: {
  entries: Array<[label: string, value: string]>
}) {
  return (
    <dl class="detail-grid">
      {entries.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function HeaderTable({
  title,
  headers,
}: {
  title: string
  headers: Array<[string, string]>
}) {
  return (
    <section class="details-section">
      <h3>{title}</h3>
      {headers.length === 0 ? (
        <div class="panel-empty">None recorded.</div>
      ) : (
        <div class="header-list">
          {headers.map(([key, value], index) => (
            <div class="header-list__row" key={`${key}-${index}`}>
              <strong>{key}</strong>
              <span>{value}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export function DetailsSidebar({
  selectedCount,
  selectedRequestId,
  detailState,
  requestBodyState,
  responseBodyState,
}: DetailsSidebarProps) {
  const detail =
    detailState.status === 'ready'
      ? detailState.data
      : null

  const requestContentType = useMemo(
    () => (detail ? headerValue(detail.request_headers, 'content-type') : null),
    [detail],
  )
  const responseContentType = useMemo(
    () => (detail ? headerValue(detail.response_headers, 'content-type') : null),
    [detail],
  )

  return (
    <aside class="panel panel--sidebar">
      <div class="panel__header">
        <div>
          <h2>Request details</h2>
          <p>Single-selection inspector for bodies, metadata, and websocket data.</p>
        </div>
      </div>

      {selectedCount === 0 && (
        <div class="panel-empty">Select a request from the list or the sequence diagram.</div>
      )}

      {selectedCount > 1 && (
        <div class="panel-empty">
          {selectedCount} requests selected. Narrow to one request to inspect headers and bodies.
        </div>
      )}

      {selectedCount === 1 && detailState.status === 'loading' && (
        <div class="panel-empty">Loading request {selectedRequestId}…</div>
      )}

      {selectedCount === 1 && detailState.status === 'error' && (
        <div class="panel-empty">{detailState.error}</div>
      )}

      {selectedCount === 1 && detail && (
        <div class="details">
          <section class="details-section">
            <div class="trace-badge">Trace {compactId(detail.trace_id, 12, 6)}</div>
            <h3>{displayUrl(detail.request_url, 'Unknown request')}</h3>
            <KeyValueGrid
              entries={[
                ['Request ID', detail.request_id],
                ['Node', detail.node_name],
                ['Method', detail.request_method ?? '—'],
                ['Status', detail.response_status_code?.toString() ?? '—'],
                ['Captured', formatTimestamp(detail.captured_at)],
                ['Updated', formatTimestamp(detail.updated_at)],
                ['Complete', detail.complete ? 'Yes' : 'No'],
                ['Error', detail.error ?? '—'],
              ]}
            />
          </section>

          <section class="details-section">
            <h3>Lifecycle</h3>
            <div class="status-strip">
              <span class={classNames('status-chip', detail.request_complete && 'is-good')}>
                Request {detail.request_complete ? 'complete' : 'open'}
              </span>
              <span class={classNames('status-chip', detail.response_complete && 'is-good')}>
                Response {detail.response_complete ? 'complete' : 'open'}
              </span>
              <span class={classNames('status-chip', detail.websocket_open && 'is-live')}>
                WebSocket {detail.websocket_open ? 'open' : 'closed'}
              </span>
            </div>
          </section>

          <HeaderTable title="Request headers" headers={detail.request_headers} />
          <HeaderTable title="Request trailers" headers={detail.request_trailers} />
          <BodyPanel
            title="Request body"
            bodyState={requestBodyState}
            fallbackContentType={requestContentType}
          />
          <HeaderTable title="Response headers" headers={detail.response_headers} />
          <HeaderTable title="Response trailers" headers={detail.response_trailers} />
          <BodyPanel
            title="Response body"
            bodyState={responseBodyState}
            fallbackContentType={responseContentType}
          />

          <section class="details-section">
            <h3>WebSocket messages</h3>
            {detail.websocket_messages.length === 0 ? (
              <div class="panel-empty">No websocket frames captured.</div>
            ) : (
              <div class="websocket-log">
                {detail.websocket_messages.map((message) => (
                  <div class="websocket-log__entry" key={message.event_index}>
                    <strong>{message.direction}</strong>
                    <span>{message.payload_type}</span>
                    <span>{message.payload_text ?? `Blob ${message.blob_id ?? 'unknown'}`}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </aside>
  )
}
