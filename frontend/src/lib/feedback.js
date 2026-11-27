// Small touches that make speaking feel responsive: a soft tone and a short
// buzz when listening starts and stops. Phones without vibration (iPhone)
// just get the tone.

let audio

function tone(from, to, ms) {
  try {
    audio = audio || new AudioContext()
    // A context made outside a tap (such as after waiting for the mic) starts
    // suspended on iPhone, and one is suspended again when the phone goes to
    // the background or takes a call. Without this the cues stay silent from
    // then on; resuming here, on the next tap, brings them back.
    if (audio.state !== 'running') audio.resume?.().catch(() => {})
    const osc = audio.createOscillator()
    const gain = audio.createGain()
    const t = audio.currentTime
    osc.type = 'sine'
    osc.frequency.setValueAtTime(from, t)
    osc.frequency.exponentialRampToValueAtTime(to, t + ms / 1000)
    gain.gain.setValueAtTime(0.0001, t)
    gain.gain.exponentialRampToValueAtTime(0.06, t + 0.015)
    gain.gain.exponentialRampToValueAtTime(0.0001, t + ms / 1000)
    osc.connect(gain).connect(audio.destination)
    osc.start(t)
    osc.stop(t + ms / 1000 + 0.02)
  } catch {
    // no audio: the visual change is enough
  }
}

export function startCue() {
  navigator.vibrate?.(12)
  tone(520, 880, 120)
}

export function stopCue() {
  navigator.vibrate?.([8, 40, 8])
  tone(780, 460, 140)
}

export function doneCue() {
  navigator.vibrate?.(20)
  tone(660, 990, 160)
}
