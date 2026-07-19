import { createContext, useContext } from 'react'

export const I18nContext = createContext(null)

const nonTranslatableFields = new Set(['action', 'asset', 'code', 'href', 'index', 'number', 'value', 'version'])

export function translateDeep(value, t, field = '') {
  if (nonTranslatableFields.has(field)) return value
  if (typeof value === 'string') return t(value)
  if (Array.isArray(value)) return value.map((item) => translateDeep(item, t))
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, translateDeep(item, t, key)]))
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) throw new Error('useI18n must be used inside I18nProvider')
  return context
}
