import type {
  BinaryBody,
  HistogramResponse,
  RequestDetail,
  RequestFilters,
  RequestListResponse,
} from './types'

const DEFAULT_SERVER_TARGET = 'http://127.0.0.1:8000'
const SERVER_TARGET =
  import.meta.env.VITE_PROXYLENS_BASE_URL?.trim() || DEFAULT_SERVER_TARGET
const API_BASE_URL = import.meta.env.DEV ? '/__proxylens' : SERVER_TARGET

export function serializeRequestQuery(filters: RequestFilters) {
  const params = new URLSearchParams()

  if (filters.capturedAfter) {
    params.set('captured_after', filters.capturedAfter)
  }

  if (filters.capturedBefore) {
    params.set('captured_before', filters.capturedBefore)
  }

  for (const value of filters.traceIds) {
    params.append('trace_ids', value)
  }

  for (const value of filters.requestIds) {
    params.append('request_ids', value)
  }

  for (const value of filters.nodeNames) {
    params.append('node_names', value)
  }

  for (const value of filters.methods) {
    params.append('methods', value)
  }

  if (filters.urlContains.trim()) {
    params.set('url_contains', filters.urlContains.trim())
  }

  for (const value of filters.statusCodes) {
    params.append('status_codes', String(value))
  }

  if (filters.complete !== undefined) {
    params.set('complete', String(filters.complete))
  }

  if (filters.requestComplete !== undefined) {
    params.set('request_complete', String(filters.requestComplete))
  }

  if (filters.responseComplete !== undefined) {
    params.set('response_complete', String(filters.responseComplete))
  }

  params.set('limit', String(filters.limit))
  params.set('offset', String(filters.offset))

  return params
}

async function requestJson<T>(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${path}`, init)

  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`)
  }

  return (await response.json()) as T
}

export async function getHistogram() {
  return requestJson<HistogramResponse>('/requests/histogram')
}

export async function getRequests(filters: RequestFilters) {
  const params = serializeRequestQuery(filters)
  return requestJson<RequestListResponse>(`/requests?${params.toString()}`)
}

export async function deleteRequests(requestIds: string[]) {
  const params = new URLSearchParams()
  for (const requestId of requestIds) {
    params.append('request_ids', requestId)
  }
  params.set('limit', String(Math.max(requestIds.length, 1)))
  params.set('offset', '0')

  const response = await fetch(`${API_BASE_URL}/requests?${params.toString()}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error(`Delete failed with ${response.status}`)
  }
}

export async function getRequestDetail(requestId: string) {
  return requestJson<RequestDetail>(`/requests/${requestId}`)
}

async function getBody(path: string): Promise<BinaryBody | null> {
  const response = await fetch(`${API_BASE_URL}${path}`)

  if (response.status === 404) {
    return null
  }

  if (!response.ok) {
    throw new Error(`Body request failed with ${response.status}`)
  }

  return {
    bytes: new Uint8Array(await response.arrayBuffer()),
    contentType: response.headers.get('content-type'),
  }
}

export async function getRequestBody(requestId: string) {
  return getBody(`/requests/${requestId}/body`)
}

export async function getResponseBody(requestId: string) {
  return getBody(`/requests/${requestId}/response/body`)
}

export function getServerTarget() {
  return SERVER_TARGET
}
