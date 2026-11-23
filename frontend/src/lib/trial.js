// What the app says when free builds are on but Vyskar's own AI key isn't
// working (the server reports this as paused on GET /api/trial).

export function pausedNote(ownKeys) {
  return ownKeys
    ? 'Free builds are paused right now. Add your own AI key to build.'
    : 'Free builds are paused right now. Try again a little later.'
}

// When today's free builds for everyone are taken (day_full on GET
// /api/trial), when they come back: midnight UTC, in the visitor's own time.
export function nextFreeBuildsTime(now = new Date(), locale = undefined, timeZone = undefined) {
  const midnight = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1))
  return midnight.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit', timeZone })
}
