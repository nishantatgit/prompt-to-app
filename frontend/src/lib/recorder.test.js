import { describe, expect, it } from 'vitest'
import { encodeWav } from './recorder'

async function read(blob) {
  return new DataView(await blob.arrayBuffer())
}

function text(view, offset, length) {
  return String.fromCharCode(...Array.from({ length }, (_, i) => view.getUint8(offset + i)))
}

describe('encodeWav', () => {
  it('writes a 16 kHz mono 16-bit PCM header', async () => {
    const blob = encodeWav(new Float32Array(10))
    expect(blob.type).toBe('audio/wav')
    expect(blob.size).toBe(44 + 20)
    const view = await read(blob)
    expect(text(view, 0, 4)).toBe('RIFF')
    expect(view.getUint32(4, true)).toBe(36 + 20)
    expect(text(view, 8, 4)).toBe('WAVE')
    expect(text(view, 12, 4)).toBe('fmt ')
    expect(view.getUint32(16, true)).toBe(16)
    expect(view.getUint16(20, true)).toBe(1) // PCM
    expect(view.getUint16(22, true)).toBe(1) // mono
    expect(view.getUint32(24, true)).toBe(16000)
    expect(view.getUint32(28, true)).toBe(32000)
    expect(view.getUint16(32, true)).toBe(2)
    expect(view.getUint16(34, true)).toBe(16)
    expect(text(view, 36, 4)).toBe('data')
    expect(view.getUint32(40, true)).toBe(20)
  })

  it('uses the given sample rate', async () => {
    const view = await read(encodeWav(new Float32Array(4), 48000))
    expect(view.getUint32(24, true)).toBe(48000)
    expect(view.getUint32(28, true)).toBe(96000)
  })

  it('turns samples into 16-bit values and clips anything past full scale', async () => {
    const view = await read(encodeWav(new Float32Array([0, 1, -1, 0.5, -0.5, 2, -3])))
    const samples = Array.from({ length: 7 }, (_, i) => view.getInt16(44 + i * 2, true))
    expect(samples).toEqual([0, 32767, -32768, 16383, -16384, 32767, -32768])
  })

  it('writes a header only for no samples', async () => {
    const blob = encodeWav(new Float32Array(0))
    expect(blob.size).toBe(44)
    expect((await read(blob)).getUint32(40, true)).toBe(0)
  })
})
