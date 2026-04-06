// [Project Remis] Build Fingerprint
console.log(
  "%c[Remis] Build Fingerprint%c\nVersion: 3.0.0\nBuild Time: 2026-04-06 09:30:00",
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

import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker'
import cssWorker from 'monaco-editor/esm/vs/language/css/css.worker?worker'
import htmlWorker from 'monaco-editor/esm/vs/language/html/html.worker?worker'
import tsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker'

self.MonacoEnvironment = {
  getWorker(_, label) {
    if (label === 'json') {
      return new jsonWorker()
    }
    if (label === 'css' || label === 'scss' || label === 'less') {
      return new cssWorker()
    }
    if (label === 'html' || label === 'handlebars' || label === 'razor') {
      return new htmlWorker()
    }
    if (label === 'typescript' || label === 'javascript') {
      return new tsWorker()
    }
    return new editorWorker()
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)