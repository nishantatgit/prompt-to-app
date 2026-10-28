const API_BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail || `Server returned ${res.status}`)
  return body
}

export function startBuild({ prompt, provider, apiKey }) {
  return request('/api/build', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, provider, api_key: apiKey || null }),
  })
}

export function getJob(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`)
}
