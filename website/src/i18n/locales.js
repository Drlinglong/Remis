export const STORAGE_KEY = 'remis-site-language'

export const supportedLocales = [
  { code: 'en', label: 'English' },
  { code: 'zh', label: '简体中文' },
  { code: 'ru', label: 'Русский' },
  { code: 'ja', label: '日本語' },
  { code: 'de', label: 'Deutsch' },
  { code: 'fr', label: 'Français' },
  { code: 'es', label: 'Español' },
  { code: 'ko', label: '한국어' },
  { code: 'pl', label: 'Polski' },
  { code: 'pt-BR', label: 'Português (Brasil)' },
  { code: 'tr', label: 'Türkçe' },
]

const supportedCodes = new Set(supportedLocales.map(({ code }) => code))

export function normalizeLocale(language) {
  if (!language) return null

  const normalized = String(language).replaceAll('_', '-').toLowerCase()
  if (normalized === 'zh' || normalized.startsWith('zh-')) return 'zh'
  if (normalized === 'pt' || normalized.startsWith('pt-')) return 'pt-BR'

  const base = normalized.split('-')[0]
  return supportedCodes.has(base) ? base : null
}

export function detectPreferredLocale(languages = []) {
  for (const language of languages) {
    const normalized = normalizeLocale(language)
    if (normalized) return normalized
  }
  return 'en'
}

export function getInitialLocale({ search = '', storage, languages = [] } = {}) {
  const requested = new URLSearchParams(search).get('lang')
  const requestedLocale = normalizeLocale(requested)
  if (requestedLocale) return requestedLocale

  const storedLocale = normalizeLocale(storage?.getItem(STORAGE_KEY))
  if (storedLocale) return storedLocale

  return detectPreferredLocale(languages)
}
