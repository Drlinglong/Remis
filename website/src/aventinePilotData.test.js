import { describe, expect, it } from 'vitest'
import { formatPilotCost, pilotMeta, pilotRecipes } from './aventinePilotData'

describe('Aventine pilot website data', () => {
  it('publishes all eleven artifact-backed recipes in one rank order', () => {
    expect(pilotMeta).toMatchObject({
      recipes: 11,
      hardTasksPerRecipe: 21,
      pairwiseReports: 42,
    })
    expect(pilotMeta.aggregateIds).toEqual([
      'remis-nine-model-pilot-2026-08-01',
      'remis-anchor-panel-placement-2026-08-02',
    ])
    expect(pilotRecipes).toHaveLength(11)
    expect(pilotRecipes.map((recipe) => recipe.rank)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    expect(pilotRecipes[0]).toMatchObject({ id: 'gemini36', model: 'Gemini 3.6 Flash', score: 84.21, reasoning: 'high' })
    expect(pilotRecipes[4]).toMatchObject({
      id: 'qwen37',
      score: 71.12,
      scoreVersion: 'pilot-score-v0.2-anchored',
      placementStatus: 'provisional',
    })
    expect(pilotRecipes[10]).toMatchObject({
      id: 'translategemma',
      score: 39.29,
      costKind: 'local-hardware',
    })
  })

  it('keeps the published score formula reproducible', () => {
    for (const recipe of pilotRecipes) {
      const reconstructed = (0.6 * recipe.softPreference) + (0.4 * recipe.hardReliability)
      expect(recipe.score).toBeCloseTo(reconstructed, 1)
      expect(recipe.coverage).toBeGreaterThan(0)
      expect(recipe.tasksPerHour).toBeGreaterThan(0)
    }
  })

  it('shows provider benefits as Free tier rather than zero-dollar inference', () => {
    const freeRecipes = pilotRecipes.filter((recipe) => recipe.costKind === 'free-tier')
    expect(freeRecipes.map((recipe) => recipe.id)).toEqual(['gemma4', 'nemotron', 'ling'])
    expect(freeRecipes.every((recipe) => formatPilotCost(recipe) === 'Free tier')).toBe(true)
    expect(freeRecipes.every((recipe) => formatPilotCost(recipe, true) !== '$0.000')).toBe(true)
  })

  it('scales paid costs to 100 tasks without changing the recorded run total', () => {
    const gemini36 = pilotRecipes.find((recipe) => recipe.id === 'gemini36')
    const luna = pilotRecipes.find((recipe) => recipe.id === 'luna')
    expect(gemini36.costUsd).toBe(0.41429)
    expect(gemini36.costPer100).toBeCloseTo(1.973, 3)
    expect(luna.costUsd).toBe(0.01066)
    expect(luna.costPer100).toBeCloseTo(0.051, 3)
    expect(luna.style.en).toContain('second-fastest')
    expect(luna.style.zh).toContain('第二快')
    const qwen = pilotRecipes.find((recipe) => recipe.id === 'qwen37')
    expect(qwen.costUsd).toBe(0.06359)
    expect(qwen.costPer100).toBeCloseTo(0.303, 3)
    const translateGemma = pilotRecipes.find((recipe) => recipe.id === 'translategemma')
    expect(formatPilotCost(translateGemma)).toBe('Local GPU')
    expect(formatPilotCost(translateGemma, false, 'zh')).toBe('本地 GPU')
    expect(translateGemma.outputTokens).toBeNull()
  })
})
