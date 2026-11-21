// What the app says when free builds are on but Vyskar's own AI key isn't
// working (the server reports this as paused on GET /api/trial).

export function pausedNote(ownKeys) {
  return ownKeys
    ? 'Free builds are paused right now. Add your own AI key to build.'
    : 'Free builds are paused right now. Try again a little later.'
}
