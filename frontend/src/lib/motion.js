// Whether the phone or computer asks for less motion (Reduce Motion on iOS,
// Remove animations on Android). A browser that can't say gets the normal motion.
export function prefersReducedMotion() {
  try {
    return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
  } catch {
    return false
  }
}

// The scroll behavior for scrollTo and scrollIntoView: a jump instead of a
// glide when less motion is asked for. A behavior set in script ignores the
// CSS scroll-behavior rule, so each script scroll has to ask.
export function scrollBehavior() {
  return prefersReducedMotion() ? 'auto' : 'smooth'
}
