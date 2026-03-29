import { render, screen } from '@testing-library/preact'
import { describe, expect, it } from 'vitest'
import type { RequestDetail } from '../types'
import { DetailsSidebar } from './details-sidebar'

const detail: RequestDetail = {
  request_id: 'req-1',
  trace_id: 'trace-1',
  node_name: 'proxy-a',
  hop_chain: 'trace-1@proxy-a',
  hop_nodes: ['proxy-a'],
  captured_at: '2026-03-22T10:00:00Z',
  updated_at: '2026-03-22T10:00:01Z',
  completed_at: '2026-03-22T10:00:01Z',
  request_method: 'GET',
  request_url: 'https://example.test/widgets',
  request_http_version: 'HTTP/1.1',
  request_headers: [['content-type', 'application/json']],
  response_status_code: 200,
  response_http_version: 'HTTP/1.1',
  response_headers: [['content-type', 'application/json']],
  request_complete: true,
  response_complete: true,
  websocket_open: false,
  error: null,
  complete: true,
  request_trailers: [],
  request_body_size: 0,
  request_body_blob_id: null,
  request_body_complete: true,
  response_trailers: [],
  response_body_size: 0,
  response_body_blob_id: null,
  response_body_complete: true,
  response_started: true,
  request_started: true,
  websocket_url: null,
  websocket_http_version: null,
  websocket_headers: [],
  websocket_close_code: null,
  websocket_messages: [],
  request_body_chunks: [],
  response_body_chunks: [],
}

describe('DetailsSidebar', () => {
  it('shows an empty state with no selection', () => {
    render(
      <DetailsSidebar
        selectedCount={0}
        detailState={{ status: 'idle' }}
        requestBodyState={{ status: 'idle' }}
        responseBodyState={{ status: 'idle' }}
      />,
    )

    expect(
      screen.getByText(
        /select a request from the list or the sequence diagram/i,
      ),
    ).toBeInTheDocument()
  })

  it('shows a multi-select message when more than one request is selected', () => {
    render(
      <DetailsSidebar
        selectedCount={2}
        detailState={{ status: 'idle' }}
        requestBodyState={{ status: 'idle' }}
        responseBodyState={{ status: 'idle' }}
      />,
    )

    expect(screen.getByText(/2 requests selected/i)).toBeInTheDocument()
  })

  it('shows request details and missing body states for a single selection', () => {
    render(
      <DetailsSidebar
        selectedCount={1}
        selectedRequestId="req-1"
        detailState={{ status: 'ready', data: detail }}
        requestBodyState={{ status: 'missing' }}
        responseBodyState={{ status: 'missing' }}
      />,
    )

    expect(screen.getByText(/example\.test\/widgets/i)).toBeInTheDocument()
    expect(screen.getByText(/trace id/i)).toBeInTheDocument()
    expect(screen.getByText('trace-1')).toBeInTheDocument()
    expect(screen.getAllByText(/no stored body/i)).toHaveLength(2)
  })
})
