/* global __APP_VERSION__ */

import { openExternalUrl } from './utils/externalLinks';

// [Project Remis] Build Fingerprint
console.log(
  `%c[Remis] Build Fingerprint%c\nVersion: ${__APP_VERSION__}`,
  "background: #4a5568; color: #fff; padding: 2px 4px; border-radius: 4px; font-weight: bold;",
  "color: #718096; font-style: italic;"
);

if (import.meta.env.DEV) {
  const showErrorOverlay = (err) => {
    if (!err) return;
    const ErrorOverlay = customElements.get('vite-error-overlay');
    if (!ErrorOverlay) {
      return;
    }
    try {
      const overlay = new ErrorOverlay(err);
      document.body.appendChild(overlay);
    } catch (e) {
      console.error("Failed to render Vite error overlay", e);
    }
  };

  window.addEventListener('error', (e) => {
    if (e.error) showErrorOverlay(e.error);
  });
  window.addEventListener('unhandledrejection', (e) => {
    if (e.reason) showErrorOverlay(e.reason);
  });
}

document.addEventListener('click', async (e) => {
  const link = e.target.closest('a[href]');
  if (!link) return;

  const href = link.getAttribute('href');
  // Only handle external http/https links
  if (href && (href.startsWith('http://') || href.startsWith('https://'))) {
    e.preventDefault();
    e.stopPropagation();

    try {
      await openExternalUrl(href);
    } catch (err) {
      console.warn('Failed to open external link:', err);
    }
  }
}, true); // Use capture phase to ensure we catch events even if propagation is stopped

import './i18n/i18n';
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './themes/definitions.css' // Import Centralized Design Tokens
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
