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
  return `Server returned ${status}`
}
