// A random id for this browser, so free trial builds can be counted per
// person without an account. It holds nothing about the person.

const KEY = 'vyskar.visitor'

export function visitorId() {
  try {
    let id = localStorage.getItem(KEY)
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`
      localStorage.setItem(KEY, id)
    }
    return id
  } catch {
    return '' // storage blocked: no trial, the visitor can still use their own key
  }
}
