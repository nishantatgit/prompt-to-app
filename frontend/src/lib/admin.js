// The admin page's token and its one request.
//
// The token lives in sessionStorage only: it is gone when the tab closes and
// is never written to localStorage or sent anywhere but the API.

import { UNREACHABLE, errorMessage } from './errors.js'

const API_BASE = import.meta.env.VITE_API_URL || ''
const KEY = 'vyskar-admin-token'

export function loadToken() {
  try {
    return sessionStorage.getItem(KEY) || ''
  } catch {
    return ''
  }
}

export function saveToken(token) {
  try {
    if (token) sessionStorage.setItem(KEY, token)
    else sessionStorage.removeItem(KEY)
  } catch {
    // Storage blocked: the token still works until the page reloads.
  }
}

// app.vyskar.com/admin, with or without a trailing slash.
export function isAdminPage() {
  return window.location.pathname.replace(/\/+$/, '') === '/admin'
}

export class NotAllowed extends Error {}

const KINDS = ['feedback', 'waitlist']

// How many of each kind are stored. The API sends this because it returns
// only the newest entries; an older API without it is counted from the rows.
function readTotals(totals, rows) {
  const counted = Object.fromEntries(KINDS.map((kind) => [kind, rows.filter((r) => r.kind === kind).length]))
  if (!totals || typeof totals !== 'object') return counted
  return Object.fromEntries(
    KINDS.map((kind) => {
      const n = totals[kind]
      return [kind, Number.isInteger(n) && n >= counted[kind] ? n : counted[kind]]
    }),
  )
}

// The total for a filter: 'all', 'feedback' or 'waitlist'.
export function totalFor(totals, filter) {
  if (filter === 'all') return KINDS.reduce((sum, kind) => sum + (totals?.[kind] || 0), 0)
  return totals?.[filter] || 0
}

// The newest feedback and waitlist entries, newest first, with how many of
// each kind are stored in all: { rows, totals }.
export async function getFeedback(token) {
  let res
  try {
    res = await fetch(`${API_BASE}/api/admin/feedback`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  } catch {
    // No signal or the API is down: say so, not the browser's "Failed to fetch".
    throw new Error(UNREACHABLE)
  }
  const body = await res.json().catch(() => ({}))
  if (res.status === 401) throw new NotAllowed('That token was not accepted.')
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  const rows = Array.isArray(body.feedback) ? body.feedback : []
  const sorted = [...rows].sort((a, b) => (b.created || 0) - (a.created || 0) || (b.id || 0) - (a.id || 0))
  return { rows: sorted, totals: readTotals(body.totals, sorted) }
}

export function formatCost(usd) {
  if (typeof usd !== 'number') return ''
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`
}

// The backend's confidence is already a percentage (0 to 100, one decimal),
// the same number the build screen shows.
export function formatConfidence(percent) {
  if (typeof percent !== 'number' || !Number.isFinite(percent)) return ''
  return `${Math.round(percent)}%`
}

export function formatWhen(seconds) {
  if (!seconds) return ''
  return new Date(seconds * 1000).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}
