import { describe, expect, it } from 'vitest'
import type { RequestSummary } from './types'
import {
  compareRequestsChronologically,
  filterRequestsByTimeShortcutAnchor,
  formatRequestState,
  getRequestState,
  intersectSelection,
  invertSelection,
  makeBrushRange,
  requestTitle,
} from './utils'

const baseRequest: RequestSummary = {
  request_id: 'req-1',
  trace_id: 'trace-1',
  node_name: 'proxy-a',
  hop_chain: 'trace-1@proxy-a',
  hop_nodes: ['proxy-a'],
  captured_at: '2026-03-22T10:00:00Z',
  updated_at: '2026-03-22T10:00:01Z',
  completed_at: null,
  request_method: 'GET',
  request_url: 'https://app1:9443/widgets?x=1',
  request_http_version: 'HTTP/1.1',
  request_headers: [['host', 'localhost:8443']],
  response_status_code: 200,
  response_http_version: 'HTTP/1.1',
  response_headers: [],
  request_complete: true,
  response_complete: true,
  websocket_open: false,
  error: null,
  complete: true,
}

describe('selection helpers', () => {
  it('keeps only visible selections after refetch', () => {
    expect(intersectSelection(['a', 'b', 'c'], ['b', 'd'])).toEqual(['b'])
  })

  it('inverts only within the filtered request set', () => {
    expect(invertSelection(['a', 'c'], ['a', 'b', 'c', 'd'])).toEqual(['b', 'd'])
  })

  it('keeps the exact clicked item as the frontend anchor when timestamps tie', () => {
    const requests = [
      {
        ...baseRequest,
        request_id: 'req-1',
        captured_at: '2026-03-22T10:00:00.123Z',
      },
      {
        ...baseRequest,
        request_id: 'req-2',
        captured_at: '2026-03-22T10:00:00.123Z',
      },
      {
        ...baseRequest,
        request_id: 'req-3',
        captured_at: '2026-03-22T10:00:00.124Z',
      },
    ].sort(compareRequestsChronologically)

    expect(
      filterRequestsByTimeShortcutAnchor(requests, {
        boundary: 'hide-before',
        requestId: 'req-2',
      }).map((request) => request.request_id),
    ).toEqual(['req-2', 'req-3'])

    expect(
      filterRequestsByTimeShortcutAnchor(requests, {
        boundary: 'hide-after',
        requestId: 'req-2',
      }).map((request) => request.request_id),
    ).toEqual(['req-1', 'req-2'])
  })
})

describe('makeBrushRange', () => {
  it('creates an inclusive bucket window for request filtering', () => {
    expect(
      makeBrushRange(
        'minute',
        '2026-03-22T10:00:00.000Z',
        '2026-03-22T10:05:00.000Z',
      ),
    ).toEqual({
      capturedAfter: '2026-03-22T09:59:59.999Z',
      capturedBefore: '2026-03-22T10:06:00.000Z',
    })
  })
})

describe('requestTitle', () => {
  it('prefers the original host header over the proxied upstream URL', () => {
    expect(requestTitle(baseRequest)).toBe('[GET localhost:8443/widgets?x=1]')
  })

  it('falls back to the request URL when no host header is present', () => {
    expect(
      requestTitle({
        ...baseRequest,
        request_headers: [],
      }),
    ).toBe('[GET app1/widgets?x=1]')
  })
})

describe('request state helpers', () => {
  it('prefers error over transport lifecycle flags', () => {
    expect(
      getRequestState({
        ...baseRequest,
        error: 'upstream failed',
        websocket_open: true,
      }),
    ).toBe('error')
  })

  it('formats a response-open request state for grid display', () => {
    expect(
      formatRequestState(
        getRequestState({
          ...baseRequest,
          response_complete: false,
          complete: false,
        }),
      ),
    ).toBe('Response open')
  })
})
