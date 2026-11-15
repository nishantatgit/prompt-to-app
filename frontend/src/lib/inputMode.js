import { useEffect, useState } from 'react'

// Phones open on the mic; bigger screens keep the text box. A choice made
// with "Type instead" or "Speak instead" is remembered on this device.
const KEY = 'vyskar.inputMode'
const PHONE = '(max-width: 639px)'

function savedMode() {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function useIsPhone() {
  const [phone, setPhone] = useState(() => window.matchMedia(PHONE).matches)
  useEffect(() => {
    const query = window.matchMedia(PHONE)
    const update = () => setPhone(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return phone
}

export function useInputMode() {
  const [mode, setMode] = useState(() => savedMode() || 'voice')
  function choose(next) {
    setMode(next)
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // private mode: the choice lasts until the page closes
    }
  }
  return [mode, choose]
}
