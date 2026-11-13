import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'

export default function App() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  async function load() {
    const { data, error } = await supabase
      .from('guestbook_entries')
      .select('id, created_at, name, message')
      .order('created_at', { ascending: false })
    if (error) setLoadError('Could not load the guestbook. Refresh the page to try again.')
    else setEntries(data)
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  async function sign(event) {
    event.preventDefault()
    if (!name.trim() || !message.trim()) {
      setSaveError('Add your name and a message.')
      return
    }
    setSaving(true)
    setSaveError('')
    const { error } = await supabase
      .from('guestbook_entries')
      .insert({ name: name.trim(), message: message.trim() })
    setSaving(false)
    if (error) {
      setSaveError('Your entry was not saved. Try again.')
      return
    }
    setMessage('')
    await load()
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-8 px-4 py-10">
      <h1 className="text-3xl font-bold">Guestbook</h1>

      <form onSubmit={sign} className="flex flex-col gap-3">
        <label htmlFor="name" className="text-sm font-medium">Name</label>
        <input
          id="name"
          value={name}
          maxLength={80}
          onChange={(e) => setName(e.target.value)}
          className="rounded border px-3 py-2"
        />
        <label htmlFor="message" className="text-sm font-medium">Message</label>
        <textarea
          id="message"
          value={message}
          maxLength={500}
          onChange={(e) => setMessage(e.target.value)}
          className="min-h-24 rounded border px-3 py-2"
        />
        {saveError && <p role="alert" className="text-sm text-red-700">{saveError}</p>}
        <button type="submit" disabled={saving} className="rounded bg-amber-800 px-4 py-2 font-semibold text-white">
          {saving ? 'Signing...' : 'Sign the guestbook'}
        </button>
      </form>

      {loading && <p>Loading entries...</p>}
      {loadError && <p role="alert">{loadError}</p>}
      <ul aria-label="Entries" className="flex flex-col gap-3">
        {entries.map((entry) => (
          <li key={entry.id} className="rounded border p-3">
            <p className="font-semibold">{entry.name}</p>
            <p className="break-words">{entry.message}</p>
          </li>
        ))}
        {!loading && !loadError && entries.length === 0 && <li>No entries yet. Be the first to sign.</li>}
      </ul>
    </main>
  )
}
