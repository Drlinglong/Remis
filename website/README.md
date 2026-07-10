# Remis product site

React/Vite source for the Remis GitHub Pages site.

## Local development

```powershell
npm install
npm run dev
```

Vite serves the site under `/Remis/` so local routing matches the GitHub Pages project URL.

## Verification

```powershell
npm run lint
npm run test
npm run build
npm run preview
```

The site is a true multi-page Vite build. Each public route has its own HTML entry:

- `/Remis/`
- `/Remis/engineering/`
- `/Remis/guide/`
- `/Remis/roadmap/`

GitHub Actions deploys `website/dist` when site changes land on `main`.
