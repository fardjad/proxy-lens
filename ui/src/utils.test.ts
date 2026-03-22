import { describe, expect, it } from 'vitest'
import { intersectSelection, invertSelection, makeBrushRange } from './utils'

describe('selection helpers', () => {
  it('keeps only visible selections after refetch', () => {
    expect(intersectSelection(['a', 'b', 'c'], ['b', 'd'])).toEqual(['b'])
  })

  it('inverts only within the filtered request set', () => {
    expect(invertSelection(['a', 'c'], ['a', 'b', 'c', 'd'])).toEqual(['b', 'd'])
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
