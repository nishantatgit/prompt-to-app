const STORAGE_KEY = 'vyskar.settings'

export const PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic', keyHint: 'sk-ant-...' },
  { id: 'openai', label: 'OpenAI', keyHint: 'sk-...' },
]

const EMPTY = { provider: 'anthropic', apiKey: '' }

// The key lives only in this browser. It is sent with each build and never stored on the server.
//
// Whatever is stored is checked: a value that is not what saveSettings wrote
// (edited by hand, or left by an older version) falls back field by field,
// so the settings panel never gets a key that is not text, which would break
// it on save, or a provider the app does not offer.
export function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return EMPTY
    return {
      provider: PROVIDERS.some((p) => p.id === saved.provider) ? saved.provider : EMPTY.provider,
      apiKey: typeof saved.apiKey === 'string' ? saved.apiKey : EMPTY.apiKey,
    }
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
