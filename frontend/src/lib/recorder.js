// Records the microphone as raw audio, reports how loud it is while
// recording, and returns 16 kHz mono 16-bit WAV: the format Sarvam
// transcribes best. Raw capture through an AudioWorklet works the same in
// Chrome and in iPhone home screen apps, so no MediaRecorder formats to juggle.

const TARGET_RATE = 16000

// Runs on the audio thread: hands each block of samples to the page.
const WORKLET = `
class Capture extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0]
    if (channel) this.port.postMessage(channel.slice(0))
    return true
  }
}
registerProcessor('vyskar-capture', Capture)
`

export function recordingSupported() {
  return Boolean(navigator.mediaDevices?.getUserMedia && window.AudioContext && window.AudioWorkletNode)
}

function downsample(samples, fromRate) {
  if (fromRate === TARGET_RATE) return samples
  const ratio = fromRate / TARGET_RATE
  const out = new Float32Array(Math.floor(samples.length / ratio))
  for (let i = 0; i < out.length; i++) {
    // Average the samples that fold into this one, a simple low-pass filter.
    const start = Math.floor(i * ratio)
    const end = Math.min(samples.length, Math.floor((i + 1) * ratio))
    let sum = 0
    for (let j = start; j < end; j++) sum += samples[j]
    out[i] = sum / Math.max(1, end - start)
  }
  return out
}

export function encodeWav(samples, rate = TARGET_RATE) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const text = (offset, s) => [...s].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)))
  text(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  text(8, 'WAVE')
  text(12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, rate, true)
  view.setUint32(28, rate * 2, true) // bytes per second
  view.setUint16(32, 2, true) // bytes per sample
  view.setUint16(34, 16, true) // bits per sample
  text(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

// Must be called from a tap: browsers only start audio on a user gesture.
// onLevel gets 0 to 1 about 40 times a second.
export async function startRecording({ onLevel }) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  })
  const context = new AudioContext()
  await context.resume()
  const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }))
  try {
    await context.audioWorklet.addModule(url)
  } finally {
    URL.revokeObjectURL(url)
  }
  const source = context.createMediaStreamSource(stream)
  const capture = new AudioWorkletNode(context, 'vyskar-capture')
  const chunks = []
  let level = 0
  capture.port.onmessage = ({ data }) => {
    chunks.push(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i]
    // Rises fast and falls slowly, so the orb breathes with the voice.
    const now = Math.min(1, Math.sqrt(sum / data.length) * 6)
    level = now > level ? now : level * 0.9 + now * 0.1
    onLevel?.(level)
  }
  source.connect(capture)
  // A silent output keeps the worklet running in Safari.
  const mute = context.createGain()
  mute.gain.value = 0
  capture.connect(mute).connect(context.destination)

  function release() {
    stream.getTracks().forEach((track) => track.stop())
    source.disconnect()
    capture.disconnect()
    context.close()
  }

  return {
    seconds: () => chunks.reduce((n, c) => n + c.length, 0) / context.sampleRate,
    stop() {
      const rate = context.sampleRate
      release()
      const total = chunks.reduce((n, c) => n + c.length, 0)
      const samples = new Float32Array(total)
      let offset = 0
      for (const c of chunks) {
        samples.set(c, offset)
        offset += c.length
      }
      return encodeWav(downsample(samples, rate))
    },
    cancel: release,
  }
}
