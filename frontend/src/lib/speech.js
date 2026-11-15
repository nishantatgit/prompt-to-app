// Speech to text with the browser's own recognizer (Web Speech API).
// Chrome on Android and Safari in a tab have it. iPhone home screen apps do
// not: WebKit leaves it out of installed web apps, so speechSupported() is
// false there and the caller falls back to typing.

const Recognition =
  typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)

export function speechSupported() {
  return Boolean(Recognition)
}

const ERRORS = {
  'not-allowed': 'Allow microphone access for Vyskar to speak your app.',
  'service-not-allowed': 'Voice is turned off on this device. Type your app instead.',
  'no-speech': "Didn't catch that. Tap the mic and try again.",
  'audio-capture': 'No microphone found. Type your app instead.',
  network: 'Voice needs an internet connection. Try again or type instead.',
}

// Starts listening at once. onText gets the whole transcript so far each time
// it changes; onEnd is called once, when listening stops for any reason.
export function listen({ onText, onEnd, onError, lang = navigator.language || 'en-US' }) {
  const recognition = new Recognition()
  recognition.lang = lang
  recognition.continuous = true
  recognition.interimResults = true
  recognition.onresult = (event) => {
    // Rebuilt from every result each time: Android repeats earlier results.
    const text = Array.from(event.results, (result) => result[0].transcript).join(' ')
    onText(text.replace(/\s+/g, ' ').trim())
  }
  recognition.onerror = (event) => {
    if (event.error === 'aborted') return
    onError?.(ERRORS[event.error] || "Voice didn't work this time. Try again or type instead.")
  }
  recognition.onend = () => onEnd?.()
  recognition.start()
  return { stop: () => recognition.stop() }
}
