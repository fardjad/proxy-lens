export type HeaderPair = [string, string]

export type HistogramBucket = 'second' | 'minute' | 'hour'

export type DiagramMode = 'grouped' | 'flat'

export type TriState = boolean | undefined

export interface HistogramPoint {
  timestamp: string
  request_count: number
}

export interface HistogramResponse {
  bucket: HistogramBucket
  captured_after: string | null
  captured_before: string | null
  points: HistogramPoint[]
}

export interface RequestSummary {
  request_id: string
  trace_id: string
  node_name: string
  hop_chain: string
  hop_nodes: string[]
  captured_at: string
  updated_at: string
  completed_at: string | null
  request_method: string | null
  request_url: string | null
  request_http_version: string | null
  request_headers: HeaderPair[]
  response_status_code: number | null
  response_http_version: string | null
  response_headers: HeaderPair[]
  request_complete: boolean
  response_complete: boolean
  websocket_open: boolean
  error: string | null
  complete: boolean
}

export interface BlobRef {
  blob_id: string
  size_bytes: number
  content_type: string | null
}

export interface WebSocketMessage {
  event_index: number
  captured_at: string
  direction: string
  payload_type: string
  payload_text: string | null
  blob_id: string | null
  size_bytes: number | null
}

export interface RequestDetail extends RequestSummary {
  request_trailers: HeaderPair[]
  request_body_size: number
  request_body_blob_id: string | null
  request_body_complete: boolean
  response_trailers: HeaderPair[]
  response_body_size: number
  response_body_blob_id: string | null
  response_body_complete: boolean
  response_started: boolean
  request_started: boolean
  websocket_url: string | null
  websocket_http_version: string | null
  websocket_headers: HeaderPair[]
  websocket_close_code: number | null
  websocket_messages: WebSocketMessage[]
  request_body_chunks: BlobRef[]
  response_body_chunks: BlobRef[]
}

export interface RequestListResponse {
  requests: RequestSummary[]
}

export interface RequestFilters {
  capturedAfter?: string
  capturedBefore?: string
  traceIds: string[]
  requestIds: string[]
  nodeNames: string[]
  methods: string[]
  urlContains: string
  statusCodes: number[]
  complete: TriState
  requestComplete: TriState
  responseComplete: TriState
  limit: number
  offset: number
}

export interface BinaryBody {
  bytes: Uint8Array
  contentType: string | null
}

export type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; error: string }

export type BodyPreview = { kind: 'text'; text: string } | { kind: 'binary' }

export type BodyState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'missing' }
  | { status: 'ready'; data: BinaryBody; preview: BodyPreview }
  | { status: 'error'; error: string }
