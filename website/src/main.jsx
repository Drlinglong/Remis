import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { pageFromPath } from './site'
import './styles.css'

const page = pageFromPath(window.location.pathname, import.meta.env.BASE_URL)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App page={page} />
  </StrictMode>,
)
