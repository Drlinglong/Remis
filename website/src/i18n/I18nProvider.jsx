import { useCallback, useEffect, useMemo, useState } from 'react'
import { I18nContext } from './context'
import { englishMessages, loadMessages } from './messages'
import { getInitialLocale, normalizeLocale, STORAGE_KEY, supportedLocales } from './locales'

const pageMetadata = {
  home: {
    title: 'Remis · The operating system for AI localization',
    description: 'Remis is an open-source desktop operating system for AI localization, with a governed LLM workflow and cloud-or-local model choice.',
  },
  engineering: {
    title: 'AI Engineering · Remis',
    description: 'Explore Remis AI engineering through animated workflows, provider-flexible inference, context retrieval, validation boundaries, repair loops, and human review.',
  },
  guide: {
    title: 'Beginner Guide · Remis',
    description: 'A beginner-friendly guide to installing Remis, configuring an AI provider, translating a Paradox mod, proofreading it, and enabling it in the launcher.',
  },
  roadmap: {
    title: 'Roadmap · Remis',
    description: 'The Remis roadmap, from the shipped desktop workflow to Micro-RAG onboarding, a schema-bound Copilot, and read-only Translation QA.',
  },
  notFound: {
    title: 'Page not found · Remis',
    description: 'The requested Remis product-site route could not be found.',
  },
}

function updateMetadata(page, t) {
  const metadata = pageMetadata[page] ?? pageMetadata.notFound
  const title = t(metadata.title)
  const description = t(metadata.description)

  document.title = title
  document.querySelector('meta[name="description"]')?.setAttribute('content', description)
  document.querySelector('meta[property="og:title"]')?.setAttribute('content', title)
  document.querySelector('meta[property="og:description"]')?.setAttribute('content', description)
}

export function I18nProvider({ page, children }) {
  const [locale, setLocaleState] = useState(() => getInitialLocale({
    search: window.location.search,
    storage: window.localStorage,
    languages: navigator.languages?.length ? navigator.languages : [navigator.language],
  }))
  const [catalogState, setCatalogState] = useState(() => (
    locale === 'en'
      ? { locale: 'en', catalog: englishMessages }
      : { locale: null, catalog: englishMessages }
  ))

  const t = useCallback((source) => {
    if (import.meta.env.DEV) {
      window.__remisI18nKeys ??= new Set()
      window.__remisI18nKeys.add(source)
    }
    return catalogState.catalog[source] ?? englishMessages[source] ?? source
  }, [catalogState])

  const setLocale = useCallback((language) => {
    const normalized = normalizeLocale(language) ?? 'en'
    window.localStorage.setItem(STORAGE_KEY, normalized)
    const url = new URL(window.location.href)
    if (url.searchParams.has('lang')) {
      url.searchParams.delete('lang')
      window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
    }
    setLocaleState(normalized)
  }, [])

  useEffect(() => {
    let current = true
    loadMessages(locale)
      .then((catalog) => {
        if (current) setCatalogState({ locale, catalog })
      })
      .catch(() => {
        if (!current) return
        window.localStorage.setItem(STORAGE_KEY, 'en')
        setLocaleState('en')
        setCatalogState({ locale: 'en', catalog: englishMessages })
      })
    return () => {
      current = false
    }
  }, [locale])

  useEffect(() => {
    document.documentElement.lang = locale
    if (catalogState.locale === locale) updateMetadata(page, t)
  }, [catalogState.locale, locale, page, t])

  const value = useMemo(() => ({ locale, setLocale, supportedLocales, t }), [locale, setLocale, t])

  return (
    <I18nContext.Provider value={value}>
      {catalogState.locale === locale
        ? children
        : <div className="language-loader" role="status" aria-label="REMIS">REMIS</div>}
    </I18nContext.Provider>
  )
}
