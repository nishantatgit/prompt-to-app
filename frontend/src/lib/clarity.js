// Microsoft Clarity: heatmaps and session recordings.
//
// Loads only in production builds, and only when VITE_CLARITY_PROJECT_ID is
// set (in .env.production). Anything marked data-clarity-mask, such as the
// API key field, is never recorded.

export function loadClarity(projectId = import.meta.env.VITE_CLARITY_PROJECT_ID) {
  if (!import.meta.env.PROD || !projectId || typeof window === 'undefined') return
  if (window.clarity) return

  // Clarity's own loader: queue calls until the script arrives.
  window.clarity = function (...args) {
    ;(window.clarity.q = window.clarity.q || []).push(args)
  }
  const script = document.createElement('script')
  script.async = true
  script.src = `https://www.clarity.ms/tag/${encodeURIComponent(projectId)}`
  document.head.appendChild(script)
}
