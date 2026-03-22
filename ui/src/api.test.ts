import { describe, expect, it } from 'vitest'
import { serializeRequestQuery } from './api'
import type { RequestFilters } from './types'

const filters: RequestFilters = {
  capturedAfter: '2026-03-22T09:59:59.999Z',
  capturedBefore: '2026-03-22T10:06:00.000Z',
  traceIds: ['trace-a', 'trace-b'],
  requestIds: ['req-1'],
  nodeNames: ['proxy-a', 'proxy-b'],
  methods: ['GET', 'POST'],
  urlContains: 'widgets',
  statusCodes: [200, 404],
  complete: true,
  requestComplete: undefined,
  responseComplete: false,
  limit: 1000,
  offset: 0,
}

describe('serializeRequestQuery', () => {
  it('serializes repeated array parameters and tristate filters', () => {
    const params = serializeRequestQuery(filters)

    expect(params.getAll('trace_ids')).toEqual(['trace-a', 'trace-b'])
    expect(params.getAll('request_ids')).toEqual(['req-1'])
    expect(params.getAll('node_names')).toEqual(['proxy-a', 'proxy-b'])
    expect(params.getAll('methods')).toEqual(['GET', 'POST'])
    expect(params.getAll('status_codes')).toEqual(['200', '404'])
    expect(params.get('complete')).toBe('true')
    expect(params.get('response_complete')).toBe('false')
    expect(params.get('request_complete')).toBeNull()
    expect(params.get('url_contains')).toBe('widgets')
    expect(params.get('captured_after')).toBe('2026-03-22T09:59:59.999Z')
    expect(params.get('captured_before')).toBe('2026-03-22T10:06:00.000Z')
  })
})
