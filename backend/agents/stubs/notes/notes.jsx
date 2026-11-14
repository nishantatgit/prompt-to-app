import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'

function AuthForm() {
  const [mode, setMode] = useState('signup')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    const { error } =
      mode === 'signup'
        ? await supabase.auth.signUp({ email, password })
        : await supabase.auth.signInWithPassword({ email, password })
    setBusy(false)
    if (error) setError(error.message)
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded border p-5">
      <h2 className="text-xl font-semibold">{mode === 'signup' ? 'Create an account' : 'Welcome back'}</h2>
      <label htmlFor="email" className="text-sm font-medium">Email</label>
      <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="rounded border px-3 py-2" />
      <label htmlFor="password" className="text-sm font-medium">Password</label>
      <input id="password" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} className="rounded border px-3 py-2" />
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <button type="submit" disabled={busy} className="rounded bg-slate-900 px-4 py-2 font-semibold text-white">
        {mode === 'signup' ? 'Sign up' : 'Log in'}
      </button>
      <button type="button" onClick={() => setMode(mode === 'signup' ? 'login' : 'signup')} className="text-sm underline">
        {mode === 'signup' ? 'I already have an account' : 'I need an account'}
      </button>
    </form>
  )
}

function Notes({ session }) {
  const [notes, setNotes] = useState([])
  const [body, setBody] = useState('')
  const [error, setError] = useState('')

  async function load() {
    const { data, error } = await supabase
      .from('notes')
      .select('id, body, created_at')
      .order('created_at', { ascending: false })
    if (error) setError('Could not load your notes. Refresh to try again.')
    else setNotes(data)
  }

  useEffect(() => {
    load()
  }, [session.user.id])

  async function add(event) {
    event.preventDefault()
    if (!body.trim()) return
    const { error } = await supabase.from('notes').insert({ body: body.trim() })
    if (error) {
      setError('Your note was not saved. Try again.')
      return
    }
    setBody('')
    await load()
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 truncate text-sm">{session.user.email}</p>
        <button type="button" onClick={() => supabase.auth.signOut()} className="rounded border px-3 py-1 text-sm">
          Log out
        </button>
      </div>
      <form onSubmit={add} className="flex flex-col gap-2">
        <label htmlFor="note" className="text-sm font-medium">New note</label>
        <textarea id="note" value={body} maxLength={2000} onChange={(e) => setBody(e.target.value)} className="min-h-20 rounded border px-3 py-2" />
        <button type="submit" className="self-start rounded bg-slate-900 px-4 py-2 font-semibold text-white">Add note</button>
      </form>
      {error && <p role="alert">{error}</p>}
      <ul aria-label="Your notes" className="flex flex-col gap-2">
        {notes.map((note) => (
          <li key={note.id} className="break-words rounded border p-3">{note.body}</li>
        ))}
        {notes.length === 0 && <li className="text-sm">No notes yet.</li>}
      </ul>
    </section>
  )
}

export default function App() {
  const [session, setSession] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setReady(true)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next))
    return () => data.subscription.unsubscribe()
  }, [])

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col gap-6 px-4 py-10">
      <h1 className="text-3xl font-bold">Notes</h1>
      {!ready ? <p>Loading...</p> : session ? <Notes session={session} /> : <AuthForm />}
    </main>
  )
}
