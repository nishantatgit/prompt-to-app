import { useState } from 'react'
import { PROVIDERS, clearSettings, saveSettings } from '../lib/settings.js'

export default function SettingsPanel({ settings, onChange, onClose }) {
  const [provider, setProvider] = useState(settings.provider)
  const [apiKey, setApiKey] = useState(settings.apiKey)
  const [showKey, setShowKey] = useState(false)
  const hint = PROVIDERS.find((p) => p.id === provider)?.keyHint

  function handleSave(e) {
    e.preventDefault()
    const next = { provider, apiKey: apiKey.trim() }
    saveSettings(next)
    onChange(next)
    onClose()
  }

  function handleForget() {
    clearSettings()
    setApiKey('')
    onChange({ provider, apiKey: '' })
  }

  return (
    <form onSubmit={handleSave} className="rounded-2xl border border-line bg-card p-6">
      <h2  id="settings-title" className="font-display text-lg font-bold">Your AI key</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        Vyskar runs on your own Anthropic or OpenAI key. It stays in this browser and is sent only to run
        your build. It is never stored on our server.
      </p>

      <label htmlFor="provider" className="mt-5 block text-sm font-medium">Provider</label>
      <select
        id="provider"
        value={provider}
        onChange={(e) => setProvider(e.target.value)}
        className="mt-2 min-h-11 w-full rounded-lg border border-wall bg-ink px-3 text-fg"
      >
        {PROVIDERS.map((p) => (
          <option key={p.id} value={p.id}>{p.label}</option>
        ))}
      </select>

      <label htmlFor="api-key" className="mt-4 block text-sm font-medium">API key</label>
      <div className="mt-2 flex gap-2">
        <input
          id="api-key"
          type={showKey ? 'text' : 'password'}
          autoComplete="off"
          spellCheck="false"
          placeholder={hint}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          className="min-h-11 min-w-0 flex-1 rounded-lg border border-wall bg-ink px-3 font-mono text-sm text-fg"
        />
        <button
          type="button"
          onClick={() => setShowKey((v) => !v)}
          className="min-h-11 rounded-lg border border-wall px-4 text-sm text-muted"
        >
          {showKey ? 'Hide' : 'Show'}
        </button>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button type="submit" className="min-h-11 rounded-full bg-saffron px-6 font-semibold text-on-saffron">
          Save
        </button>
        <button type="button" onClick={onClose} className="min-h-11 rounded-full border border-wall px-6 text-fg">
          Cancel
        </button>
        {settings.apiKey && (
          <button type="button" onClick={handleForget} className="ml-auto text-sm text-dim underline">
            Forget my key
          </button>
        )}
      </div>
    </form>
  )
}
