import { useCallback, useEffect, useRef, useState } from 'react'
import JobView from './components/JobView.jsx'
import SettingsPanel from './components/SettingsPanel.jsx'
import { getCredits, getTrial, getVoice, startBuild } from './lib/api.js'
import { askToNotify, notifyBuildDone } from './lib/notify.js'
import { watchBuild } from './lib/push.js'
import { PROVIDERS, loadSettings } from './lib/settings.js'
import InstallButton from './components/InstallButton.jsx'
import Modal from './components/SettingsModal.jsx'
import VoiceComposer from './components/VoiceComposer.jsx'
import MyApps from './components/MyApps.jsx'
import BuyBuilds from './components/BuyBuilds.jsx'
import BuildsPanel from './components/BuildsPanel.jsx'
import { loadApps, rememberApp } from './lib/myApps.js'
import { useInputMode, useIsPhone } from './lib/inputMode.js'

const CHANGE_EXAMPLES = [
  'add a dark mode',
  'make the buttons bigger',
  'let me delete items',
  'add a search box at the top',
  'show the total at the bottom',
]

export default function App() {
  const [settings, setSettings] = useState(loadSettings)
  // Opened once the free trial is known: only when there is no key and no
  // free build to use instead.
  const [showSettings, setShowSettings] = useState(false)
  const [trial, setTrial] = useState({ enabled: false, builds_left: 0 })
  const [credits, setCredits] = useState({ enabled: false, builds_left: 0, packs: [] })
  const [prompt, setPrompt] = useState('')
  const [jobId, setJobId] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const isPhone = useIsPhone()
  const [inputMode, setInputMode] = useInputMode()
  const [dictateHint, setDictateHint] = useState(false)
  const [serverVoice, setServerVoice] = useState(false)
  const promptBox = useRef(null)
  const [apps, setApps] = useState(loadApps)
  // The app being changed, or null when building a new one.
  const [changing, setChanging] = useState(null)
  // Per job: the edit key and prompt, to remember the app once it is live.
  const jobInfo = useRef({})
  const voice = isPhone && inputMode === 'voice'

  const providerLabel = PROVIDERS.find((p) => p.id === settings.provider)?.label
  const canBuild = prompt.trim() && !running
  // With own keys switched off, a key saved earlier is not used.
  const ownKeys = trial.own_keys !== false
  const apiKey = ownKeys ? settings.apiKey : ''
  // Without a key: bought builds first, then free ones.
  const paidBuild = !apiKey && credits.builds_left > 0
  const freeBuild = !apiKey && !paidBuild && trial.builds_left > 0
  const refreshTrial = () => getTrial().then(setTrial).catch(() => {})

  useEffect(() => {
    let stopped = false
    Promise.all([
      getTrial().catch(() => ({ enabled: false, builds_left: 0 })),
      getCredits().catch(() => ({ enabled: false, builds_left: 0, packs: [] })),
    ]).then(([nextTrial, nextCredits]) => {
      if (stopped) return
      setTrial(nextTrial)
      setCredits(nextCredits)
      const canBuild = nextTrial.builds_left > 0 || nextCredits.builds_left > 0
      const savedKey = nextTrial.own_keys !== false && loadSettings().apiKey
      if (!savedKey && !canBuild) setShowSettings(true)
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
    if (!apiKey && !freeBuild && !paidBuild) {
      setShowSettings(true)
      return
    }
    setError('')
    setRunning(true)
    const asked = askToNotify()
    try {
      const { job_id, edit_key } = await startBuild({
        prompt: prompt.trim(),
        ...settings,
        apiKey,
        app: changing?.name,
        editKey: changing?.editKey,
      })
      jobInfo.current[job_id] = { editKey: edit_key || changing?.editKey, prompt: prompt.trim() }
      setJobId(job_id)
      // Once notifications are allowed, the server can push when it's done.
      asked.then(() => watchBuild(job_id))
      if (freeBuild) refreshTrial()
      if (paidBuild) getCredits().then(setCredits).catch(() => {})
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

  const buildNote = paidBuild
    ? `Uses 1 of your ${credits.builds_left} builds.`
    : freeBuild
    ? `Free build, no AI key needed: ${trial.builds_left} left.`
    : isPhone
      ? 'Takes a few minutes.'
      : 'Takes a few minutes. Ctrl or Cmd + Enter also works.'

  const handleDone = useCallback((job) => {
    setRunning(false)
    notifyBuildDone(job)
    const info = job && jobInfo.current[job.job_id]
    if (job?.status === 'succeeded' && job.app_name && info) {
      setApps(
        rememberApp({
          name: job.app_name,
          url: job.deploy_url,
          editKey: job.editable ? info.editKey : null,
          prompt: info.prompt,
        }),
      )
      setChanging(null)
    }
  }, [])

  function startChange(name) {
    const app = loadApps().find((a) => a.name === name)
    if (!app?.editKey) return
    setChanging(app)
    setPrompt('')
    setJobId(null)
    setError('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
    if (!voice) requestAnimationFrame(() => promptBox.current?.focus())
  }

  const changeBanner = changing && (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl border border-line bg-card px-4 py-3 text-sm">
      <span className="text-muted">
        Changing{' '}
        <a href={changing.url} target="_blank" rel="noreferrer" className="font-mono text-accent">
          {changing.name}
        </a>
      </span>
      <button
        type="button"
        onClick={() => setChanging(null)}
        disabled={running}
        className="min-h-11 text-muted underline underline-offset-4 disabled:opacity-50"
      >
        Build a new app instead
      </button>
    </div>
  )

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
              <span className="sm:hidden">
                {apiKey
                  ? 'Key saved'
                  : paidBuild
                    ? `${credits.builds_left} builds`
                    : freeBuild
                      ? `${trial.builds_left} free`
                      : ownKeys && !credits.enabled
                        ? 'Add key'
                        : 'Get builds'}
              </span>
              <span className="hidden sm:inline">
                {apiKey
                  ? `${providerLabel} key saved`
                  : paidBuild
                    ? `${credits.builds_left} builds left`
                    : freeBuild
                      ? `${trial.builds_left} free builds`
                      : !ownKeys
                        ? 'Get more builds'
                        : credits.enabled
                          ? 'Buy builds or add a key'
                          : 'Add your AI key'}
              </span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-12">

        {changeBanner}
        {voice ? (
          <VoiceComposer
            title={changing ? 'What should change?' : undefined}
            buildLabel={changing ? 'Change my app' : undefined}
            examples={changing ? CHANGE_EXAMPLES : undefined}
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
                {changing ? 'What should change?' : 'What should your senior engineer build?'}
              </h1>
              <p className="mt-3 text-muted">
                {changing
                  ? 'Describe the change. Vyskar updates the app at the same address and keeps its data.'
                  : 'Describe the app in plain English. Vyskar writes the requirements, builds it, tests it and puts it online.'}
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
              placeholder={
                changing
                  ? 'e.g. Add a dark mode and make the buttons bigger'
                  : 'e.g. A to-do list where I can add, complete, delete and filter tasks'
              }
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
                {running ? 'Building...' : changing ? 'Change my app' : 'Build my app'}
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

        {jobId && (
          <JobView
            key={jobId}
            jobId={jobId}
            onDone={handleDone}
            onChange={startChange}
            feedbackBonus={!apiKey && trial.bonus_available ? (trial.bonus_builds ?? 2) : 0}
            onBonus={refreshTrial}
          />
        )}

        {!running && <MyApps apps={apps} onChange={(app) => startChange(app.name)} disabled={running} />}
      </main>
      <Modal
        open={showSettings}
        onClose={() => setShowSettings(false)}
        labelledBy={!apiKey && (trial.enabled || !ownKeys) ? 'builds-title' : 'settings-title'}
      >
          <div className="flex flex-col gap-4">
            {!apiKey && (trial.enabled || !ownKeys) && (
              <BuildsPanel
                trial={trial}
                credits={credits}
                bonusBuilds={trial.bonus_builds ?? 2}
                onBonus={refreshTrial}
              />
            )}
            {credits.enabled && !apiKey && (
              <BuyBuilds
                credits={credits}
                onBought={(left) => setCredits((c) => ({ ...c, builds_left: left }))}
              />
            )}
            {ownKeys && (
              <SettingsPanel settings={settings} onChange={setSettings} onClose={() => setShowSettings(false)} />
            )}
          </div>
      </Modal>
    </div>
  )
}
