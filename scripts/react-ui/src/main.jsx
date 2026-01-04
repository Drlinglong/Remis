if (import.meta.env.DEV) {
  const showErrorOverlay = (err) => {
    const ErrorOverlay = customElements.get('vite-error-overlay');
    if (!ErrorOverlay) {
      return;
    }
    const overlay = new ErrorOverlay(err);
    document.body.appendChild(overlay);
  };

  window.addEventListener('error', (e) => showErrorOverlay(e.error));
  window.addEventListener('unhandledrejection', (e) => showErrorOverlay(e.reason));
}

// [TAURI] Handle external links - open in system browser
// [TAURI] Handle external links - open in system browser
document.addEventListener('click', async (e) => {
  const link = e.target.closest('a[href]');
  if (!link) return;

  const href = link.getAttribute('href');
  // Only handle external http/https links
  if (href && (href.startsWith('http://') || href.startsWith('https://'))) {
    e.preventDefault();
    e.stopPropagation();

    // Use Tauri shell API if available (in production build)
    if (window.__TAURI__) {
      try {
        const { open } = await import('@tauri-apps/plugin-shell');
        await open(href);
      } catch (err) {
        console.warn('Failed to open link via Tauri shell:', err);
        // Fallback: try window.open
        window.open(href, '_blank');
      }
    } else {
      // Dev mode: use regular browser navigation
      window.open(href, '_blank');
    }
  }
}, true); // Use capture phase to ensure we catch events even if propagation is stopped

import './i18n/i18n';
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './themes/index.css'
import './themes/definitions.css' // Import Centralized Design Tokens
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)