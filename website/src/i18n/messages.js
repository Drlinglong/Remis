import sourceMessages from './source-messages.json'

const localeLoaders = {
  zh: () => import('./translations/zh.json'),
  ru: () => import('./translations/ru.json'),
  ja: () => import('./translations/ja.json'),
  de: () => import('./translations/de.json'),
  fr: () => import('./translations/fr.json'),
  es: () => import('./translations/es.json'),
  ko: () => import('./translations/ko.json'),
  pl: () => import('./translations/pl.json'),
  'pt-BR': () => import('./translations/pt-BR.json'),
  tr: () => import('./translations/tr.json'),
}

export function defineMessages(translations) {
  if (translations.length !== sourceMessages.length) {
    throw new Error(`Translation catalog length mismatch: expected ${sourceMessages.length}, received ${translations.length}`)
  }
  return Object.freeze(Object.fromEntries(sourceMessages.map((source, index) => [source, translations[index]])))
}

export const englishMessages = defineMessages(sourceMessages)

const catalogCache = new Map([['en', englishMessages]])

export async function loadMessages(locale) {
  if (catalogCache.has(locale)) return catalogCache.get(locale)
  const loader = localeLoaders[locale]
  if (!loader) return englishMessages
  const module = await loader()
  const catalog = defineMessages(module.default)
  catalogCache.set(locale, catalog)
  return catalog
}

export { sourceMessages }
