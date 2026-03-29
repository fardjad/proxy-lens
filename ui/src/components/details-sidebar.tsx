import { useEffect, useMemo, useState } from 'preact/hooks'
import type { BodyState, LoadState, RequestDetail } from '../types'
import { displayUrl, formatBytes, formatTimestamp, headerValue } from '../utils'

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
  const [prettyJson, setPrettyJson] = useState(false)

  const effectiveContentType =
    bodyState.status === 'ready'
      ? bodyState.data.contentType || fallbackContentType
      : fallbackContentType

  const formattedJson = useMemo(() => {
    if (bodyState.status !== 'ready' || bodyState.preview.kind !== 'text') {
      return null
    }

    try {
      return JSON.stringify(JSON.parse(bodyState.preview.text), null, 2)
    } catch {
      return null
    }
  }, [bodyState])

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

    const stableBlob = new Blob([Uint8Array.from(bodyState.data.bytes)], {
      type: effectiveContentType ?? 'application/octet-stream',
    })
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
      <div class="details-section__header">
        <h3>{title}</h3>
        {formattedJson && (
          <button
            type="button"
            class="button button--ghost"
            onClick={() => setPrettyJson((current) => !current)}
          >
            {prettyJson ? 'Raw' : 'Pretty JSON'}
          </button>
        )}
      </div>
      {bodyState.status === 'idle' && (
        <div class="panel-empty">Select one request to load body data.</div>
      )}
      {bodyState.status === 'loading' && (
        <div class="panel-empty">Loading body…</div>
      )}
      {bodyState.status === 'missing' && (
        <div class="panel-empty">
          No stored body for this side of the exchange.
        </div>
      )}
      {bodyState.status === 'error' && (
        <div class="panel-empty">{bodyState.error}</div>
      )}
      {bodyState.status === 'ready' && bodyState.preview.kind === 'text' && (
        <pre class="body-preview">
          {prettyJson && formattedJson ? formattedJson : bodyState.preview.text}
        </pre>
      )}
      {bodyState.status === 'ready' && bodyState.preview.kind === 'binary' && (
        <div class="binary-preview">
          <div>
            Binary payload · {formatBytes(bodyState.data.bytes.byteLength)}
            {effectiveContentType ? ` · ${effectiveContentType}` : ''}
          </div>
          {downloadUrl && (
            <a
              class="button button--ghost"
              href={downloadUrl}
              download={`${title.toLowerCase().replace(/\s+/g, '-')}.bin`}
            >
              Download body
            </a>
          )}
        </div>
      )}
    </section>
  )
}

function KeyValueList({
  entries,
}: {
  entries: Array<[label: string, value: string]>
}) {
  return (
    <dl class="detail-list">
      {entries.map(([label, value]) => (
        <div key={label} class="detail-list__item">
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
      <div class="details-section__header">
        <h3>{title}</h3>
      </div>
      {headers.length === 0 ? (
        <div class="panel-empty">None recorded.</div>
      ) : (
        <div class="header-list">
          {headers.map(([key, value]) => (
            <div class="header-list__row" key={`${key}:${value}`}>
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
  const detail = detailState.status === 'ready' ? detailState.data : null

  const requestContentType = useMemo(
    () => (detail ? headerValue(detail.request_headers, 'content-type') : null),
    [detail],
  )
  const responseContentType = useMemo(
    () =>
      detail ? headerValue(detail.response_headers, 'content-type') : null,
    [detail],
  )

  return (
    <aside class="panel panel--sidebar">
      {selectedCount === 0 && (
        <div class="panel-empty">
          Select a request from the list or the sequence diagram.
        </div>
      )}

      {selectedCount > 1 && (
        <div class="panel-empty">
          {selectedCount} requests selected. Narrow to one request to inspect
          headers and bodies.
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
            <div class="details-section__header">
              <h3>Request</h3>
            </div>
            <KeyValueList
              entries={[
                ['URL', displayUrl(detail.request_url, 'Unknown request')],
                ['Trace ID', detail.trace_id],
                ['Request ID', detail.request_id],
                ['Node', detail.node_name],
                ['Method', detail.request_method ?? '—'],
                ['Status', detail.response_status_code?.toString() ?? '—'],
                ['Captured', formatTimestamp(detail.captured_at)],
                ['Updated', formatTimestamp(detail.updated_at)],
                ['Complete', detail.complete ? 'Yes' : 'No'],
                ['Request complete', detail.request_complete ? 'Yes' : 'No'],
                ['Response complete', detail.response_complete ? 'Yes' : 'No'],
                ['WebSocket', detail.websocket_open ? 'Open' : 'Closed'],
                ['Error', detail.error ?? '—'],
              ]}
            />
          </section>

          <HeaderTable
            title="Request headers"
            headers={detail.request_headers}
          />
          <HeaderTable
            title="Request trailers"
            headers={detail.request_trailers}
          />
          <BodyPanel
            title="Request body"
            bodyState={requestBodyState}
            fallbackContentType={requestContentType}
          />
          <HeaderTable
            title="Response headers"
            headers={detail.response_headers}
          />
          <HeaderTable
            title="Response trailers"
            headers={detail.response_trailers}
          />
          <BodyPanel
            title="Response body"
            bodyState={responseBodyState}
            fallbackContentType={responseContentType}
          />

          <section class="details-section">
            <div class="details-section__header">
              <h3>WebSocket messages</h3>
            </div>
            {detail.websocket_messages.length === 0 ? (
              <div class="panel-empty">No websocket frames captured.</div>
            ) : (
              <div class="websocket-log">
                {detail.websocket_messages.map((message) => (
                  <div class="websocket-log__entry" key={message.event_index}>
                    <strong>{message.direction}</strong>
                    <span>{message.payload_type}</span>
                    <span>
                      {message.payload_text ??
                        `Blob ${message.blob_id ?? 'unknown'}`}
                    </span>
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
