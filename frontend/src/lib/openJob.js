// A stopped build's push notification opens Vyskar at /?job=<id>, so the
// build's screen shows what happened instead of an empty composer.

// Job ids look like 26-11-23-1763900000-abc123def0; anything else is ignored.
const JOB_ID = /^[\w-]{1,80}$/

export function jobFromSearch(search) {
  const id = new URLSearchParams(search || '').get('job')
  return id && JOB_ID.test(id) ? id : null
}

// The job named in the address, taken out of it so a reload or a new build
// does not open it again.
export function takeJobFromUrl() {
  if (typeof window === 'undefined') return null
  const id = jobFromSearch(window.location.search)
  if (id) {
    const url = new URL(window.location.href)
    url.searchParams.delete('job')
    try {
      window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash)
    } catch {
      // The address keeps the job; reopening it is harmless.
    }
  }
  return id
}
