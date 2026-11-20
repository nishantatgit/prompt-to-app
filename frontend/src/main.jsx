import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import Root from './Root.jsx'
import { isAdminPage } from './lib/admin.js'
import { loadClarity } from './lib/clarity.js'
import { registerServiceWorker } from './lib/pwa.js'
import { hideSplash } from './lib/splash.js'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)

// Two frames: the first screen has been painted when the second one starts.
requestAnimationFrame(() => requestAnimationFrame(hideSplash))
registerServiceWorker()
// No session recording on the admin page: it shows people's feedback and emails.
if (!isAdminPage()) loadClarity()
