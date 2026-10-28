import { useCallback, useState } from 'react'
import JobView from './components/JobView.jsx'
import SettingsPanel from './components/SettingsPanel.jsx'
import { startBuild } from './lib/api.js'
import { PROVIDERS, loadSettings } from './lib/settings.js'
  import Modal from './components/SettingsModal.jsx'

export default function App() {
  const [settings, setSettings] = useState(loadSettings)
  const [showSettings, setShowSettings] = useState(() => !loadSettings().apiKey)
  const [prompt, setPrompt] = useState('')
  const [jobId, setJobId] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const providerLabel = PROVIDERS.find((p) => p.id === settings.provider)?.label
  const canBuild = prompt.trim() && !running

  async function handleBuild() {
    if (!canBuild) return
    if (!settings.apiKey) {
      setShowSettings(true)
      return
    }
    setError('')
    setRunning(true)
    try {
      const { job_id } = await startBuild({ prompt: prompt.trim(), ...settings })
      setJobId(job_id)
    } catch (err) {
      setError(err.message)
      setRunning(false)
    }
  }

  const handleDone = useCallback(() => setRunning(false), [])

  return (
    <div className="min-h-screen bg-ink text-fg">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-6 py-5">
          <span className="font-display text-xl font-bold tracking-[0.1em]">VYSKAR</span>
          <button
            type="button"
            onClick={() => setShowSettings((v) => !v)}
            className="min-h-11 rounded-full border border-wall px-4 text-sm text-muted"
          >
            {settings.apiKey ? `${providerLabel} key saved` : 'Add your AI key'}
          </button>
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">
        {showSettings && (<SettingsPanel settings={settings} onChange={setSettings} onClose={() => setShowSettings(false)} />)}

        <div>
          <h1 className="font-display text-[clamp(26px,4vw,38px)] font-bold leading-tight">
            What should your senior engineer build?
          </h1>
          <p className="mt-3 text-muted">
            Describe the app in plain English. Vyskar writes the requirements, builds it, tests it and puts it online.
          </p>
        </div>

        <label htmlFor="prompt" className="sr-only">Describe your app</label>
        <textarea
          id="prompt"
          className="h-36 w-full rounded-2xl border border-wall bg-card p-4 text-fg placeholder:text-dim focus:outline-none focus:ring-2 focus:ring-saffron"
          placeholder="e.g. A to-do list where I can add, complete, delete and filter tasks"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleBuild()
          }}
        />

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={handleBuild}
            disabled={!canBuild}
            className="min-h-11 rounded-full bg-saffron px-7 font-semibold text-on-saffron disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? 'Building...' : 'Build my app'}
          </button>
          <span className="text-sm text-dim">Takes a few minutes. Ctrl or Cmd + Enter also works.</span>
        </div>

        {error && <p className="rounded-lg border border-line bg-card p-4 text-saffron">{error}</p>}

        {jobId && <JobView key={jobId} jobId={jobId} onDone={handleDone} />}
      </main>
      <Modal open={showSettings} onClose={() => setShowSettings(false)} labelledBy="settings-title">
          <SettingsPanel settings={settings} onChange={setSettings} onClose={() => setShowSettings(false)} />
      </Modal>
    </div>
  )
}
