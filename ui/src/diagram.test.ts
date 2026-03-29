import { describe, expect, it } from 'bun:test'
import { buildSequenceDiagramModel, ORIGIN_COLUMN } from './diagram'
import type { RequestSummary } from './types'

const requestA: RequestSummary = {
  request_id: 'req-a',
  trace_id: 'trace-1',
  node_name: 'proxy-a',
  hop_chain: 'trace-1@proxy-a',
  hop_nodes: ['proxy-a'],
  captured_at: '2026-03-22T10:00:00Z',
  updated_at: '2026-03-22T10:00:01Z',
  completed_at: null,
  request_method: 'GET',
  request_url: 'https://example.test/a',
  request_http_version: 'HTTP/1.1',
  request_headers: [],
  response_status_code: 200,
  response_http_version: 'HTTP/1.1',
  response_headers: [],
  request_complete: true,
  response_complete: true,
  websocket_open: false,
  error: null,
  complete: true,
}

const requestB: RequestSummary = {
  ...requestA,
  request_id: 'req-b',
  trace_id: 'trace-2',
  node_name: 'proxy-b',
  hop_chain: 'trace-2@edge-a,proxy-b',
  hop_nodes: ['edge-a', 'proxy-b'],
  captured_at: '2026-03-22T10:01:00Z',
  request_url: 'https://example.test/b',
}

describe('buildSequenceDiagramModel', () => {
  it('uses a synthetic origin for single-hop requests', () => {
    const model = buildSequenceDiagramModel([requestA], 'flat')
    const row = model.rows[0]

    expect(model.columns[0]).toBe(ORIGIN_COLUMN)
    expect(row.kind).toBe('request')
    if (row.kind === 'request') {
      expect(row.fromNode).toBe(ORIGIN_COLUMN)
      expect(row.toNode).toBe('proxy-a')
    }
  })

  it('adds trace separators in grouped mode', () => {
    const grouped = buildSequenceDiagramModel([requestA, requestB], 'grouped')
    const flat = buildSequenceDiagramModel([requestA, requestB], 'flat')

    expect(grouped.rows.filter((row) => row.kind === 'group')).toHaveLength(2)
    expect(flat.rows.filter((row) => row.kind === 'group')).toHaveLength(0)
  })
})
