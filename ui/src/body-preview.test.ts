import { describe, expect, it } from 'vitest'
import { decodeBodyPreview } from './body-preview'

describe('decodeBodyPreview', () => {
  it('renders decodable text inline', () => {
    const result = decodeBodyPreview(
      new TextEncoder().encode('{"ok":true}\n'),
      'application/json',
    )

    expect(result).toEqual({ kind: 'text', text: '{"ok":true}\n' })
  })

  it('marks undecodable binary bodies for download', () => {
    const result = decodeBodyPreview(new Uint8Array([0xff, 0xd8, 0xff, 0x00]), 'image/jpeg')

    expect(result).toEqual({ kind: 'binary' })
  })
})
