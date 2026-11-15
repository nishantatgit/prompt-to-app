import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { loadClarity } from './lib/clarity.js'
import { registerServiceWorker } from './lib/pwa.js'
import { hideSplash } from './lib/splash.js'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Two frames: the first screen has been painted when the second one starts.
requestAnimationFrame(() => requestAnimationFrame(hideSplash))
registerServiceWorker()
loadClarity()
