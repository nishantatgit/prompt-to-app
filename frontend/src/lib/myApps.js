// The apps this browser built, with the edit key that lets Vyskar change
// them. Only this browser has the keys: clearing site data loses them.
const KEY = 'vyskar.apps'
const MAX_APPS = 50

export function loadApps() {
  try {
    const apps = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(apps) ? apps : []
  } catch {
    return []
  }
}

function save(apps) {
  try {
    localStorage.setItem(KEY, JSON.stringify(apps))
  } catch {
    // private mode or full storage: the list lasts until the page closes
  }
}

// Newest first. A changed app moves to the top and keeps its first prompt
// and its key.
export function rememberApp({ name, url, editKey, prompt }) {
  const apps = loadApps()
  const old = apps.find((app) => app.name === name)
  const entry = {
    name,
    url,
    editKey: editKey || old?.editKey,
    prompt: old?.prompt || prompt,
    updatedAt: Date.now(),
  }
  const next = [entry, ...apps.filter((app) => app.name !== name)].slice(0, MAX_APPS)
  save(next)
  return next
}

export function forgetApp(name) {
  const next = loadApps().filter((app) => app.name !== name)
  save(next)
  return next
}
