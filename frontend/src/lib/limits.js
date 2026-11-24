// Feedback limits the API enforces, in backend/api/feedback.py. The backend
// test test_frontend_limits.py fails if these drift from the server's.

// The longest feedback message the API takes (MAX_FEEDBACK_CHARS).
export const MAX_FEEDBACK_CHARS = 4000

// How long a message must be to earn bonus builds (MIN_MESSAGE_FOR_BONUS).
export const FEEDBACK_BONUS_MIN_CHARS = 20

// Characters as the server counts them: Python's len() counts each emoji as
// one, while a JavaScript string's length counts most emoji as two.
export function serverLength(text) {
  return [...text].length
}
