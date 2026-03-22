import { useMemo, useState } from 'preact/hooks'
import type { HistogramBucket, HistogramPoint } from '../types'
import { classNames, formatCount, formatTimestamp } from '../utils'

interface HistogramProps {
  points: HistogramPoint[]
  bucket: HistogramBucket
  selectedRange: { capturedAfter?: string; capturedBefore?: string }
  onSelectRange: (startIndex: number, endIndex: number) => void
  onClearRange: () => void
}

function isIndexSelected(
  index: number,
  point: HistogramPoint,
  selectedRange: { capturedAfter?: string; capturedBefore?: string },
) {
  if (!selectedRange.capturedAfter || !selectedRange.capturedBefore) {
    return false
  }

  const pointMs = new Date(point.timestamp).getTime()
  const startMs = new Date(selectedRange.capturedAfter).getTime() + 1
  const endMs = new Date(selectedRange.capturedBefore).getTime()
  return Number.isFinite(index) && pointMs >= startMs && pointMs < endMs
}

export function Histogram({
  points,
  bucket,
  selectedRange,
  onSelectRange,
  onClearRange,
}: HistogramProps) {
  const [dragStartIndex, setDragStartIndex] = useState<number | null>(null)
  const [dragCurrentIndex, setDragCurrentIndex] = useState<number | null>(null)

  const maxCount = Math.max(...points.map((point) => point.request_count), 1)
  const previewRange = useMemo(() => {
    if (dragStartIndex === null || dragCurrentIndex === null) {
      return null
    }

    return {
      start: Math.min(dragStartIndex, dragCurrentIndex),
      end: Math.max(dragStartIndex, dragCurrentIndex),
    }
  }, [dragCurrentIndex, dragStartIndex])

  return (
    <div class="histogram">
      <div class="histogram__meta">
        <div>
          <strong>Captured requests over time</strong>
          <span>{points.length} buckets · {bucket}</span>
        </div>
        <button
          type="button"
          class="button button--ghost"
          disabled={!selectedRange.capturedAfter && !selectedRange.capturedBefore}
          onClick={onClearRange}
        >
          Clear brush
        </button>
      </div>

      {points.length === 0 ? (
        <div class="panel-empty">No histogram data yet.</div>
      ) : (
        <>
          <svg
            class="histogram__svg"
            viewBox={`0 0 ${Math.max(points.length * 24, 240)} 180`}
            preserveAspectRatio="none"
            role="img"
            aria-label="Request histogram"
          >
            {points.map((point, index) => {
              const x = index * 24
              const barHeight = Math.max(8, (point.request_count / maxCount) * 132)
              const y = 156 - barHeight
              const inPreview =
                previewRange !== null &&
                index >= previewRange.start &&
                index <= previewRange.end
              const selected = inPreview || isIndexSelected(index, point, selectedRange)

              return (
                <g key={point.timestamp}>
                  <rect
                    x={x}
                    y={y}
                    width="18"
                    height={barHeight}
                    rx="8"
                    class={classNames(
                      'histogram__bar',
                      selected && 'is-selected',
                    )}
                    onPointerDown={() => {
                      setDragStartIndex(index)
                      setDragCurrentIndex(index)
                    }}
                    onPointerEnter={() => {
                      if (dragStartIndex !== null) {
                        setDragCurrentIndex(index)
                      }
                    }}
                    onPointerUp={() => {
                      if (dragStartIndex === null) {
                        onSelectRange(index, index)
                      } else {
                        onSelectRange(
                          Math.min(dragStartIndex, index),
                          Math.max(dragStartIndex, index),
                        )
                      }
                      setDragStartIndex(null)
                      setDragCurrentIndex(null)
                    }}
                  />
                  <title>{`${formatTimestamp(point.timestamp)} • ${formatCount(point.request_count)} requests`}</title>
                </g>
              )
            })}
          </svg>
          <div class="histogram__axis">
            <span>{formatTimestamp(points[0]?.timestamp)}</span>
            <span>{formatTimestamp(points[points.length - 1]?.timestamp)}</span>
          </div>
        </>
      )}
    </div>
  )
}
