import { describe, expect, it } from 'vitest'
import {
  agentMilestones,
  aventineEvidence,
  aventineProofPoints,
  aventineRanking,
  aventineRecipeStages,
  pageFromPath,
  productLayers,
  roadmapPhases,
  SITE_BASE,
  workflowDiagrams,
} from './site'

describe('pageFromPath', () => {
  it.each([
    ['/Remis/', 'home'],
    ['/Remis/index.html', 'home'],
    ['/Remis/engineering/', 'engineering'],
    ['/Remis/aventine/', 'aventine'],
    ['/Remis/guide/', 'guide'],
    ['/Remis/roadmap/', 'roadmap'],
    ['/Remis/not-a-page/', 'notFound'],
  ])('maps %s to %s', (path, page) => {
    expect(pageFromPath(path, SITE_BASE)).toBe(page)
  })
})

describe('roadmap content', () => {
  it('labels every future-facing claim with a delivery status', () => {
    expect(roadmapPhases.every((phase) => phase.status && phase.version)).toBe(true)
  })
})

describe('product positioning content', () => {
  it('labels every product layer with a delivery status', () => {
    expect(productLayers.map((layer) => layer.status)).toEqual([
      'Shipped',
      'In development',
      'In development',
    ])
  })

  it('documents every workflow with its trust-boundary questions', () => {
    expect(workflowDiagrams).toHaveLength(3)
    expect(workflowDiagrams.every((workflow) => (
      workflow.asset
      && workflow.input
      && workflow.state
      && workflow.model
      && workflow.recovery
    ))).toBe(true)
  })

  it('publishes the Agent delivery and Aventine evidence contracts', () => {
    expect(agentMilestones).toHaveLength(4)
    expect(aventineProofPoints).toHaveLength(4)
    expect(aventineRecipeStages).toHaveLength(3)
    expect(aventineRanking[0]).toMatchObject({
      recipe: 'Qwen 3.6 27B Q4_K_M',
      result: 'Champion',
    })
    expect(aventineEvidence).toHaveLength(4)
  })
})
