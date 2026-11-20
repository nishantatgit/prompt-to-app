import { Suspense, lazy } from 'react'
import App from './App.jsx'
import { isAdminPage } from './lib/admin.js'

// /admin is its own small page, loaded only there, so the app's bundle
// carries none of it.
const Admin = lazy(() => import('./components/Admin.jsx'))

export default function Root() {
  if (!isAdminPage()) return <App />
  return (
    <Suspense fallback={null}>
      <Admin />
    </Suspense>
  )
}
