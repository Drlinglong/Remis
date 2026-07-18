import { describe, expect, it } from 'vitest'
import { supportedLocales } from './locales'
import { loadMessages, sourceMessages } from './messages'

const protectedProductTerms = [
  'Remis',
  'RAG',
  'LLM',
  'Ollama',
  'OpenAI',
  'GitHub',
  'Tauri',
  'React',
  'FastAPI',
  'SQLite',
  'PydanticAI',
  'LlamaIndex',
  'Paradox',
  'Copilot',
  'Micro-RAG',
  'Aventine',
]

describe('translation catalogs', () => {
  it('has a unique canonical source key for every website message', () => {
    expect(sourceMessages.length).toBeGreaterThan(250)
    expect(new Set(sourceMessages).size).toBe(sourceMessages.length)
  })

  it.each(supportedLocales.map(({ code }) => [code]))('%s has a complete non-empty catalog', async (locale) => {
    const catalog = await loadMessages(locale)
    expect(Object.keys(catalog)).toHaveLength(sourceMessages.length)
    expect(sourceMessages.every((source) => typeof catalog[source] === 'string' && catalog[source].trim())).toBe(true)
  })

  it.each(supportedLocales.filter(({ code }) => code !== 'en').map(({ code }) => [code]))(
    '%s preserves product and technology names',
    async (locale) => {
      const catalog = await loadMessages(locale)
      for (const source of sourceMessages) {
        for (const term of protectedProductTerms) {
          if (source.includes(term)) expect(catalog[source]).toContain(term)
        }
      }
    },
  )
})
