import { useState } from 'react'
import JsonTree from './components/JsonTree.jsx'
export default function App() {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function handleBuild() {
    if (!prompt.trim()) return
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const res = await fetch('/api/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      })
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      setResult(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 flex items-start justify-center p-6">
      <div className="w-full max-w-2xl mt-16">
        <h1 className="text-3xl font-bold text-gray-900">prompt-to-app</h1>
        <p className="mt-2 text-gray-600">
          Describe the app you want. The agent will build and deploy it.
        </p>

        <textarea
          className="mt-6 w-full h-36 rounded-lg border border-gray-300 bg-white p-4 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="e.g. A to-do list where I can add, complete, delete and filter tasks"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleBuild()
          }}
        />

        <button
          className="mt-4 rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
          onClick={handleBuild}
          disabled={loading || !prompt.trim()}
        >
          {loading ? 'Building...' : 'Build'}
        </button>

        {error && (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-6 rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-sm font-medium text-gray-500">Server response</p>
            <pre className="mt-2 whitespace-pre-wrap text-sm text-gray-800">
              <JsonTree value={result} />
            </pre>
          </div>
        )}
      </div>
    </main>
  )
}