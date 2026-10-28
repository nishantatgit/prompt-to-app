const STORAGE_KEY = 'vyskar.settings'

export const PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic', keyHint: 'sk-ant-...' },
  { id: 'openai', label: 'OpenAI', keyHint: 'sk-...' },
]

const EMPTY = { provider: 'anthropic', apiKey: '' }

// The key lives only in this browser. It is sent with each build and never stored on the server.
export function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    return saved ? { ...EMPTY, ...saved } : EMPTY
  } catch {
    return EMPTY
  }
}

export function saveSettings(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // Storage can be blocked (private mode). Settings then last for this visit only.
  }
}

export function clearSettings() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
