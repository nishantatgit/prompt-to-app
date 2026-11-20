// The admin page's token and its one request.
//
// The token lives in sessionStorage only: it is gone when the tab closes and
// is never written to localStorage or sent anywhere but the API.

import { errorMessage } from './errors.js'

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

// Feedback and waitlist entries, newest first.
export async function getFeedback(token) {
  const res = await fetch(`${API_BASE}/api/admin/feedback`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const body = await res.json().catch(() => ({}))
  if (res.status === 401) throw new NotAllowed('That token was not accepted.')
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  const rows = Array.isArray(body.feedback) ? body.feedback : []
  return [...rows].sort((a, b) => (b.created || 0) - (a.created || 0))
}

export function formatCost(usd) {
  if (typeof usd !== 'number') return ''
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`
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
