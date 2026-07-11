import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { I18nProvider } from './i18n/I18nProvider'
import { pageFromPath } from './site'
import './styles.css'

const page = pageFromPath(window.location.pathname, import.meta.env.BASE_URL)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <I18nProvider page={page}>
      <App page={page} />
    </I18nProvider>
  </StrictMode>,
)
