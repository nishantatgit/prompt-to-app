// Turns an API error body into a sentence a person can act on.
//
// Most errors carry `detail` as a string. FastAPI's validation errors (422)
// carry a list of objects instead, which used to show up as "[object Object]",
// for example when a pasted order ID went into "Restore builds".

import { MAX_PROMPT_CHARS } from './prompt.js'

// What to say when a field was rejected, by the field's name.
const FIELD_MESSAGES = {
  payment_id: "That doesn't look like a payment ID. It starts with pay_ and is on your Razorpay receipt.",
  email: 'That email is too long. Check it and try again.',
  message: 'That message is too long. Keep it under 4000 characters.',
  prompt: `That description is too long. Keep it under ${MAX_PROMPT_CHARS} characters.`,
  answers: "Those answers weren't accepted. Shorten them and try again.",
  app: "That app name isn't valid. Open it again from My apps.",
}

// A blank description is refused too, which "too long" would not explain.
const EMPTY_PROMPT = 'Describe your app first, then build it.'

const FALLBACK = "Something in the request wasn't accepted. Check it and try again."

// When the request never reached Vyskar: no signal, or the server is away.
// Browsers word this as "Failed to fetch" (Chrome) or "Load failed" (Safari).
export const UNREACHABLE = "Can't reach Vyskar right now. Check your connection and try again."

// Fly's proxy answers these, without a detail, while the server restarts
// after a deploy or is overloaded.
const AWAY_STATUSES = new Set([502, 503, 504])
export const SERVER_AWAY = 'Vyskar is restarting. Try again in a minute.'

function fieldOf(item) {
  // loc looks like ["body", "payment_id"] or ["body", "answers", 0, "answer"].
  const loc = Array.isArray(item?.loc) ? item.loc : []
  return loc.find((part) => typeof part === 'string' && part in FIELD_MESSAGES)
}

export function errorMessage(body, status) {
  const detail = body?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    const item = detail.find(fieldOf)
    if (!item) return FALLBACK
    const field = fieldOf(item)
    if (field === 'prompt' && item.type === 'string_too_short') return EMPTY_PROMPT
    return FIELD_MESSAGES[field]
  }
  if (AWAY_STATUSES.has(status)) return SERVER_AWAY
  return `Server returned ${status}`
}
