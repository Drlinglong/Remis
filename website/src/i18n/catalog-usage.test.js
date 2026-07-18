import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  agentMilestones,
  aventineEvidence,
  aventineProofPoints,
  aventineRanking,
  aventineRecipeStages,
  benchmarkMetrics,
  copilotLayers,
  guideQuestions,
  guideSteps,
  pages,
  pipeline,
  productLayers,
  proofPoints,
  roadmapPhases,
  workflowDiagrams,
} from '../site'
import { sourceMessages } from './messages'

const srcDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const nonTranslatableFields = new Set([
  'asset',
  'code',
  'href',
  'index',
  'key',
  'number',
  'path',
  'rank',
  'recipe',
  'hardPass',
  'record',
  'unresolved',
  'evidence',
  'value',
  'version',
])

function collectDataMessages(value, messages, field = '') {
  if (nonTranslatableFields.has(field)) return
  if (typeof value === 'string') {
    messages.add(value)
    return
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectDataMessages(item, messages))
    return
  }
  if (!value || typeof value !== 'object') return
  Object.entries(value).forEach(([key, item]) => collectDataMessages(item, messages, key))
}

function sourceFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name)
    if (entry.isDirectory()) return entry.name === 'i18n' ? [] : sourceFiles(entryPath)
    return /\.(?:js|jsx)$/.test(entry.name) && !entry.name.endsWith('.test.js') ? [entryPath] : []
  })
}

function collectInlineMessages() {
  const messages = new Set()
  const directTranslation = /\bt\(\s*(['"`])([\s\S]*?)\1\s*\)/g
  const translatedChild = /<(ButtonLink|TextLink|StatusPill)\b[^>]*>([^<{]+)<\/\1>/g

  for (const file of sourceFiles(srcDirectory)) {
    const source = fs.readFileSync(file, 'utf8')
    for (const match of source.matchAll(directTranslation)) messages.add(match[2].trim())
    for (const match of source.matchAll(translatedChild)) messages.add(match[2].trim())
  }
  return messages
}

describe('catalog usage', () => {
  it('contains every message referenced directly by website components', () => {
    const catalog = new Set(sourceMessages)
    const missing = [...collectInlineMessages()].filter((message) => !catalog.has(message))
    expect(missing).toEqual([])
  })

  it('contains every translatable message in shared site data', () => {
    const usedMessages = new Set()
    ;[
      pages,
      proofPoints,
      pipeline,
      productLayers,
      workflowDiagrams,
      copilotLayers,
      guideSteps,
      guideQuestions,
      roadmapPhases,
      agentMilestones,
      aventineEvidence,
      aventineProofPoints,
      aventineRanking,
      aventineRecipeStages,
    ].forEach((value) => collectDataMessages(value, usedMessages))
    benchmarkMetrics.forEach(([, question]) => usedMessages.add(question))

    const catalog = new Set(sourceMessages)
    const missing = [...usedMessages].filter((message) => !catalog.has(message))
    expect(missing).toEqual([])
  })
})
