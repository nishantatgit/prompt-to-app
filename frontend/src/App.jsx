import { useCallback, useEffect, useRef, useState } from 'react'
import JobView from './components/JobView.jsx'
import SettingsPanel from './components/SettingsPanel.jsx'
import { getTrial, getVoice, startBuild } from './lib/api.js'
import { askToNotify, notifyBuildDone } from './lib/notify.js'
import { PROVIDERS, loadSettings } from './lib/settings.js'
import InstallButton from './components/InstallButton.jsx'
import Modal from './components/SettingsModal.jsx'
import VoiceComposer from './components/VoiceComposer.jsx'
import { useInputMode, useIsPhone } from './lib/inputMode.js'

export default function App() {
  const [settings, setSettings] = useState(loadSettings)
  // Opened once the free trial is known: only when there is no key and no
  // free build to use instead.
  const [showSettings, setShowSettings] = useState(false)
  const [trial, setTrial] = useState({ enabled: false, builds_left: 0 })
  const [prompt, setPrompt] = useState('')
  const [jobId, setJobId] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const isPhone = useIsPhone()
  const [inputMode, setInputMode] = useInputMode()
  const [dictateHint, setDictateHint] = useState(false)
  const [serverVoice, setServerVoice] = useState(false)
  const promptBox = useRef(null)
  const voice = isPhone && inputMode === 'voice'

  const providerLabel = PROVIDERS.find((p) => p.id === settings.provider)?.label
  const canBuild = prompt.trim() && !running
  const freeBuild = !settings.apiKey && trial.builds_left > 0

  useEffect(() => {
    let stopped = false
    getTrial()
      .catch(() => ({ enabled: false, builds_left: 0 }))
      .then((next) => {
        if (stopped) return
        setTrial(next)
        if (!loadSettings().apiKey && !(next.builds_left > 0)) setShowSettings(true)
      })
    return () => {
      stopped = true
    }
  }, [])

  useEffect(() => {
    getVoice()
      .then((v) => setServerVoice(Boolean(v.enabled)))
      .catch(() => {})
  }, [])

  async function handleBuild() {
    if (!canBuild) return
    if (!settings.apiKey && !freeBuild) {
      setShowSettings(true)
      return
    }
    setError('')
    setRunning(true)
    askToNotify()
    try {
      const { job_id } = await startBuild({ prompt: prompt.trim(), ...settings })
      setJobId(job_id)
      if (freeBuild) getTrial().then(setTrial).catch(() => {})
    } catch (err) {
      setError(err.message)
      setRunning(false)
    }
  }

  function switchToTyping({ dictate = false }) {
    setInputMode('type')
    setDictateHint(dictate)
    // Focus after the text box appears; on a phone this opens the keyboard.
    requestAnimationFrame(() => promptBox.current?.focus())
  }

  const buildNote = freeBuild
    ? `Free build, no AI key needed: ${trial.builds_left} left.`
    : isPhone
      ? 'Takes a few minutes.'
      : 'Takes a few minutes. Ctrl or Cmd + Enter also works.'

  const handleDone = useCallback((job) => {
    setRunning(false)
    notifyBuildDone(job)
  }, [])

  return (
    <div className="min-h-screen bg-ink text-fg">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-2 px-4 py-5 sm:gap-4 sm:px-6">
          <span className="font-display text-lg font-bold tracking-[0.1em] sm:text-xl">VYSKAR</span>
          <div className="flex items-center gap-1">
            <InstallButton />
            <button
              type="button"
              onClick={() => setShowSettings((v) => !v)}
              className="min-h-11 whitespace-nowrap rounded-full border border-wall px-4 text-sm text-muted"
            >
              <span className="sm:hidden">{settings.apiKey ? 'Key saved' : 'Add key'}</span>
              <span className="hidden sm:inline">
                {settings.apiKey ? `${providerLabel} key saved` : 'Add your AI key'}
              </span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">

        {voice ? (
          <VoiceComposer
            prompt={prompt}
            onPromptChange={setPrompt}
            onBuild={handleBuild}
            canBuild={canBuild}
            running={running}
            note={buildNote}
            onType={switchToTyping}
            compact={Boolean(jobId)}
            serverVoice={serverVoice}
          />
        ) : (
          <>
            <div>
              <h1 className="font-display text-[clamp(26px,4vw,38px)] font-bold leading-tight">
                What should your senior engineer build?
              </h1>
              <p className="mt-3 text-muted">
                Describe the app in plain English. Vyskar writes the requirements, builds it, tests it and puts it online.
              </p>
            </div>

            <label htmlFor="prompt" className="sr-only">Describe your app</label>
            {dictateHint && (
              <p className="rounded-lg border border-line bg-card p-4 text-sm text-muted">
                Voice isn't available here yet. Tap the mic on your keyboard to dictate
                instead.
              </p>
            )}
            <textarea
              ref={promptBox}
              id="prompt"
              className="h-36 w-full rounded-2xl border border-wall bg-card p-4 text-fg placeholder:text-dim focus:outline-none focus:ring-2 focus:ring-accent"
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
                className="min-h-11 rounded-full bg-accent px-7 font-semibold text-on-accent disabled:cursor-not-allowed disabled:opacity-50"
              >
                {running ? 'Building...' : 'Build my app'}
              </button>
              <span className="text-sm text-dim">{buildNote}</span>
              {isPhone && (
                <button
                  type="button"
                  onClick={() => {
                    setDictateHint(false)
                    setInputMode('voice')
                  }}
                  className="min-h-11 text-sm text-muted underline underline-offset-4"
                >
                  Speak instead
                </button>
              )}
            </div>
          </>
        )}

        {error && <p className="rounded-lg border border-line bg-card p-4 text-accent">{error}</p>}

        {jobId && <JobView key={jobId} jobId={jobId} onDone={handleDone} />}
      </main>
      <Modal open={showSettings} onClose={() => setShowSettings(false)} labelledBy="settings-title">
          <SettingsPanel settings={settings} onChange={setSettings} onClose={() => setShowSettings(false)} />
      </Modal>
    </div>
  )
}
