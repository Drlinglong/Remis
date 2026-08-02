import { describe, expect, it } from 'vitest'
import { formatPilotCost, pilotMeta, pilotRecipes } from './aventinePilotData'

describe('Aventine pilot website data', () => {
  it('publishes all nine artifact-backed recipes in rank order', () => {
    expect(pilotMeta).toMatchObject({
      aggregateId: 'remis-nine-model-pilot-2026-08-01',
      scoreVersion: 'pilot-score-v0.1',
      recipes: 9,
      hardTasksPerRecipe: 21,
    })
    expect(pilotRecipes).toHaveLength(9)
    expect(pilotRecipes.map((recipe) => recipe.rank)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9])
    expect(pilotRecipes[0]).toMatchObject({ id: 'gemini36', model: 'Gemini 3.6 Flash', score: 84.21, reasoning: 'high' })
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
    const freeRecipes = pilotRecipes.filter((recipe) => recipe.costUsd === null)
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
  })
})
