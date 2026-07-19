# Remis product site

React/Vite source for the Remis GitHub Pages site.

The public positioning is a mature open-source desktop AI product, not a commercial
SaaS. The homepage uses `The operating system for AI localization.` as the category
statement, then distinguishes local project control from cloud-or-local model
inference. Future RAG and agent claims must retain visible delivery status.
The in-app Copilot remains an in-development roadmap item and is not presented
as shipped in v3.0.7. The standalone Aventine page presents the first
reproducible translation-recipe tournament and judge-calibration results.

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
- `/Remis/aventine/`
- `/Remis/guide/`
- `/Remis/roadmap/`

GitHub Actions deploys `website/dist` when site changes land on `main`.

## Internationalization

The product site supports the same 11 languages as the Remis desktop app:

- English
- 简体中文
- Русский
- 日本語
- Deutsch
- Français
- Español
- 한국어
- Polski
- Português (Brasil)
- Türkçe

Language selection follows this order:

1. A valid `?lang=` URL override;
2. The visitor's manual choice stored in `localStorage`;
3. The first supported entry in `navigator.languages`;
4. English fallback.

Visitors can change language from the header on every page. Manual choices persist,
update `<html lang>`, and refresh each page's title, description, and Open Graph copy.
Non-English catalogs are loaded on demand so the default bundle does not contain all
ten additional translations.

`src/i18n/source-messages.json` is the canonical message contract. Every translation
array must have the same number of non-empty entries, which is enforced by unit tests.
Product and technology names such as Remis, RAG, LLM, Ollama, OpenAI, PydanticAI, and
LlamaIndex, and Aventine are also protected from accidental translation.

## Engineering diagrams

The Engineering page republishes the repository's existing animated workflow SVGs:

- `public/assets/project-management-workflow.svg`
- `public/assets/incremental-update-workflow.svg`
- `public/assets/agentic-repair-workflow.svg`

These are copied from the README assets in the repository root so GitHub Pages can
serve them under the `/Remis/` base path. Keep the public copies synchronized when the
source workflows change. The page supplies adjacent text for input, retained state,
model role, and recovery behaviour; reduced-motion visitors receive the text without
the animated image.
