// Deletes an app's Supabase database after its tests, so the next app can
// have one. The free plan allows only 2 active databases per account.
//
// Vyskar names each database after the app (the job's database_name). The
// calls are the ones the Vercel CLI makes for `integration resource remove`.

const API = 'https://api.vercel.com'

function url(route) {
  const team = process.env.VERCEL_TEAM_ID
  return `${API}${route}${team ? `${route.includes('?') ? '&' : '?'}teamId=${team}` : ''}`
}

async function call(route, method = 'GET') {
  const res = await fetch(url(route), {
    method,
    headers: { Authorization: `Bearer ${process.env.VERCEL_TOKEN}` },
  })
  if (!res.ok && res.status !== 404) throw new Error(`${method} ${route} returned ${res.status}`)
  return res.status === 204 ? {} : res.json().catch(() => ({}))
}

// Returns true when a database with that name existed and was deleted.
export async function deleteDatabase(name) {
  if (!name) return false
  if (!process.env.VERCEL_TOKEN) throw new Error('VERCEL_TOKEN is needed to delete databases')
  const { stores = [] } = await call('/v1/storage/stores')
  const store = stores.find((s) => s.name === name)
  if (!store) return false
  await call(`/v1/storage/stores/${store.id}/connections`, 'DELETE')
  await call(`/v1/storage/stores/integration/${store.id}`, 'DELETE')
  return true
}
